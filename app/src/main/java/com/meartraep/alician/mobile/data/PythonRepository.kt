package com.meartraep.alician.mobile.data

import android.app.Application
import android.net.Uri
import androidx.core.content.edit
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

class PythonRepository(private val application: Application) {
    private val dataDirectory = application.filesDir
    private val databaseFile = File(dataDirectory, "translated.db")
    private val preferences =
        application.getSharedPreferences("alician_mobile", Application.MODE_PRIVATE)
    private val storageAndUpdates = DatabaseStorageAndUpdates(
        application = application,
        dataDirectory = dataDirectory,
        databaseFile = databaseFile,
        preferences = preferences,
    )
    private var bridgeReady = false

    val databasePath: String get() = databaseFile.absolutePath
    val alicianFontEnabled: Boolean
        get() = preferences.getBoolean("alician_font", false)
    val dynamicColorsEnabled: Boolean
        get() = preferences.getBoolean("dynamic_colors", true)
    val semanticExpansionsEnabled: Boolean
        get() = preferences.getBoolean("semantic_expansions_enabled", true)

    /** Whether the app checks the published database manifest on every cold start. */
    val autoDatabaseUpdateCheck: Boolean
        get() = preferences.getBoolean("auto_database_update_check", true)

    /** Revision the user deferred with "later"; nothing is deferred by default. */
    val dismissedDatabaseVersion: Int
        get() = preferences.getInt(
            "dismissed_database_version",
            DatabaseUpdateLogic.NO_DISMISSED_VERSION,
        )

    /** Wall clock of the last completed check, or 0 when never checked. */
    val lastDatabaseCheckAt: Long
        get() = preferences.getLong("last_database_check_at", 0L)
    val uiSettings: UiSettings
        get() = UiSettings(
            themeMode = preferenceEnum("theme_mode", ThemeMode.SYSTEM),
            dynamicColors = dynamicColorsEnabled,
            colorPalette = preferenceEnum("color_palette", ColorPalette.ALICIAN),
            contrastLevel = preferenceEnum("contrast_level", ContrastLevel.STANDARD),
            shapeStyle = preferenceEnum("shape_style", ShapeStyle.ROUNDED),
            typographySize = preferenceEnum("typography_size", TypographySize.STANDARD),
            amoledBlack = preferences.getBoolean("amoled_black", false),
            alicianFont = alicianFontEnabled,
        )

    suspend fun initialize(): JSONObject = withContext(Dispatchers.IO) {
        storageAndUpdates.ensureBundledFiles()
        if (!Python.isStarted()) {
            Python.start(AndroidPlatform(application))
        }
        val result = JSONObject(
            Python.getInstance().getModule("mobile_bridge")
                .callAttr("initialize", databaseFile.absolutePath, dataDirectory.absolutePath)
                .toString(),
        )
        result.requireOk()
        bridgeReady = true
        result
    }

    private suspend fun invoke(method: String, payload: JSONObject = JSONObject()): JSONObject =
        withContext(Dispatchers.IO) {
            check(bridgeReady) { "Python bridge is not ready" }
            val text = Python.getInstance().getModule("mobile_bridge")
                .callAttr("invoke", method, payload.toString())
                .toString()
            JSONObject(text).also { it.requireOk() }
        }

    suspend fun dictionarySearch(
        query: String,
        exact: Boolean,
        position: String,
        recordHistory: Boolean = true,
    ): DictionaryResult {
        val json = invoke(
            "dictionary_search",
            JSONObject()
                .put("query", query)
                .put("exact", exact)
                .put("position", position)
                .put("record_history", recordHistory),
        )
        return json.toDictionaryResult()
    }

    suspend fun dictionaryExamples(word: String, position: String): ExampleResult {
        val json = invoke(
            "dictionary_examples",
            JSONObject().put("word", word).put("position", position),
        )
        return json.toExampleResult()
    }

    suspend fun dictionarySongLyrics(title: String, album: String): ExampleResult =
        invoke("dictionary_song_lyrics", JSONObject().put("title", title).put("album", album))
            .toExampleResult()

