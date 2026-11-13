package com.meartraep.alician.mobile.data

import android.app.Application
import android.content.SharedPreferences
import android.database.sqlite.SQLiteDatabase
import android.net.Uri
import android.util.Log
import androidx.core.content.edit
import androidx.core.database.sqlite.transaction
import com.meartraep.alician.mobile.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

internal class DatabaseStorageAndUpdates(
    private val application: Application,
    private val dataDirectory: File,
    private val databaseFile: File,
    private val preferences: SharedPreferences,
) {
    fun ensureBundledFiles() {
        if (!databaseFile.exists()) {
            application.assets.open("translated.db").use { input ->
                databaseFile.outputStream().use(input::copyTo)
            }
            preferences.edit {
                putString("database_asset_version", BuildConfig.DATABASE_ASSET_VERSION)
            }
        } else {
            updateBundledSemanticAliases()
        }
        val config = File(dataDirectory, "word_checker_config.json")
        if (!config.exists()) {
            application.assets.open("word_checker_config.json").use { input ->
                config.outputStream().use(input::copyTo)
            }
        }
    }

    private fun updateBundledSemanticAliases() {
        val installedVersion = preferences.getString("database_asset_version", null)
        if (installedVersion == BuildConfig.DATABASE_ASSET_VERSION) return

        try {
            val bundledDatabase = File(application.cacheDir, "bundled_semantic_aliases.db")
            application.assets.open("translated.db").use { input ->
                bundledDatabase.outputStream().use(input::copyTo)
            }
            val updated = try {
                copySemanticAliasesWhenDictionaryMatches(bundledDatabase)
            } finally {
                bundledDatabase.delete()
            }
            if (updated) {
                preferences.edit {
                    putString("database_asset_version", BuildConfig.DATABASE_ASSET_VERSION)
                }
            } else {
                Log.w(
                    "AlicianRepository",
                    "Bundled semantic aliases were not applied because the dictionary data differs.",
                )
            }
        } catch (error: Exception) {
            Log.w(
                "AlicianRepository",
                "Unable to update bundled semantic aliases; keeping the user's database.",
                error,
            )
        }
    }

    private fun copySemanticAliasesWhenDictionaryMatches(bundledDatabase: File): Boolean {
        SQLiteDatabase.openDatabase(
            databaseFile.absolutePath,
            null,
            SQLiteDatabase.OPEN_READWRITE,
        ).use { database ->
            var attached = false
            try {
                database.execSQL(
                    "ATTACH DATABASE ? AS bundled",
                    arrayOf(bundledDatabase.absolutePath),
                )
                attached = true
                if (!database.hasTable("bundled", "dictionary_semantic_aliases")) return false
                if (!database.hasTable("bundled", "semantic_alias_metadata")) return false
                if (!database.semanticAliasSensesMatch()) return false

                database.transaction {
                    execSQL("DROP TABLE IF EXISTS dictionary_semantic_aliases")
                    execSQL(
                        """
                        CREATE TABLE dictionary_semantic_aliases (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            sense_id INTEGER NOT NULL,
                            alias TEXT NOT NULL,
                            similarity REAL NOT NULL,
                            rank INTEGER NOT NULL,
                            source_frequency INTEGER NOT NULL,
                            source_pos TEXT NOT NULL,
                            model_name TEXT NOT NULL,
                            model_revision TEXT NOT NULL,
                            generated_at TEXT NOT NULL,
                            generation_method TEXT NOT NULL,
                            UNIQUE (alias, sense_id),
                            FOREIGN KEY (sense_id) REFERENCES dictionary(id) ON DELETE CASCADE
                        )
                        """.trimIndent(),
                    )
                    execSQL(
                        """
                        INSERT INTO dictionary_semantic_aliases (
                            id,
                            sense_id,
                            alias,
                            similarity,
                            rank,
                            source_frequency,
                            source_pos,
                            model_name,
                            model_revision,
                            generated_at,
                            generation_method
                        )
                        SELECT
                            id,
                            sense_id,
                            alias,
                            similarity,
                            rank,
                            source_frequency,
                            source_pos,
                            model_name,
                            model_revision,
                            generated_at,
                            generation_method
                        FROM bundled.dictionary_semantic_aliases
                        """.trimIndent(),
                    )
                    execSQL(
                        """
                        CREATE INDEX IF NOT EXISTS idx_semantic_aliases_alias
                        ON dictionary_semantic_aliases(alias)
                        """.trimIndent(),
                    )
                    execSQL(
                        """
                        CREATE INDEX IF NOT EXISTS idx_semantic_aliases_sense
                        ON dictionary_semantic_aliases(sense_id, rank)
                        """.trimIndent(),
                    )
                    execSQL("DROP TABLE IF EXISTS semantic_alias_metadata")
                    execSQL(
                        """
                        CREATE TABLE semantic_alias_metadata (
                            "key" TEXT PRIMARY KEY,
                            value TEXT NOT NULL
                        )
                        """.trimIndent(),
                    )
                    execSQL(
                        """
                        INSERT INTO semantic_alias_metadata ("key", value)
                        SELECT "key", value FROM bundled.semantic_alias_metadata
                        """.trimIndent(),
                    )
                    // The previous release stored nearest existing definitions,
                    // not actual aliases. Keeping those tables would be both
                    // misleading in the database manager and wasted space.
                    execSQL("DROP TABLE IF EXISTS dictionary_sense_expansions")
                    execSQL("DROP TABLE IF EXISTS semantic_expansion_metadata")
                }
                return true
            } finally {
                if (attached) {
                    database.execSQL("DETACH DATABASE bundled")
                }
            }
        }
    }

    private fun SQLiteDatabase.hasTable(schema: String, table: String): Boolean =
        rawQuery(
            "SELECT 1 FROM $schema.sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            arrayOf(table),
        ).use { it.moveToFirst() }

    private fun SQLiteDatabase.semanticAliasSensesMatch(): Boolean {
        return rawQuery(
            """
            SELECT NOT EXISTS(
                SELECT 1
                FROM bundled.dictionary_semantic_aliases AS alias
                JOIN bundled.dictionary AS bundled_sense
                    ON bundled_sense.id = alias.sense_id
                LEFT JOIN main.dictionary AS installed_sense
                    ON installed_sense.id = bundled_sense.id
                WHERE installed_sense.id IS NULL
                   OR installed_sense.headword_id IS NOT bundled_sense.headword_id
                   OR installed_sense.words IS NOT bundled_sense.words
                   OR installed_sense.explanation IS NOT bundled_sense.explanation
                   OR installed_sense."class" IS NOT bundled_sense."class"
                   OR installed_sense.sense_order IS NOT bundled_sense.sense_order
            )
            """.trimIndent(),
            null,
        ).use { cursor -> cursor.moveToFirst() && (cursor.getInt(0) != 0) }
    }

    suspend fun copyFileTo(file: File, uri: Uri): Long = withContext(Dispatchers.IO) {
        application.contentResolver.openOutputStream(uri, "w")!!.use { output ->
            file.inputStream().use { it.copyTo(output) }
        }
    }

    suspend fun copyUriToTempDatabase(uri: Uri): File = withContext(Dispatchers.IO) {
        val temporary = File(application.cacheDir, "database_import.db")
        application.contentResolver.openInputStream(uri)!!.use { input ->
            temporary.outputStream().use(input::copyTo)
        }
        temporary
    }

    suspend fun copyBundledDatabaseToTemp(): File = withContext(Dispatchers.IO) {
        val temporary = File(application.cacheDir, "bundled_translated.db")
        application.assets.open("translated.db").use { input ->
            temporary.outputStream().use(input::copyTo)
        }
        temporary
    }

    suspend fun localDatabaseIdentity(): Pair<Long, String> = withContext(Dispatchers.IO) {
        databaseFile.length() to (if (databaseFile.isFile) sha1Of(databaseFile) else "")
    }

    fun publicationScratchFile(): File =
        File(application.cacheDir, "publication").apply { mkdirs() }

    /**
     * Fetches the small published manifest; the database itself is only downloaded
     * on demand. Returns null when the repository simply does not publish one yet.
     */
    suspend fun fetchDatabaseUpdateManifest(): DatabaseUpdateManifest? = withContext(Dispatchers.IO) {
        val connection = URL(DATABASE_MANIFEST_URL).openConnection() as HttpURLConnection
        connection.requestMethod = "GET"
        connection.connectTimeout = 8_000
        connection.readTimeout = 8_000
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("Cache-Control", "no-cache")
        connection.setRequestProperty("User-Agent", "AlicianDictionaryMobile/${BuildConfig.VERSION_NAME}")
        try {
            when (val responseCode = connection.responseCode) {
                HttpURLConnection.HTTP_NOT_FOUND -> return@withContext null
                HttpURLConnection.HTTP_OK -> Unit
                else -> throw IllegalStateException("数据库更新清单获取失败（HTTP $responseCode）")
            }
            val json = JSONObject(connection.inputStream.bufferedReader().use { it.readText() })
            DatabaseUpdateManifest(
                dbVersion = json.optInt("db_version", 0),
                publishedAt = json.optString("published_at"),
                notes = json.optString("notes"),
                size = json.optLong("size", 0L),
                sha1 = json.optString("sha1").lowercase(),
                url = json.optString("url").ifBlank { DATABASE_RAW_URL },
            )
        } finally {
            connection.disconnect()
        }
    }

    /** Downloads the published database and verifies size and SHA-1 before it is applied. */
    suspend fun downloadDatabaseUpdate(manifest: DatabaseUpdateManifest): File =
        withContext(Dispatchers.IO) {
            val target = File(application.cacheDir, "database_update.db")
            if (target.exists() && !target.delete()) {
                throw IllegalStateException("无法清理旧的下载缓存。")
            }
            val connection = URL(manifest.url).openConnection() as HttpURLConnection
            connection.connectTimeout = 15_000
            connection.readTimeout = 120_000
            connection.setRequestProperty("User-Agent", "AlicianDictionaryMobile/${BuildConfig.VERSION_NAME}")
            try {
                val responseCode = connection.responseCode
                if (responseCode != HttpURLConnection.HTTP_OK) {
                    throw IllegalStateException("数据库下载失败（HTTP $responseCode）")
                }
                connection.inputStream.use { input ->
                    target.outputStream().use(input::copyTo)
                }
            } finally {
                connection.disconnect()
            }
            if ((manifest.size > 0L) && (target.length() != manifest.size)) {
                val actual = target.length()
                target.delete()
                throw IllegalStateException("数据库下载不完整（$actual / ${manifest.size} 字节）")
            }
            if (manifest.sha1.isNotBlank() && (sha1Of(target) != manifest.sha1)) {
                target.delete()
                throw IllegalStateException("数据库校验失败，下载内容与发布清单不一致。")
            }
            target
        }

    suspend fun checkAppUpdate(): AppUpdateInfo = withContext(Dispatchers.IO) {
        val currentVersion = BuildConfig.VERSION_NAME
        val connection = URL(APP_RELEASE_API_URL).openConnection() as HttpURLConnection
        connection.requestMethod = "GET"
        connection.connectTimeout = 15_000
        connection.readTimeout = 15_000
        connection.setRequestProperty("Accept", "application/vnd.github+json")
        connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
        connection.setRequestProperty("User-Agent", "AlicianDictionaryMobile/$currentVersion")
        try {
            when (val responseCode = connection.responseCode) {
                HttpURLConnection.HTTP_OK -> {
                    val json = connection.inputStream.bufferedReader().use {
                        JSONObject(it.readText())
                    }
                    val latestVersion = json.optString("tag_name").trim()
                    val updateAvailable = isVersionNewer(latestVersion, currentVersion)
                    AppUpdateInfo(
                        currentVersion = currentVersion,
                        latestVersion = latestVersion,
                        releaseName = json.optString("name").ifBlank { latestVersion },
                        releaseUrl = json.optString("html_url").ifBlank { APP_RELEASES_URL },
                        publishedAt = json.optString("published_at"),
                        updateAvailable = updateAvailable,
                        hasRelease = latestVersion.isNotBlank(),
                        message = if (updateAvailable) {
                            "发现新版本 $latestVersion"
                        } else {
                            "当前已是最新版本"
                        },
                    )
                }
                HttpURLConnection.HTTP_NOT_FOUND -> AppUpdateInfo(
                    currentVersion = currentVersion,
                    latestVersion = "",
                    releaseName = "",
                    releaseUrl = APP_RELEASES_URL,
                    publishedAt = "",
                    updateAvailable = false,
                    hasRelease = false,
                    message = "GitHub 仓库尚未公开，或尚未发布正式 Release。",
                )
                else -> {
                    val detail = connection.errorStream?.bufferedReader()?.use {
                        runCatching { JSONObject(it.readText()).optString("message") }.getOrNull()
                    }.orEmpty()
                    throw IllegalStateException(
                        "GitHub 更新检查失败（HTTP $responseCode）" +
                            if (detail.isBlank()) "" else "：$detail",
                    )
                }
            }
        } finally {
            connection.disconnect()
        }
    }

    companion object {
        private const val DATABASE_MANIFEST_URL =
            "https://raw.githubusercontent.com/Meartraep/AlicianDictionaryMobile/" +
                "main/database-manifest.json"
        const val DATABASE_RAW_URL =
            "https://raw.githubusercontent.com/Meartraep/AlicianDictionaryMobile/" +
                "main/app/src/main/assets/translated.db"
        private const val APP_RELEASE_API_URL =
            "https://api.github.com/repos/Meartraep/AlicianDictionaryMobile/releases/latest"
        private const val APP_RELEASES_URL =
            "https://github.com/Meartraep/AlicianDictionaryMobile/releases"
    }
}

private fun sha1Of(file: File): String {
    val digest = MessageDigest.getInstance("SHA-1")
    file.inputStream().use { stream ->
        val buffer = ByteArray(64 * 1024)
        while (true) {
            val read = stream.read(buffer)
            if (read <= 0) break
            digest.update(buffer, 0, read)
        }
    }
    return digest.digest().joinToString("") { byte -> "%02x".format(byte) }
}

internal fun isVersionNewer(candidate: String, current: String): Boolean {
    val candidateParts = numericVersionParts(candidate)
    val currentParts = numericVersionParts(current)
    if (candidateParts.isEmpty()) return false
    val size = maxOf(candidateParts.size, currentParts.size)
    repeat(size) { index ->
        val candidatePart = candidateParts.getOrElse(index) { 0 }
        val currentPart = currentParts.getOrElse(index) { 0 }
        if (candidatePart != currentPart) return candidatePart > currentPart
    }
    return false
}

private fun numericVersionParts(value: String): List<Int> =
    Regex("""\d+""").findAll(value)
        .mapNotNull { it.value.toIntOrNull() }
        .toList()
