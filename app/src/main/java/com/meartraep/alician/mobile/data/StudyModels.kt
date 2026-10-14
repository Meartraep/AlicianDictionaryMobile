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

/**
 * How the learner reads Alician words.
 *
 * [ALICIAN] starts with the glyph primer and its recognition quiz. [LATIN] reads the plain
 * Latin transcription and never forces the original glyphs.
 */
enum class StudyScript {
    ALICIAN,
    LATIN,
}

/** The screen the study tab must show before the deck overview becomes reachable. */
enum class StudyEntry {
    /** Nothing is chosen yet: ask which script to learn. */
    SCRIPT_CHOICE,

    /** The learner picked the original glyphs but has not passed the recognition quiz. */
    ALPHABET_PRIMER,

    /** The deck overview; only [StudyScript.LATIN] reaches it without any glyph training. */
    OVERVIEW,
}

data class StudySettings(
    val order: StudyOrder = StudyOrder.FREQUENCY,
    val content: StudyContent = StudyContent.ALL,
    val dailyNewLimit: Int = 10,
    /** Null until the learner answers the first-run script question. */
    val script: StudyScript? = null,
    val alphabetCompleted: Boolean = false,
)

/**
 * Resolves what the study tab shows. Choosing [StudyScript.LATIN] skips the glyph primer and
 * its quiz entirely, so the study flow starts right away.
 */
fun studyEntryFor(settings: StudySettings): StudyEntry = when {
    settings.script == null -> StudyEntry.SCRIPT_CHOICE
    settings.script == StudyScript.ALICIAN && !settings.alphabetCompleted ->
        StudyEntry.ALPHABET_PRIMER
    else -> StudyEntry.OVERVIEW
}

/** True when study cards lead with the Alician glyph font instead of the Latin transcription. */
val StudySettings.leadsWithAlicianGlyphs: Boolean
    get() = script == StudyScript.ALICIAN

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