    suspend fun updateDictionaryEntry(
        headwordId: Int,
        originalWord: String,
        word: String,
        displayExplanation: String,
        senses: List<DictionarySense>,
    ): String {
        val sensesJson = dictionarySensesJson(senses, includeId = true)
        return invoke(
            "dictionary_update_word",
            JSONObject()
                .put("headword_id", headwordId)
                .put("original_word", originalWord)
                .put("word", word)
                .put("display_explanation", displayExplanation)
                .put("senses", sensesJson),
        ).optString("message")
    }

    suspend fun updateLyric(title: String, album: String, lyric: String): String =
        invoke(
            "dictionary_update_lyric",
            JSONObject().put("title", title).put("album", album).put("lyric", lyric),
        ).optString("message")

    suspend fun checkWriting(text: String): WritingResult =
        invoke("writing_check", JSONObject().put("text", text)).toWritingResult()

    suspend fun writingLookup(text: String): LookupResult =
        invoke("writing_lookup", JSONObject().put("text", text)).toLookupResult()

    suspend fun saveWritingSettings(settings: WritingSettings): WritingSettings {
        val payload = JSONObject()
            .put("strict_case", settings.strictCase)
            .put("max_undo_steps", settings.maxUndoSteps)
            .put("excluded_words", JSONArray(settings.excludedWords))
            .put("dictionary_format_enabled", settings.dictionaryFormatEnabled)
            .put("dictionary_format_separators", JSONArray(settings.dictionaryFormatSeparators))
        return invoke("writing_save_settings", payload)
            .getJSONObject("settings")
            .toWritingSettings()
    }

    suspend fun translate(
        text: String,
        direction: String,
        useSemanticExpansions: Boolean,
    ): TranslationResult =
        invoke(
            "translate",
            JSONObject()
                .put("text", text)
                .put("direction", direction)
                .put("use_semantic_expansions", useSemanticExpansions),
        ).toTranslationResult()

    suspend fun dataTables(): List<DataTableGroup> =
        invoke("data_tables").let { json ->
            val groupsJson = json.optJSONArray("groups") ?: JSONArray()
            List(groupsJson.length()) { index ->
                val group = groupsJson.getJSONObject(index)
                val tablesJson = group.optJSONArray("tables") ?: JSONArray()
                DataTableGroup(
                    group = group.optString("group"),
                    title = group.optString("title"),
                    note = group.optString("note"),
                    tables = List(tablesJson.length()) { tableIndex ->
                        val table = tablesJson.getJSONObject(tableIndex)
                        DataTableInfo(
                            name = table.optString("name"),
                            label = table.optString("label"),
                            editable = table.optBoolean("editable"),
                            note = table.optString("note"),
                            display = (table.optJSONArray("display") ?: JSONArray()).stringList(),
                        )
                    },
                )
            }
        }

    suspend fun dataPage(
        table: String,
        keyword: String,
        exact: Boolean,
        offset: Int,
        limit: Int = 50,
    ): DataTablePage = invoke(
        "data_page",
        JSONObject()
            .put("table", table)
            .put("keyword", keyword)
            .put("exact", exact)
            .put("offset", offset)
            .put("limit", limit),
    ).toDataTablePage()

    suspend fun dataForm(table: String): DataFormMeta =
        invoke("data_form", JSONObject().put("table", table)).toDataFormMeta()

    suspend fun dataCreate(table: String, values: Map<String, String>): Long? {
        val json = invoke(
            "data_create",
            JSONObject().put("table", table).put("values", JSONObject(values)),
        )
        return if (json.has("key")) json.optLong("key") else null
    }

    suspend fun dataUpdate(table: String, key: Long, values: Map<String, String>): String =
        invoke(
            "data_update",
            JSONObject().put("table", table).put("key", key).put("values", JSONObject(values)),
        ).optString("message")

    suspend fun dataDelete(table: String, key: Long): String =
        invoke("data_delete", JSONObject().put("table", table).put("key", key))
            .optString("message")

    suspend fun dataDeletePreview(table: String, key: Long): DataDeletePreview =
        invoke("data_delete_preview", JSONObject().put("table", table).put("key", key))
            .toDataDeletePreview()

