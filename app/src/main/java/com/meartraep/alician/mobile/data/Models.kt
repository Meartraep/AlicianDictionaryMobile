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

data class DictionarySense(
    val id: Int,
    val explanation: String,
    val wordClass: String,
    val englishGloss: String,
    val japaneseGloss: String,
)

data class DictionaryEntry(
    val word: String,
    val explanation: String,
    val wordClass: String,
    val kind: String,
    val count: Int,
    val variety: Int,
    val englishGloss: String = "",
    val japaneseGloss: String = "",
    val headwordId: Int = 0,
    val album: String = "",
    val songTitle: String = "",
    val senses: List<DictionarySense> = emptyList(),
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

data class LyricLineTranslation(
    val line: String,
    val poetic: String,
    val english: String = "",
    val japanese: String = "",
    val korean: String = "",
)

data class LyricExample(
    val id: Int,
    val paragraph: String,
    val title: String,
    val album: String,
    val lyric: String,
    val start: Int,
    val end: Int,
    val poeticTranslation: String = "",
    val englishTranslation: String = "",
    val japaneseTranslation: String = "",
    val koreanTranslation: String = "",
    val lyricTranslations: List<LyricLineTranslation> = emptyList(),
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
)

data class TextRange(val start: Int, val end: Int)

data class WritingResult(
    val sourceText: String,
    val unknownCount: Int,
    val unknownRanges: List<TextRange>,
    val uncertainRanges: List<TextRange>,
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

/** One table shown in the dictionary's data workspace. */
data class DataTableInfo(
    val name: String,
    val label: String,
    val editable: Boolean = false,
    val note: String = "",
    val display: List<String> = emptyList(),
)

/** Curated table group (core / lyric / semantic / system / legacy). */
data class DataTableGroup(
    val group: String,
    val title: String,
    val note: String = "",
    val tables: List<DataTableInfo> = emptyList(),
)

/** One server-side page of a table plus the metadata the UI needs. */
data class DataTablePage(
    val table: String,
    val label: String,
    val group: String,
    val editable: Boolean,
    val display: List<String>,
    val fields: List<String>,
    val rows: List<Map<String, String>>,
    val total: Int,
    val offset: Int,
    val limit: Int,
) {
    val pageIndex: Int get() = if (limit <= 0) 0 else offset / limit
    val pageCount: Int get() = if (limit <= 0) 0 else (total + limit - 1) / limit
    val canGoPrevious: Boolean get() = offset > 0
    val canGoNext: Boolean get() = offset + limit < total
}

data class GlobalMatch(
    val table: String,
    val id: Long,
    val field: String,
    val value: String,
)

/** Reference (foreign-key) target shown next to an editable field. */
data class DataReference(
    val table: String,
    val label: String,
    val column: String,
)

/** One column of a curated editor form. */
data class DataFieldMeta(
    val name: String,
    val label: String,
    val type: String = "",
    val notnull: Boolean = false,
    val maxLength: Int = 0,
    val required: Boolean = false,
    val primaryKey: Boolean = false,
    val multiline: Boolean = false,
    val hasDefault: Boolean = false,
    val defaultValue: String = "",
    val reference: DataReference? = null,
)

/** A child table that is removed together with the edited row. */
data class DataCascadeInfo(
    val table: String,
    val label: String,
    val column: String,
)

/** Server-described form for one table; the UI never hard-codes table rules. */
data class DataFormMeta(
    val table: String,
    val label: String,
    val group: String,
    val note: String,
    val editable: Boolean,
    val keyColumn: String,
    val display: List<String>,
    val fields: List<DataFieldMeta>,
    val cascade: List<DataCascadeInfo>,
) {
    fun field(name: String): DataFieldMeta? = fields.firstOrNull { it.name == name }
}

/** One table affected by a delete (the deleted table itself excluded). */
data class DataDeleteChild(
    val table: String,
    val label: String,
    val group: String,
    val count: Int,
)

/** Exact impact of one delete, computed by the backend. */
data class DataDeletePreview(
    val table: String,
    val label: String,
    val key: Long,
    val summary: String,
    val deletedSelf: Int,
    val children: List<DataDeleteChild>,
    val totalRemoved: Int,
)

/** Candidate value for a reference field. */
data class DataReferenceOption(
    val value: String,
    val label: String,
)

/** Result of a write, consumed by the dialog that triggered it. */
data class DataMutation(
    val token: Long,
    val ok: Boolean,
    val message: String,
    val key: Long? = null,
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

/**
 * Published "database-manifest.json" describing the newest database release.
 *
 * The bundled Lite database carries a matching revision in its own
 * `database_metadata` table, so the app can decide whether the published one is
 * newer without downloading the database itself.
 */
data class DatabaseUpdateManifest(
    val dbVersion: Int,
    val publishedAt: String = "",
    val notes: String = "",
    val size: Long = 0L,
    val sha1: String = "",
    val url: String = "",
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

/** One orphan-row check reported by the read-only database diagnosis. */
data class DataOrphan(
    val table: String,
    val label: String,
    val count: Int,
)

/** Row count of one table in the database diagnosis. */
data class DataDiagnosisTable(
    val name: String,
    val rows: Int,
    val group: String,
)

/** Full integrity report behind 维护 → 数据库诊断 (read-only). */
data class DataDiagnosis(
    val integrity: String,
    val foreignKeyViolations: Int,
    val orphans: List<DataOrphan>,
    val tables: List<DataDiagnosisTable>,
    val localEdits: Int,
    val pragmas: Map<String, String>,
)

/** Preview payload of one global replace (editable tables only). */
data class ReplacePreview(
    val keyword: String,
    val replacement: String,
    val matches: List<GlobalMatch>,
)

/** One recovery point (backup file) shown in the database governance screen. */
data class BackupEntry(
    val path: String,
    val name: String,
    val dbVersion: Int,
    val size: Long,
    val sha1: String,
    val createdAt: String,
    val reason: String,
)

/** Read-only identity of the installed database plus local-edit/backup counters. */
data class GovIdentity(
    val dbVersion: Int,
    val publishedAt: String,
    val notes: String,
    val format: String,
    val sha256: String,
    val size: Long,
    val modified: String,
    val wordCount: Int,
    val songCount: Int,
    val tableCount: Int,
    val localEdits: Int,
    val localModified: Boolean,
    val backupCount: Int,
    val latestBackup: BackupEntry?,
)
