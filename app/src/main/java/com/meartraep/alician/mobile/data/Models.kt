package com.meartraep.alician.mobile.data

data class DatabaseInfo(
    val path: String = "",
    val size: Long = 0,
    val modified: String = "",
    val sha256: String = "",
    val tableCount: Int = 0,
    val wordCount: Int = 0,
    val songCount: Int = 0,
)

data class AppUpdateInfo(
    val currentVersion: String,
    val latestVersion: String,
    val releaseName: String,
    val releaseUrl: String,
    val publishedAt: String,
    val updateAvailable: Boolean,
    val hasRelease: Boolean,
    val message: String,
)

enum class ThemeMode {
    SYSTEM,
    LIGHT,
    DARK,
}

enum class ColorPalette {
    ALICIAN,
    OCEAN,
    FOREST,
    ROSE,
}

enum class ContrastLevel {
    STANDARD,
    MEDIUM,
    HIGH,
}

enum class ShapeStyle {
    COMPACT,
    ROUNDED,
    EXPRESSIVE,
}

enum class TypographySize {
    COMPACT,
    STANDARD,
    LARGE,
}

data class UiSettings(
    val themeMode: ThemeMode = ThemeMode.SYSTEM,
    val dynamicColors: Boolean = true,
    val colorPalette: ColorPalette = ColorPalette.ALICIAN,
    val contrastLevel: ContrastLevel = ContrastLevel.STANDARD,
    val shapeStyle: ShapeStyle = ShapeStyle.ROUNDED,
    val typographySize: TypographySize = TypographySize.STANDARD,
    val amoledBlack: Boolean = false,
    val alicianFont: Boolean = false,
)

data class DictionaryEntry(
    val word: String,
    val explanation: String,
    val wordClass: String,
    val kind: String,
    val count: Int,
    val variety: Int,
)

data class DictionarySection(
    val title: String,
    val kind: String,
    val entries: List<DictionaryEntry>,
)

data class Suggestion(
    val word: String,
    val explanation: String,
    val score: Double,
)

data class DictionaryResult(
    val query: String,
    val exactMatch: Boolean,
    val isPhrase: Boolean,
    val sections: List<DictionarySection>,
    val suggestions: List<Suggestion>,
    val history: List<String>,
    val message: String,
)

data class LyricExample(
    val id: Int,
    val paragraph: String,
    val title: String,
    val album: String,
    val lyric: String,
    val start: Int,
    val end: Int,
)

data class SongExampleStats(
    val album: String,
    val title: String,
    val before: Int,
    val after: Int,
)

data class ExampleResult(
    val word: String,
    val examples: List<LyricExample>,
    val positionFilter: String,
    val songStats: List<SongExampleStats>,
    val totalBefore: Int,
    val totalAfter: Int,
    val deduplicationRate: Double,
    val message: String,
)

data class WritingIssue(
    val key: String,
    val display: String,
    val type: String,
    val position: Int,
    val reasons: List<String>,
    val count: Int,
    val variety: Int,
)

data class TextRange(val start: Int, val end: Int)

data class WritingResult(
    val sourceText: String,
    val unknownCount: Int,
    val unknownRanges: List<TextRange>,
    val lowStatRanges: List<TextRange>,
    val issues: List<WritingIssue>,
    val status: String,
)

data class WritingSettings(
    val strictCase: Boolean = true,
    val maxUndoSteps: Int = 100,
    val excludedWords: List<String> = emptyList(),
    val dictionaryFormatEnabled: Boolean = false,
    val dictionaryFormatSeparators: List<String> = listOf(":", "："),
)

data class LookupExplanation(
    val word: String,
    val partOfSpeech: String,
    val explanation: String,
)

data class SimilarWord(
    val word: String,
    val similarWord: String,
    val partOfSpeech: String,
    val explanation: String,
    val score: Double,
)

data class LookupResult(
    val explanations: List<LookupExplanation>,
    val similarWords: List<SimilarWord>,
    val message: String,
)

data class TranslationAlternative(
    val target: String,
    val explanation: String,
    val wordClass: String,
    val score: Double,
)

data class TranslationToken(
    val source: String,
    val target: String,
    val status: String,
    val method: String,
    val confidence: Double,
    val explanation: String,
    val wordClass: String,
    val count: Int,
    val variety: Int,
    val alternatives: List<TranslationAlternative>,
    val note: String,
    val resolvedTarget: String = "",
    val omitFromResult: Boolean = false,
    val templateArguments: List<String> = emptyList(),
)

data class TranslationResult(
    val direction: String,
    val sourceText: String,
    val resultText: String,
    val tokens: List<TranslationToken>,
    val exact: Int,
    val approximate: Int,
    val unknown: Int,
    val semanticExpansionsEnabled: Boolean = false,
    val semanticExpansionsAvailable: Boolean = false,
    val semanticExpansionCount: Int = 0,
    val message: String,
)

data class DbTablePage(
    val table: String,
    val fields: List<String>,
    val rows: List<Map<String, String>>,
    val total: Int,
    val offset: Int,
    val limit: Int,
)

data class GlobalMatch(
    val table: String,
    val id: Long,
    val field: String,
    val value: String,
)

data class RemoteComparison(
    val upToDate: Boolean,
    val message: String,
    val localSha1: String,
    val remoteSha1: String,
    val localCounts: Map<String, Int>,
    val remoteCounts: Map<String, Int>,
    val diff: DatabaseDiff = DatabaseDiff(),
)

data class DatabaseDiff(
    val totalAdded: Int = 0,
    val totalRemoved: Int = 0,
    val totalModified: Int = 0,
    val totalFieldChanges: Int = 0,
    val tables: List<DatabaseTableDiff> = emptyList(),
)

data class DatabaseTableDiff(
    val table: String,
    val localRows: Int,
    val remoteRows: Int,
    val added: Int,
    val removed: Int,
    val modified: Int,
    val fieldChanges: Int,
    val addedRows: List<DatabaseRowDiff>,
    val removedRows: List<DatabaseRowDiff>,
    val fieldDiffs: List<DatabaseFieldDiff>,
    val truncatedAdded: Boolean,
    val truncatedRemoved: Boolean,
    val truncatedModified: Boolean,
)

data class DatabaseRowDiff(
    val id: String,
    val values: Map<String, String>,
)

data class DatabaseFieldDiff(
    val rowId: String,
    val column: String,
    val localValue: String,
    val remoteValue: String,
)