    suspend fun dataReferenceOptions(
        table: String,
        column: String,
        keyword: String = "",
    ): List<DataReferenceOption> {
        val array = invoke(
            "data_reference_options",
            JSONObject().put("table", table).put("column", column).put("keyword", keyword),
        ).getJSONArray("options")
        return List(array.length()) { index ->
            array.getJSONObject(index).let {
                DataReferenceOption(value = it.optValue("value"), label = it.optValue("label"))
            }
        }
    }

    suspend fun dictionaryEntry(headwordId: Long): DictionaryEntry =
        invoke("dictionary_entry", JSONObject().put("headword_id", headwordId))
            .getJSONObject("entry")
            .toDictionaryEntry()

    suspend fun dictionaryCreateWord(
        word: String,
        displayExplanation: String,
        displayClass: String,
        senses: List<DictionarySense>,
    ): Long = invoke(
        "dictionary_create_word",
        JSONObject()
            .put("word", word)
            .put("display_explanation", displayExplanation)
            .put("display_class", displayClass)
            .put("senses", dictionarySensesJson(senses, includeId = false)),
    ).optLong("headword_id")

    suspend fun dictionaryAddSense(
        headwordId: Long,
        explanation: String,
        wordClass: String,
        english: String,
        japanese: String,
    ): Long = invoke(
        "dictionary_add_sense",
        JSONObject()
            .put("headword_id", headwordId)
            .put("explanation", explanation)
            .put("class", wordClass)
            .put("english", english)
            .put("japanese", japanese),
    ).optLong("sense_id")

    suspend fun dictionaryDeleteSense(senseId: Long): String =
        invoke("dictionary_delete_sense", JSONObject().put("sense_id", senseId))
            .optString("message")

    suspend fun dictionaryDeleteHeadword(headwordId: Long, word: String): String =
        invoke(
            "dictionary_delete_headword",
            JSONObject().put("headword_id", headwordId).put("word", word),
        ).optString("message")

    // ---- P3b maintenance ---------------------------------------------------

    /** Rebuilds the derived no_class table from senses without a word class. */
    suspend fun rebuildNoClass(): String =
        invoke("maintenance_no_class").optString("message")

    /** Recounts count/variety for every word from the single lyric source. */
    suspend fun recountWordStats(): String =
        invoke("update_word_count").optString("message")

    /** Reads the replacement preview; only editable tables are returned. */
    suspend fun dataReplacePreview(
        keyword: String,
        replacement: String,
    ): List<GlobalMatch> {
        val array = invoke(
            "data_replace_preview",
            JSONObject().put("keyword", keyword).put("replacement", replacement),
        ).getJSONArray("matches")
        return List(array.length()) { index ->
            array.getJSONObject(index).toGlobalMatch()
        }
    }

    /** Applies exactly the previewed matches; the bridge creates a recovery point. */
    suspend fun dataReplaceApply(
        keyword: String,
        replacement: String,
        matches: List<GlobalMatch>,
    ): String {
        val jsonMatches = JSONArray().apply {
            matches.forEach {
                put(
                    JSONObject()
                        .put("table", it.table)
                        .put("id", it.id)
                        .put("field", it.field)
                        .put("value", it.value),
                )
            }
        }
        return invoke(
            "data_replace_apply",
            JSONObject()
                .put("keyword", keyword)
                .put("replacement", replacement)
                .put("matches", jsonMatches),
        ).optString("message")
    }

    /** Reads the read-only integrity/orphan/pragma report. */
    suspend fun dataDiagnose(): DataDiagnosis {
        val json = invoke("data_diagnose")
        val orphansJson = json.optJSONArray("orphans") ?: JSONArray()
        val tablesJson = json.optJSONArray("tables") ?: JSONArray()
        val pragmasJson = json.optJSONObject("pragmas") ?: JSONObject()
        return DataDiagnosis(
            integrity = json.optString("integrity"),
            foreignKeyViolations = json.optInt("foreign_key_violations", -1),
            orphans = List(orphansJson.length()) { index ->
                orphansJson.getJSONObject(index).let {
                    DataOrphan(
                        table = it.optString("table"),
                        label = it.optString("label"),
                        count = it.optInt("count"),
                    )
                }
            },
            tables = List(tablesJson.length()) { index ->
                tablesJson.getJSONObject(index).let {
                    DataDiagnosisTable(
                        name = it.optString("name"),
                        rows = it.optInt("rows"),
                        group = it.optString("group"),
                    )
                }
            },
            localEdits = json.optInt("local_edits"),
            pragmas = pragmasJson.keys().asSequence()
                .associateWith { column -> pragmasJson.optValue(column) },
        )
    }

