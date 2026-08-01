package com.meartraep.alician.mobile.data

/** The dictionary source represented by one study card. */
enum class StudyScope {
    WORD,
    PHRASE,
}

/** Which dictionary sources are included in a study session. */
enum class StudyContent {
    ALL,
    WORDS,
    PHRASES,
}

/** Ordering used only when introducing unseen cards. Due reviews always come first. */
enum class StudyOrder {
    FREQUENCY,
    ALPHABETICAL,
    RANDOM,
}

enum class StudyPhase {
    LEARNING,
    REVIEW,
    RELEARNING,
}

enum class StudyRating {
    AGAIN,
    HARD,
    GOOD,
    EASY,
}

data class StudySettings(
    val order: StudyOrder = StudyOrder.FREQUENCY,
    val content: StudyContent = StudyContent.ALL,
    val dailyNewLimit: Int = 10,
    val alphabetCompleted: Boolean = false,
)

/**
 * Dictionary content shown by a study card.
 *
 * [id] must be stable across dictionary replacements. A scope-prefixed, NFC-normalized,
 * case-insensitive text key is preferable to a row id from the replaceable dictionary database.
 */
data class StudyItem(
    val id: String,
    val scope: StudyScope,
    val text: String,
    val explanation: String,
    val wordClass: String = "",
    val frequency: Int = 0,
    val variety: Int = 0,
)

/** Persisted scheduling state for one [StudyItem]. */
data class StudyProgress(
    val itemId: String,
    val phase: StudyPhase = StudyPhase.LEARNING,
    val dueAtEpochMillis: Long = 0L,
    val intervalDays: Int = 0,
    val easeFactor: Double = 2.5,
    val stepIndex: Int = 0,
    val repetitions: Int = 0,
    val lapses: Int = 0,
    val reviewCount: Int = 0,
    val lastReviewedAtEpochMillis: Long? = null,
    val lastRating: StudyRating? = null,
)

/** Read-only timing information used to label the four answer buttons. */
data class StudyRatingPreview(
    val rating: StudyRating,
    val nextPhase: StudyPhase,
    val dueAtEpochMillis: Long,
    val intervalMillis: Long,
    val intervalDays: Int,
)
