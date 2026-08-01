package com.meartraep.alician.mobile.data

import android.app.Application
import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper
import androidx.core.content.edit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale

data class StudyCard(
    val item: StudyItem,
    val progress: StudyProgress? = null,
) {
    val isNew: Boolean get() = progress == null
}

data class StudyOverview(
    val totalCards: Int = 0,
    val dueCount: Int = 0,
    val unseenCount: Int = 0,
    val newRemainingToday: Int = 0,
    val learningCount: Int = 0,
    val learnedCount: Int = 0,
    val masteredCount: Int = 0,
    val reviewedToday: Int = 0,
    val rememberedToday: Int = 0,
    val newSeenToday: Int = 0,
    val streakDays: Int = 0,
    val nextDueAtEpochMillis: Long? = null,
) {
    val retentionToday: Float
        get() = if (reviewedToday == 0) 0f else rememberedToday.toFloat() / reviewedToday
}

data class StudySessionPlan(
    val cards: List<StudyCard> = emptyList(),
    val dueCount: Int = 0,
    val newCount: Int = 0,
)

/**
 * Keeps learning records separate from translated.db. Dictionary replacement can therefore
 * refresh definitions without erasing the user's review history.
 */
class StudyRepository(
    application: Application,
    private val dictionaryPath: String,
    private val scheduler: StudyScheduler = StudyScheduler(),
) {
    private val progressDatabase = StudyProgressDatabase(application)
    private val preferences =
        application.getSharedPreferences(STUDY_PREFERENCES, Application.MODE_PRIVATE)
    private val mutex = Mutex()

    val settings: StudySettings
        get() = StudySettings(
            order = preferenceEnum(SETTING_ORDER, StudyOrder.FREQUENCY),
            content = preferenceEnum(SETTING_CONTENT, StudyContent.ALL),
            dailyNewLimit = preferences.getInt(SETTING_DAILY_NEW, DEFAULT_DAILY_NEW)
                .coerceIn(MIN_DAILY_NEW, MAX_DAILY_NEW),
            alphabetCompleted = preferences.getBoolean(SETTING_ALPHABET_COMPLETE, false),
        )

    fun saveSettings(value: StudySettings) {
        preferences.edit {
            putString(SETTING_ORDER, value.order.name)
            putString(SETTING_CONTENT, value.content.name)
            putInt(
                SETTING_DAILY_NEW,
                value.dailyNewLimit.coerceIn(MIN_DAILY_NEW, MAX_DAILY_NEW),
            )
            putBoolean(SETTING_ALPHABET_COMPLETE, value.alphabetCompleted)
        }
    }

    suspend fun loadOverview(
        value: StudySettings = settings,
        nowEpochMillis: Long = System.currentTimeMillis(),
    ): StudyOverview = withContext(Dispatchers.IO) {
        mutex.withLock {
            val items = loadItems(value.content)
            val itemIds = items.asSequence().map { it.id }.toHashSet()
            val progress = loadProgress().filterKeys(itemIds::contains)
            val daily = loadDaily(dayKey(nowEpochMillis))
            val unseenCount = items.count { it.id !in progress }
            val futureDue = progress.values
                .asSequence()
                .map { it.dueAtEpochMillis }
                .filter { it > nowEpochMillis }
                .minOrNull()
            StudyOverview(
                totalCards = items.size,
                dueCount = progress.values.count { it.dueAtEpochMillis <= nowEpochMillis },
                unseenCount = unseenCount,
                newRemainingToday = minOf(
                    unseenCount,
                    (value.dailyNewLimit - daily.newSeen).coerceAtLeast(0),
                ),
                learningCount = progress.values.count { it.phase != StudyPhase.REVIEW },
                learnedCount = progress.size,
                masteredCount = progress.values.count {
                    it.phase == StudyPhase.REVIEW && it.intervalDays >= MATURE_INTERVAL_DAYS
                },
                reviewedToday = daily.answers,
                rememberedToday = daily.remembered,
                newSeenToday = daily.newSeen,
                streakDays = calculateStreak(nowEpochMillis),
                nextDueAtEpochMillis = futureDue,
            )
        }
    }

    suspend fun buildSession(
        value: StudySettings = settings,
        nowEpochMillis: Long = System.currentTimeMillis(),
    ): StudySessionPlan = withContext(Dispatchers.IO) {
        mutex.withLock {
            val items = loadItems(value.content)
            val progress = loadProgress()
            val daily = loadDaily(dayKey(nowEpochMillis))

            val dueCards = items.mapNotNull { item ->
                val itemProgress = progress[item.id] ?: return@mapNotNull null
                if (itemProgress.dueAtEpochMillis <= nowEpochMillis) {
                    StudyCard(item, itemProgress)
                } else {
                    null
                }
            }.sortedWith(
                compareBy<StudyCard> {
                    when (it.progress?.phase) {
                        StudyPhase.LEARNING, StudyPhase.RELEARNING -> 0
                        StudyPhase.REVIEW, null -> 1
                    }
                }.thenBy { it.progress?.dueAtEpochMillis ?: Long.MAX_VALUE },
            )

            val newBudget = (value.dailyNewLimit - daily.newSeen).coerceAtLeast(0)
            val newItems = orderStudyItems(
                items = items.filter { it.id !in progress },
                order = value.order,
                randomSeed = dayKey(nowEpochMillis).hashCode().toLong(),
            ).take(newBudget)
            val newCards = newItems.map(::StudyCard)

            StudySessionPlan(
                cards = dueCards + newCards,
                dueCount = dueCards.size,
                newCount = newCards.size,
            )
        }
    }

    suspend fun review(
        card: StudyCard,
        rating: StudyRating,
        reviewedAtEpochMillis: Long = System.currentTimeMillis(),
    ): StudyProgress = withContext(Dispatchers.IO) {
        mutex.withLock {
            val writable = progressDatabase.writableDatabase
            val previous = loadProgress(card.item.id, writable)
            val next = scheduler.schedule(
                progress = previous ?: StudyProgress(itemId = card.item.id),
                rating = rating,
                reviewedAtEpochMillis = reviewedAtEpochMillis,
            )
            writable.beginTransaction()
            try {
                saveProgress(next, writable)
                updateDaily(
                    database = writable,
                    day = dayKey(reviewedAtEpochMillis),
                    remembered = rating != StudyRating.AGAIN,
                    isNew = previous == null,
                )
                writable.setTransactionSuccessful()
            } finally {
                writable.endTransaction()
            }
            next
        }
    }

    fun ratingPreview(
        card: StudyCard,
        nowEpochMillis: Long = System.currentTimeMillis(),
    ): List<StudyRatingPreview> = scheduler.preview(
        progress = card.progress ?: StudyProgress(itemId = card.item.id),
        reviewedAtEpochMillis = nowEpochMillis,
    )

    suspend fun resetProgress() = withContext(Dispatchers.IO) {
        mutex.withLock {
            val database = progressDatabase.writableDatabase
            database.beginTransaction()
            try {
                database.delete(TABLE_PROGRESS, null, null)
                database.delete(TABLE_DAILY, null, null)
                database.setTransactionSuccessful()
            } finally {
                database.endTransaction()
            }
        }
    }

    suspend fun pruneOrphanedProgress() = withContext(Dispatchers.IO) {
        mutex.withLock {
            val validItemIds = loadItems(StudyContent.ALL)
                .asSequence()
                .map { it.id }
                .toHashSet()
            val orphanedItemIds = loadProgress().keys.filterNot(validItemIds::contains)
            if (orphanedItemIds.isEmpty()) return@withLock

            val database = progressDatabase.writableDatabase
            database.beginTransaction()
            try {
                orphanedItemIds.forEach { itemId ->
                    database.delete(TABLE_PROGRESS, "item_id = ?", arrayOf(itemId))
                }
                database.setTransactionSuccessful()
            } finally {
                database.endTransaction()
            }
        }
    }

    private fun loadItems(content: StudyContent): List<StudyItem> {
        val result = mutableListOf<StudyItem>()
        SQLiteDatabase.openDatabase(
            dictionaryPath,
            null,
            SQLiteDatabase.OPEN_READONLY,
        ).use { database ->
            if (content != StudyContent.PHRASES) {
                val columns = database.tableColumns("dictionary_headwords")
                val frequency = if ("count" in columns) "COALESCE(count, 0)" else "0"
                val variety = if ("variety" in columns) "COALESCE(variety, 0)" else "0"
                database.rawQuery(
                    """
                    SELECT words, display_explanation, COALESCE(display_class, ''),
                           $frequency, $variety
                    FROM dictionary_headwords
                    WHERE TRIM(words) <> '' AND TRIM(COALESCE(display_explanation, '')) <> ''
                    """.trimIndent(),
                    null,
                ).use { cursor ->
                    while (cursor.moveToNext()) {
                        val text = cursor.getString(0).trim()
                        result += StudyItem(
                            id = stableItemId(StudyScope.WORD, text),
                            scope = StudyScope.WORD,
                            text = text,
                            explanation = cursor.getString(1).trim(),
                            wordClass = cursor.getString(2).trim(),
                            frequency = cursor.getInt(3).coerceAtLeast(0),
                            variety = cursor.getInt(4).coerceAtLeast(0),
                        )
                    }
                }
            }
            if (content != StudyContent.WORDS) {
                val columns = database.tableColumns("phrase")
                val frequency = if ("count" in columns) {
                    "CAST(COALESCE(count, 0) AS INTEGER)"
                } else {
                    "0"
                }
                val variety = if ("variety" in columns) {
                    "CAST(COALESCE(variety, 0) AS INTEGER)"
                } else {
                    "0"
                }
                database.rawQuery(
                    """
                    SELECT PHRASE, explanation, $frequency, $variety
                    FROM phrase
                    WHERE TRIM(COALESCE(PHRASE, '')) <> ''
                      AND TRIM(COALESCE(explanation, '')) <> ''
                      AND LOWER(TRIM(PHRASE)) <> 'test test test'
                    """.trimIndent(),
                    null,
                ).use { cursor ->
                    while (cursor.moveToNext()) {
                        val text = cursor.getString(0).trim()
                        result += StudyItem(
                            id = stableItemId(StudyScope.PHRASE, text),
                            scope = StudyScope.PHRASE,
                            text = text,
                            explanation = cursor.getString(1).trim(),
                            frequency = cursor.getInt(2).coerceAtLeast(0),
                            variety = cursor.getInt(3).coerceAtLeast(0),
                        )
                    }
                }
            }
        }
        return mergeStudyItems(result)
    }

    private fun SQLiteDatabase.tableColumns(table: String): Set<String> {
        val quotedTable = table.replace("\"", "\"\"")
        val result = mutableSetOf<String>()
        rawQuery("PRAGMA table_info(\"$quotedTable\")", null).use { cursor ->
            while (cursor.moveToNext()) {
                result += cursor.getString(1).lowercase(Locale.ROOT)
            }
        }
        return result
    }

    private fun loadProgress(): Map<String, StudyProgress> {
        val result = mutableMapOf<String, StudyProgress>()
        progressDatabase.readableDatabase.query(
            TABLE_PROGRESS,
            PROGRESS_COLUMNS,
            null,
            null,
            null,
            null,
            null,
        ).use { cursor ->
            while (cursor.moveToNext()) {
                cursor.toStudyProgress()?.let { result[it.itemId] = it }
            }
        }
        return result
    }

    private fun loadProgress(itemId: String, database: SQLiteDatabase): StudyProgress? =
        database.query(
            TABLE_PROGRESS,
            PROGRESS_COLUMNS,
            "item_id = ?",
            arrayOf(itemId),
            null,
            null,
            null,
            "1",
        ).use { cursor -> if (cursor.moveToFirst()) cursor.toStudyProgress() else null }

    private fun android.database.Cursor.toStudyProgress(): StudyProgress? {
        val phase = runCatching { StudyPhase.valueOf(getString(1)) }.getOrNull() ?: return null
        val rating = getString(10)?.let { value ->
            runCatching { StudyRating.valueOf(value) }.getOrNull()
        }
        return StudyProgress(
            itemId = getString(0),
            phase = phase,
            dueAtEpochMillis = getLong(2),
            intervalDays = getInt(3),
            easeFactor = getDouble(4),
            stepIndex = getInt(5),
            repetitions = getInt(6),
            lapses = getInt(7),
            reviewCount = getInt(8),
            lastReviewedAtEpochMillis = if (isNull(9)) null else getLong(9),
            lastRating = rating,
        )
    }

    private fun saveProgress(progress: StudyProgress, database: SQLiteDatabase) {
        val values = ContentValues().apply {
            put("item_id", progress.itemId)
            put("phase", progress.phase.name)
            put("due_at", progress.dueAtEpochMillis)
            put("interval_days", progress.intervalDays)
            put("ease_factor", progress.easeFactor)
            put("step_index", progress.stepIndex)
            put("repetitions", progress.repetitions)
            put("lapses", progress.lapses)
            put("review_count", progress.reviewCount)
            progress.lastReviewedAtEpochMillis?.let { put("last_reviewed_at", it) }
            progress.lastRating?.let { put("last_rating", it.name) }
        }
        database.insertWithOnConflict(
            TABLE_PROGRESS,
            null,
            values,
            SQLiteDatabase.CONFLICT_REPLACE,
        )
    }

    private fun updateDaily(
        database: SQLiteDatabase,
        day: String,
        remembered: Boolean,
        isNew: Boolean,
    ) {
        val previous = loadDaily(day, database)
        val values = ContentValues().apply {
            put("day", day)
            put("answers", previous.answers + 1)
            put("remembered", previous.remembered + if (remembered) 1 else 0)
            put("new_seen", previous.newSeen + if (isNew) 1 else 0)
        }
        database.insertWithOnConflict(
            TABLE_DAILY,
            null,
            values,
            SQLiteDatabase.CONFLICT_REPLACE,
        )
    }

    private fun loadDaily(day: String): StudyDaily =
        loadDaily(day, progressDatabase.readableDatabase)

    private fun loadDaily(day: String, database: SQLiteDatabase): StudyDaily =
        database.query(
            TABLE_DAILY,
            arrayOf("answers", "remembered", "new_seen"),
            "day = ?",
            arrayOf(day),
            null,
            null,
            null,
            "1",
        ).use { cursor ->
            if (cursor.moveToFirst()) {
                StudyDaily(cursor.getInt(0), cursor.getInt(1), cursor.getInt(2))
            } else {
                StudyDaily()
            }
        }

    private fun calculateStreak(nowEpochMillis: Long): Int {
        val activeDays = mutableSetOf<String>()
        progressDatabase.readableDatabase.query(
            TABLE_DAILY,
            arrayOf("day"),
            "answers > 0",
            null,
            null,
            null,
            null,
        ).use { cursor ->
            while (cursor.moveToNext()) activeDays += cursor.getString(0)
        }
        if (activeDays.isEmpty()) return 0

        val calendar = Calendar.getInstance().apply { timeInMillis = nowEpochMillis }
        if (dayKey(calendar.timeInMillis) !in activeDays) {
            calendar.add(Calendar.DAY_OF_YEAR, -1)
        }
        var streak = 0
        while (dayKey(calendar.timeInMillis) in activeDays) {
            streak += 1
            calendar.add(Calendar.DAY_OF_YEAR, -1)
        }
        return streak
    }

    private fun dayKey(epochMillis: Long): String =
        SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date(epochMillis))

    private inline fun <reified T : Enum<T>> preferenceEnum(key: String, fallback: T): T {
        val stored = preferences.getString(key, fallback.name).orEmpty()
        return enumValues<T>().firstOrNull { it.name == stored } ?: fallback
    }

    private data class StudyDaily(
        val answers: Int = 0,
        val remembered: Int = 0,
        val newSeen: Int = 0,
    )

    private class StudyProgressDatabase(context: Context) :
        SQLiteOpenHelper(context, DATABASE_NAME, null, DATABASE_VERSION) {
        override fun onCreate(database: SQLiteDatabase) {
            database.execSQL(
                """
                CREATE TABLE $TABLE_PROGRESS (
                    item_id TEXT PRIMARY KEY NOT NULL,
                    phase TEXT NOT NULL,
                    due_at INTEGER NOT NULL,
                    interval_days INTEGER NOT NULL,
                    ease_factor REAL NOT NULL,
                    step_index INTEGER NOT NULL,
                    repetitions INTEGER NOT NULL,
                    lapses INTEGER NOT NULL,
                    review_count INTEGER NOT NULL,
                    last_reviewed_at INTEGER,
                    last_rating TEXT
                )
                """.trimIndent(),
            )
            database.execSQL(
                """
                CREATE TABLE $TABLE_DAILY (
                    day TEXT PRIMARY KEY NOT NULL,
                    answers INTEGER NOT NULL,
                    remembered INTEGER NOT NULL,
                    new_seen INTEGER NOT NULL
                )
                """.trimIndent(),
            )
            database.execSQL(
                "CREATE INDEX idx_study_progress_due ON $TABLE_PROGRESS(due_at)",
            )
        }

        override fun onUpgrade(database: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit
    }

    private companion object {
        const val STUDY_PREFERENCES = "alician_study"
        const val SETTING_ORDER = "order"
        const val SETTING_CONTENT = "content"
        const val SETTING_DAILY_NEW = "daily_new"
        const val SETTING_ALPHABET_COMPLETE = "alphabet_complete"
        const val DEFAULT_DAILY_NEW = 10
        const val MIN_DAILY_NEW = 5
        const val MAX_DAILY_NEW = 30
        const val MATURE_INTERVAL_DAYS = 21

        const val DATABASE_NAME = "study_progress.db"
        const val DATABASE_VERSION = 1
        const val TABLE_PROGRESS = "study_progress"
        const val TABLE_DAILY = "study_daily"
        val PROGRESS_COLUMNS = arrayOf(
            "item_id",
            "phase",
            "due_at",
            "interval_days",
            "ease_factor",
            "step_index",
            "repetitions",
            "lapses",
            "review_count",
            "last_reviewed_at",
            "last_rating",
        )
    }
}