    // ---- P4 governance -----------------------------------------------------

    /** Read-only identity of the installed database for the governance screen. */
    suspend fun govIdentity(): GovIdentity {
        val json = invoke("gov_identity")
        return GovIdentity(
            dbVersion = json.optInt("db_version"),
            publishedAt = json.optString("published_at"),
            notes = json.optString("notes"),
            format = json.optString("format"),
            sha256 = json.optString("sha256"),
            size = json.optLong("size"),
            modified = json.optString("modified"),
            wordCount = json.optInt("word_count"),
            songCount = json.optInt("song_count"),
            tableCount = json.optInt("table_count"),
            localEdits = json.optInt("local_edits"),
            localModified = json.optBoolean("local_modified"),
            backupCount = json.optInt("backup_count"),
            latestBackup = json.optJSONObject("latest_backup")?.toBackupEntry(),
        )
    }

    /** Recovery points, newest first (each verified against its sidecar). */
    suspend fun govBackups(): List<BackupEntry> {
        val array = invoke("gov_backups").getJSONArray("backups")
        return List(array.length()) { index ->
            array.getJSONObject(index).toBackupEntry()
        }
    }

    suspend fun govBackupCreate(reason: String = "manual"): String {
        val json = invoke("gov_backup_create", JSONObject().put("reason", reason))
        return json.optString("message").ifBlank { "恢复点已创建。" }
    }

    suspend fun govBackupRestore(path: String): String =
        invoke("gov_backup_restore", JSONObject().put("path", path))
            .optString("message")
            .ifBlank { "已恢复到所选恢复点。" }

    suspend fun prepareCsvArchive(): File {
        val output = File(application.cacheDir, "AlicianDictionaryCsv.zip")
        invoke("export_csv_zip", JSONObject().put("path", output.absolutePath))
        return output
    }

    suspend fun copyDatabaseTo(uri: Uri): Long =
        storageAndUpdates.copyFileTo(databaseFile, uri)

    suspend fun copyFileTo(file: File, uri: Uri): Long =
        storageAndUpdates.copyFileTo(file, uri)

    suspend fun importDatabase(uri: Uri): String = withContext(Dispatchers.IO) {
        val temporary = storageAndUpdates.copyUriToTempDatabase(uri)
        invoke("replace_database", JSONObject().put("path", temporary.absolutePath))
            .optString("message")
    }

    suspend fun resetBundledDatabase(): String = withContext(Dispatchers.IO) {
        val temporary = storageAndUpdates.copyBundledDatabaseToTemp()
        invoke("replace_database", JSONObject().put("path", temporary.absolutePath))
            .optString("message")
    }

    suspend fun databaseInfo(): DatabaseInfo =
        invoke("database_info").getJSONObject("database").toDatabaseInfo()

    /** Revision carried by the installed database (0 for pre-marker databases). */
    suspend fun databaseVersion(): Int = withContext(Dispatchers.IO) {
        invoke("database_metadata").optInt("database_version", 0)
    }

    /** Size and SHA-1 of the installed database, used by the publishing preview. */
    suspend fun localDatabaseIdentity(): Pair<Long, String> =
        storageAndUpdates.localDatabaseIdentity()

    /** Scratch directory holding the stamped copy that gets uploaded. */
    fun publicationScratchFile(): File =
        storageAndUpdates.publicationScratchFile()

    /**
     * Stamps the next version into a copy of the installed database and returns the
     * ledger and manifest the phone commits, so the pipeline only has to verify
     * instead of writing a commit of its own.
     */
    suspend fun prepareDatabasePublication(
        ledgerJson: String,
        version: Int,
        notes: String,
        target: File,
    ): JSONObject = withContext(Dispatchers.IO) {
        invoke(
            "prepare_database_publication",
            JSONObject()
                .put("source", databaseFile.absolutePath)
                .put("target", target.absolutePath)
                .put("ledger_json", ledgerJson)
                .put("version", version)
                .put("notes", notes)
                .put("database_url", DatabaseStorageAndUpdates.DATABASE_RAW_URL),
        )
    }

    fun setAutoDatabaseUpdateCheck(enabled: Boolean) {
        preferences.edit { putBoolean("auto_database_update_check", enabled) }
    }

    fun recordDatabaseUpdateDismissed(version: Int) {
        preferences.edit { putInt("dismissed_database_version", version) }
    }

    fun recordDatabaseCheck() {
        preferences.edit { putLong("last_database_check_at", System.currentTimeMillis()) }
    }

    /**
     * Fetches the small published manifest; the database itself is only downloaded
     * on demand. Returns null when the repository simply does not publish one yet.
     */
    suspend fun fetchDatabaseUpdateManifest(): DatabaseUpdateManifest? =
        storageAndUpdates.fetchDatabaseUpdateManifest()

    /** Downloads the published database and verifies size and SHA-1 before it is applied. */
    suspend fun downloadDatabaseUpdate(manifest: DatabaseUpdateManifest): File =
        storageAndUpdates.downloadDatabaseUpdate(manifest)

    /**
     * Backs up the installed database, then replaces it with the downloaded one.
     *
     * The download is only accepted when the revision stored inside the file is the
     * one the manifest announced, so a mismatched publication cannot install a
     * database under the wrong version number.
     */
    suspend fun applyDownloadedDatabase(file: File, expectedDbVersion: Int): String =
        withContext(Dispatchers.IO) {
            try {
                invoke(
                    "replace_database",
                    JSONObject()
                        .put("path", file.absolutePath)
                        .put("expected_db_version", expectedDbVersion),
                ).optString("message")
            } finally {
                file.delete()
            }
        }

    suspend fun checkRemoteUpdate(): RemoteComparison {
        val json = invoke("check_remote_update")
        return withContext(Dispatchers.Default) {
            val comparison = json.optJSONObject("comparison") ?: JSONObject()
            val diff = json.optJSONObject("diff") ?: JSONObject()
            val tableDiffs = diff.optJSONArray("tables") ?: JSONArray()
            RemoteComparison(
                upToDate = json.optBoolean("up_to_date"),
                message = json.optString("message"),
                localSha1 = json.optString("local_sha1"),
                remoteSha1 = json.optString("remote_sha1"),
                localCounts = comparison.optJSONObject("local").toIntMap(),
                remoteCounts = comparison.optJSONObject("remote").toIntMap(),
                diff = DatabaseDiff(
                    totalAdded = diff.optInt("total_added"),
                    totalRemoved = diff.optInt("total_removed"),
                    totalModified = diff.optInt("total_modified"),
                    totalFieldChanges = diff.optInt("total_field_changes"),
                    tables = List(tableDiffs.length()) { index ->
                        tableDiffs.getJSONObject(index).toDatabaseTableDiff()
                    },
                ),
            )
        }
    }

    suspend fun applyRemoteUpdate(): String =
        invoke("apply_remote_update").optString("message")

    suspend fun checkAppUpdate(): AppUpdateInfo =
        storageAndUpdates.checkAppUpdate()

    fun setSemanticExpansionsEnabled(enabled: Boolean) {
        preferences.edit { putBoolean("semantic_expansions_enabled", enabled) }
    }

    fun saveUiSettings(settings: UiSettings) {
        preferences.edit {
            putString("theme_mode", settings.themeMode.name)
            putBoolean("dynamic_colors", settings.dynamicColors)
            putString("color_palette", settings.colorPalette.name)
            putString("contrast_level", settings.contrastLevel.name)
            putString("shape_style", settings.shapeStyle.name)
            putString("typography_size", settings.typographySize.name)
            putBoolean("amoled_black", settings.amoledBlack)
            putBoolean("alician_font", settings.alicianFont)
        }
    }

    private inline fun <reified T : Enum<T>> preferenceEnum(key: String, fallback: T): T {
        val stored = preferences.getString(key, fallback.name).orEmpty()
        return enumValues<T>().firstOrNull { it.name == stored } ?: fallback
    }
}
