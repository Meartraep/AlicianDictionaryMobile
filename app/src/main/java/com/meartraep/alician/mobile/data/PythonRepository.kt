package com.meartraep.alician.mobile.data

import android.app.Application
import android.database.sqlite.SQLiteDatabase
import android.net.Uri
import android.util.Log
import androidx.core.content.edit
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.meartraep.alician.mobile.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

class PythonRepository(private val application: Application) {
    private val dataDirectory = application.filesDir
    private val databaseFile = File(dataDirectory, "translated.db")
    private val preferences =
        application.getSharedPreferences("alician_mobile", Application.MODE_PRIVATE)
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
        ensureBundledFiles()
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

    private fun ensureBundledFiles() {
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

                database.beginTransaction()
                try {
                    database.execSQL("DROP TABLE IF EXISTS dictionary_semantic_aliases")
                    database.execSQL(
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
                    database.execSQL(
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
                    database.execSQL(
                        """
                        CREATE INDEX IF NOT EXISTS idx_semantic_aliases_alias
                        ON dictionary_semantic_aliases(alias)
                        """.trimIndent(),
                    )
                    database.execSQL(
                        """
                        CREATE INDEX IF NOT EXISTS idx_semantic_aliases_sense
                        ON dictionary_semantic_aliases(sense_id, rank)
                        """.trimIndent(),
                    )
                    database.execSQL("DROP TABLE IF EXISTS semantic_alias_metadata")
                    database.execSQL(
                        """
                        CREATE TABLE semantic_alias_metadata (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL
                        )
                        """.trimIndent(),
                    )
                    database.execSQL(
                        """
                        INSERT INTO semantic_alias_metadata (key, value)
                        SELECT key, value FROM bundled.semantic_alias_metadata
                        """.trimIndent(),
                    )
                    // The previous release stored nearest existing definitions,
                    // not actual aliases. Keeping those tables would be both
                    // misleading in the database manager and wasted space.
                    database.execSQL("DROP TABLE IF EXISTS dictionary_sense_expansions")
                    database.execSQL("DROP TABLE IF EXISTS semantic_expansion_metadata")
                    database.setTransactionSuccessful()
                } finally {
                    database.endTransaction()
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
        ).use { cursor -> cursor.moveToFirst() && cursor.getInt(0) != 0 }
    }

    private suspend fun invoke(method: String, payload: JSONObject = JSONObject()): JSONObject =
        withContext(Dispatchers.IO) {
            check(bridgeReady) { "Python bridge is not ready" }
            val text = Python.getInstance().getModule("mobile_bridge")
                .callAttr("invoke", method, payload.toString())
                .toString()
            JSONObject(text).also { it.requireOk() }
        }

    suspend fun bootstrap(): JSONObject = invoke("bootstrap")

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

    suspend fun getTables(): List<String> =
        invoke("db_tables").getJSONArray("tables").stringList()

    suspend fun getTablePage(
        table: String,
        keyword: String,
        exact: Boolean,
        offset: Int,
        limit: Int = 50,
    ): DbTablePage = invoke(
        "db_table_page",
        JSONObject()
            .put("table", table)
            .put("keyword", keyword)
            .put("exact", exact)
            .put("offset", offset)
            .put("limit", limit),
    ).toDbTablePage()

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

    suspend fun addRecord(table: String, values: Map<String, String>): String =
        invoke(
            "db_add",
            JSONObject().put("table", table).put("values", JSONObject(values)),
        ).optString("message")

    suspend fun updateRecord(table: String, id: Long, values: Map<String, String>): String =
        invoke(
            "db_update",
            JSONObject().put("table", table).put("id", id).put("values", JSONObject(values)),
        ).optString("message")

    suspend fun deleteRecord(table: String, id: Long): String =
        invoke(
            "db_delete",
            JSONObject().put("table", table).put("ids", JSONArray(listOf(id))),
        ).optString("message")

    suspend fun globalSearch(keyword: String, exact: Boolean): List<GlobalMatch> {
        val array = invoke(
            "db_global_search",
            JSONObject().put("keyword", keyword).put("exact", exact),
        ).getJSONArray("results")
        return List(array.length()) { index ->
            array.getJSONObject(index).let {
                GlobalMatch(
                    table = it.optString("table"),
                    id = it.optLong("id"),
                    field = it.optString("field"),
                    value = it.optValue("value"),
                )
            }
        }
    }

    suspend fun globalReplace(
        keyword: String,
        replacement: String,
        records: List<GlobalMatch>,
    ): String {
        val jsonRecords = JSONArray().apply {
            records.forEach {
                put(
                    JSONObject()
                        .put("table", it.table)
                        .put("id", it.id)
                        .put("field", it.field)
                        .put("value", it.value),
                )
            }
        }
        val result = invoke(
            "db_global_replace",
            JSONObject()
                .put("keyword", keyword)
                .put("replacement", replacement)
                .put("records", jsonRecords),
        )
        return "已替换 ${result.optInt("replaced_count")} 个字段。"
    }

    suspend fun updateWordCount(): String = invoke("update_word_count").optString("message")

    suspend fun classifyWords(): String = invoke("classify_words").optString("message")

    suspend fun prepareCsvArchive(): File {
        val output = File(application.cacheDir, "AlicianDictionaryCsv.zip")
        invoke("export_csv_zip", JSONObject().put("path", output.absolutePath))
        return output
    }

    suspend fun copyDatabaseTo(uri: Uri) = withContext(Dispatchers.IO) {
        application.contentResolver.openOutputStream(uri, "w")!!.use { output ->
            databaseFile.inputStream().use { it.copyTo(output) }
        }
    }

    suspend fun copyFileTo(file: File, uri: Uri) = withContext(Dispatchers.IO) {
        application.contentResolver.openOutputStream(uri, "w")!!.use { output ->
            file.inputStream().use { it.copyTo(output) }
        }
    }

    suspend fun importDatabase(uri: Uri): String = withContext(Dispatchers.IO) {
        val temporary = File(application.cacheDir, "database_import.db")
        application.contentResolver.openInputStream(uri)!!.use { input ->
            temporary.outputStream().use(input::copyTo)
        }
        invoke("replace_database", JSONObject().put("path", temporary.absolutePath))
            .optString("message")
    }

    suspend fun resetBundledDatabase(): String = withContext(Dispatchers.IO) {
        val temporary = File(application.cacheDir, "bundled_translated.db")
        application.assets.open("translated.db").use { input ->
            temporary.outputStream().use(input::copyTo)
        }
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
    suspend fun localDatabaseIdentity(): Pair<Long, String> = withContext(Dispatchers.IO) {
        val file = databaseFile
        file.length() to (if (file.isFile) sha1Of(file) else "")
    }

    /** The installed database file; publishing uploads a stamped copy of it. */
    fun installedDatabaseFile(): File = databaseFile

    /** Scratch directory holding the stamped copy that gets uploaded. */
    fun publicationScratchFile(): File =
        File(application.cacheDir, "publication").apply { mkdirs() }

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
                .put("database_url", DATABASE_RAW_URL),
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
    suspend fun fetchDatabaseUpdateManifest(): DatabaseUpdateManifest? = withContext(Dispatchers.IO) {
        val connection = URL(DATABASE_MANIFEST_URL).openConnection() as HttpURLConnection
        connection.requestMethod = "GET"
        connection.connectTimeout = 8_000
        connection.readTimeout = 8_000
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("Cache-Control", "no-cache")
        connection.setRequestProperty("User-Agent", "AlicianDictionaryMobile/" + BuildConfig.VERSION_NAME)
        try {
            when (val responseCode = connection.responseCode) {
                HttpURLConnection.HTTP_NOT_FOUND -> return@withContext null
                HttpURLConnection.HTTP_OK -> Unit
                else -> throw IllegalStateException("数据库更新清单获取失败（HTTP " + responseCode + "）")
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
            connection.setRequestProperty("User-Agent", "AlicianDictionaryMobile/" + BuildConfig.VERSION_NAME)
            try {
                val responseCode = connection.responseCode
                if (responseCode != HttpURLConnection.HTTP_OK) {
                    throw IllegalStateException("数据库下载失败（HTTP " + responseCode + "）")
                }
                connection.inputStream.use { input ->
                    target.outputStream().use(input::copyTo)
                }
            } finally {
                connection.disconnect()
            }
            if (manifest.size > 0L && target.length() != manifest.size) {
                val actual = target.length()
                target.delete()
                throw IllegalStateException("数据库下载不完整（" + actual + " / " + manifest.size + " 字节）")
            }
            if (manifest.sha1.isNotBlank() && sha1Of(target) != manifest.sha1) {
                target.delete()
                throw IllegalStateException("数据库校验失败，下载内容与发布清单不一致。")
            }
            target
        }

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

    fun setAlicianFontEnabled(enabled: Boolean) {
        preferences.edit { putBoolean("alician_font", enabled) }
    }

    fun setDynamicColorsEnabled(enabled: Boolean) {
        preferences.edit { putBoolean("dynamic_colors", enabled) }
    }

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

    private companion object {
        const val DATABASE_MANIFEST_URL =
            "https://raw.githubusercontent.com/Meartraep/AlicianDictionaryMobile/" +
                "main/database-manifest.json"
        const val DATABASE_RAW_URL =
            "https://raw.githubusercontent.com/Meartraep/AlicianDictionaryMobile/" +
                "main/app/src/main/assets/translated.db"
        const val APP_RELEASE_API_URL =
            "https://api.github.com/repos/Meartraep/AlicianDictionaryMobile/releases/latest"
        const val APP_RELEASES_URL =
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

private fun JSONObject.requireOk() {
    if (!optBoolean("ok", false)) {
        throw IllegalStateException(optString("message", "操作失败"))
    }
}

private fun JSONObject?.toIntMap(): Map<String, Int> {
    if (this == null) return emptyMap()
    return keys().asSequence().associateWith { optInt(it) }
}

private fun JSONObject.optValue(key: String): String {
    val value = opt(key)
    return if (value == null || value === JSONObject.NULL) "" else value.toString()
}

private fun JSONArray.stringList(): List<String> =
    List(length()) { optString(it) }

private fun JSONArray.ranges(): List<TextRange> =
    List(length()) { index ->
        getJSONArray(index).let { TextRange(it.optInt(0), it.optInt(1)) }
    }

private fun JSONObject.toDatabaseInfo() = DatabaseInfo(
    path = optString("path"),
    size = optLong("size"),
    modified = optString("modified"),
    sha256 = optString("sha256"),
    tableCount = optInt("table_count"),
    wordCount = optInt("word_count"),
    songCount = optInt("song_count"),
)

private fun JSONObject.toDictionaryResult(): DictionaryResult {
    val sectionArray = optJSONArray("sections") ?: JSONArray()
    val sections = List(sectionArray.length()) { sectionIndex ->
        val section = sectionArray.getJSONObject(sectionIndex)
        val entriesJson = section.optJSONArray("entries") ?: JSONArray()
        DictionarySection(
            title = section.optString("title"),
            kind = section.optString("kind"),
            entries = List(entriesJson.length()) { entryIndex ->
                entriesJson.getJSONObject(entryIndex).let {
                    DictionaryEntry(
                        word = it.optString("word"),
                        explanation = it.optString("explanation"),
                        wordClass = it.optString("word_class"),
                        kind = it.optString("kind"),
                        count = it.optInt("count"),
                        variety = it.optInt("variety"),
                        englishGloss = it.optString("english_gloss"),
                        japaneseGloss = it.optString("japanese_gloss"),
                        headwordId = it.optInt("headword_id"),
                        album = it.optString("album"),
                        songTitle = it.optString("song_title"),
                        senses = it.toDictionarySenses(),
                    )
                }
            },
        )
    }
    val suggestionsJson = optJSONArray("suggestions") ?: JSONArray()
    return DictionaryResult(
        query = optString("query"),
        exactMatch = optBoolean("exact_match"),
        isPhrase = optBoolean("is_phrase"),
        sections = sections,
        suggestions = List(suggestionsJson.length()) { index ->
            suggestionsJson.getJSONObject(index).let { suggestion ->
                val words = suggestion.optJSONArray("words")
                val word = suggestion.optString("word").ifBlank {
                    words?.optString(0).orEmpty()
                }
                Suggestion(
                    word = word,
                    explanation = suggestion.optString("explanation"),
                    score = suggestion.optDouble("score", suggestion.optDouble("similarity", 0.0)),
                )
            }
        },
        history = (optJSONArray("history") ?: JSONArray()).stringList(),
        message = optString("message"),
    )
}

private fun JSONObject.toDictionarySenses(): List<DictionarySense> {
    val sensesJson = optJSONArray("senses") ?: JSONArray()
    return List(sensesJson.length()) { index ->
        sensesJson.getJSONObject(index).let { sense ->
            DictionarySense(
                id = sense.optInt("id"),
                explanation = sense.optString("explanation"),
                wordClass = sense.optString("class"),
                englishGloss = sense.optString("english_gloss"),
                japaneseGloss = sense.optString("japanese_gloss"),
            )
        }
    }
}

private fun JSONObject.toExampleResult(): ExampleResult {
    val array = optJSONArray("examples") ?: JSONArray()
    val stats = optJSONArray("song_stats") ?: JSONArray()
    return ExampleResult(
        word = optString("word"),
        examples = List(array.length()) { index ->
            array.getJSONObject(index).let { it.toLyricExample() }
        },
        positionFilter = optString("position_filter", "any"),
        songStats = List(stats.length()) { index ->
            stats.getJSONObject(index).let {
                SongExampleStats(
                    album = it.optString("album"),
                    title = it.optString("title"),
                    before = it.optInt("before"),
                    after = it.optInt("after"),
                )
            }
        },
        totalBefore = optInt("total_before"),
        totalAfter = optInt("total_after"),
        deduplicationRate = optDouble("deduplication_rate"),
        message = optString("message"),
    )
}

private fun JSONObject.toLyricExample(): LyricExample {
    val linesJson = optJSONArray("lyric_translations") ?: JSONArray()
    return LyricExample(
        id = optInt("id"),
        paragraph = optString("paragraph"),
        title = optString("title"),
        album = optString("album"),
        lyric = optString("lyric"),
        start = optInt("start"),
        end = optInt("end"),
        poeticTranslation = optString("poetic_translation"),
        englishTranslation = optString("english_translation"),
        japaneseTranslation = optString("japanese_translation"),
        koreanTranslation = optString("korean_translation"),
        lyricTranslations = List(linesJson.length()) { lineIndex ->
            linesJson.getJSONObject(lineIndex).let {
                LyricLineTranslation(
                    line = it.optString("line"),
                    poetic = it.optString("poetic"),
                    english = it.optString("english"),
                    japanese = it.optString("japanese"),
                    korean = it.optString("korean"),
                )
            }
        },
    )
}

private fun JSONObject.toWritingResult(): WritingResult {
    val issuesJson = optJSONArray("sidebar_items") ?: JSONArray()
    return WritingResult(
        sourceText = optString("source_text"),
        unknownCount = optInt("unknown_count"),
        unknownRanges = (optJSONArray("unknown_ranges") ?: JSONArray()).ranges(),
        lowStatRanges = (optJSONArray("lowstat_ranges") ?: JSONArray()).ranges(),
        issues = List(issuesJson.length()) { index ->
            issuesJson.getJSONObject(index).let {
                WritingIssue(
                    key = it.optString("key"),
                    display = it.optString("display"),
                    type = it.optString("type"),
                    position = it.optInt("pos"),
                    reasons = (it.optJSONArray("reasons") ?: JSONArray()).stringList(),
                    count = it.optInt("count"),
                    variety = it.optInt("variety"),
                )
            }
        },
        status = optString("status"),
    )
}

private fun JSONObject.toWritingSettings() = WritingSettings(
    strictCase = optBoolean("strict_case", true),
    maxUndoSteps = optInt("max_undo_steps", 100),
    excludedWords = (optJSONArray("excluded_words") ?: JSONArray()).stringList(),
    dictionaryFormatEnabled = optBoolean("dictionary_format_enabled"),
    dictionaryFormatSeparators =
        (optJSONArray("dictionary_format_separators") ?: JSONArray(listOf(":", "："))).stringList(),
)

private fun JSONObject.toLookupResult(): LookupResult {
    val explanationsJson = optJSONArray("explanations") ?: JSONArray()
    val similarJson = optJSONArray("similar_words") ?: JSONArray()
    return LookupResult(
        explanations = List(explanationsJson.length()) { index ->
            explanationsJson.getJSONObject(index).let {
                LookupExplanation(
                    word = it.optString("word"),
                    partOfSpeech = it.optString("part_of_speech"),
                    explanation = it.optString("explanation"),
                )
            }
        },
        similarWords = List(similarJson.length()) { index ->
            similarJson.getJSONObject(index).let {
                SimilarWord(
                    word = it.optString("word"),
                    similarWord = it.optString("similar_word"),
                    partOfSpeech = it.optString("part_of_speech"),
                    explanation = it.optString("explanation"),
                    score = it.optDouble("score"),
                )
            }
        },
        message = optString("message"),
    )
}

private fun JSONObject.toTranslationResult(): TranslationResult {
    val tokensJson = optJSONArray("tokens") ?: JSONArray()
    val stats = optJSONObject("stats") ?: JSONObject()
    return TranslationResult(
        direction = optString("direction"),
        sourceText = optString("source_text"),
        resultText = optString("result_text"),
        tokens = List(tokensJson.length()) { index ->
            tokensJson.getJSONObject(index).let { token ->
                val alternativesJson = token.optJSONArray("alternatives") ?: JSONArray()
                val templateArgumentsJson =
                    token.optJSONArray("template_arguments") ?: JSONArray()
                TranslationToken(
                    source = token.optString("source"),
                    target = token.optString("target"),
                    status = token.optString("status"),
                    method = token.optString("method"),
                    confidence = token.optDouble("confidence"),
                    explanation = token.optString("explanation"),
                    wordClass = token.optString("word_class"),
                    count = token.optInt("count"),
                    variety = token.optInt("variety"),
                    alternatives = List(alternativesJson.length()) { alternativeIndex ->
                        alternativesJson.getJSONObject(alternativeIndex).let {
                            TranslationAlternative(
                                target = it.optString("target"),
                                explanation = it.optString("explanation"),
                                wordClass = it.optString("word_class"),
                                score = it.optDouble("score"),
                            )
                        }
                    },
                    note = token.optString("note"),
                    resolvedTarget = token.optString("resolved_target"),
                    omitFromResult = token.optBoolean("omit_from_result"),
                    templateArguments = templateArgumentsJson.stringList(),
                )
            }
        },
        exact = stats.optInt("exact"),
        approximate = stats.optInt("approximate"),
        unknown = stats.optInt("unknown"),
        semanticExpansionsEnabled = optBoolean("semantic_expansions_enabled"),
        semanticExpansionsAvailable = optBoolean("semantic_expansions_available"),
        semanticExpansionCount = optInt("semantic_expansion_count"),
        message = optString("message"),
    )
}

private fun dictionarySensesJson(
    senses: List<DictionarySense>,
    includeId: Boolean,
): JSONArray = JSONArray().apply {
    senses.forEach { sense ->
        put(
            JSONObject()
                .apply { if (includeId) put("id", sense.id) }
                .put("explanation", sense.explanation)
                .put("class", sense.wordClass)
                .put("english", sense.englishGloss)
                .put("japanese", sense.japaneseGloss),
        )
    }
}

private fun JSONObject.toDataFormMeta(): DataFormMeta {
    val fieldsJson = optJSONArray("fields") ?: JSONArray()
    val cascadeJson = optJSONArray("cascade") ?: JSONArray()
    return DataFormMeta(
        table = optString("table"),
        label = optString("label"),
        group = optString("group"),
        note = optString("note"),
        editable = optBoolean("editable"),
        keyColumn = optString("key_column", "id"),
        display = (optJSONArray("display") ?: JSONArray()).stringList(),
        fields = List(fieldsJson.length()) { index ->
            fieldsJson.getJSONObject(index).let { field ->
                DataFieldMeta(
                    name = field.optString("name"),
                    label = field.optString("label"),
                    type = field.optString("type"),
                    notnull = field.optBoolean("notnull"),
                    maxLength = field.optInt("max_length"),
                    required = field.optBoolean("required"),
                    primaryKey = field.optBoolean("primary_key"),
                    multiline = field.optBoolean("multiline"),
                    hasDefault = field.has("default") && !field.isNull("default"),
                    defaultValue = if (field.isNull("default")) "" else field.optValue("default"),
                    reference = field.optJSONObject("reference")?.let { reference ->
                        DataReference(
                            table = reference.optString("table"),
                            label = reference.optString("label"),
                            column = reference.optString("column"),
                        )
                    },
                )
            }
        },
        cascade = List(cascadeJson.length()) { index ->
            cascadeJson.getJSONObject(index).let {
                DataCascadeInfo(
                    table = it.optString("table"),
                    label = it.optString("label"),
                    column = it.optString("column"),
                )
            }
        },
    )
}

private fun JSONObject.toDataDeletePreview(): DataDeletePreview {
    val childrenJson = optJSONArray("children") ?: JSONArray()
    return DataDeletePreview(
        table = optString("table"),
        label = optString("label"),
        key = optLong("key"),
        summary = optString("summary"),
        deletedSelf = optInt("deleted_self"),
        children = List(childrenJson.length()) { index ->
            childrenJson.getJSONObject(index).let {
                DataDeleteChild(
                    table = it.optString("table"),
                    label = it.optString("label"),
                    group = it.optString("group"),
                    count = it.optInt("count"),
                )
            }
        },
        totalRemoved = optInt("total_removed"),
    )
}

private fun JSONObject.toDictionaryEntry(): DictionaryEntry = DictionaryEntry(
    word = optValue("word"),
    explanation = optValue("explanation"),
    wordClass = optString("word_class"),
    kind = optString("kind", "alice"),
    count = optInt("count"),
    variety = optInt("variety"),
    englishGloss = optString("english_gloss"),
    japaneseGloss = optString("japanese_gloss"),
    headwordId = optInt("headword_id"),
    album = optString("album"),
    songTitle = optString("song_title"),
    senses = toDictionarySenses(),
)

private fun JSONObject.toDataTablePage(): DataTablePage {
    val fields = (optJSONArray("fields") ?: JSONArray()).stringList()
    val rowsJson = optJSONArray("rows") ?: JSONArray()
    return DataTablePage(
        table = optString("table"),
        label = optString("label"),
        group = optString("group"),
        editable = optBoolean("editable"),
        display = (optJSONArray("display") ?: JSONArray()).stringList(),
        fields = fields,
        rows = List(rowsJson.length()) { index ->
            rowsJson.getJSONObject(index).let { row ->
                fields.associateWith { row.optValue(it) }
            }
        },
        total = optInt("total"),
        offset = optInt("offset"),
        limit = optInt("limit", 50),
    )
}

private fun JSONObject.toDbTablePage(): DbTablePage {
    val fields = (optJSONArray("fields") ?: JSONArray()).stringList()
    val rowsJson = optJSONArray("data") ?: JSONArray()
    return DbTablePage(
        table = optString("table"),
        fields = fields,
        rows = List(rowsJson.length()) { index ->
            rowsJson.getJSONObject(index).let { row ->
                fields.associateWith { row.optValue(it) }
            }
        },
        total = optInt("total"),
        offset = optInt("offset"),
        limit = optInt("limit", 50),
    )
}

private fun JSONObject.toDatabaseTableDiff(): DatabaseTableDiff {
    val addedJson = optJSONArray("added_rows") ?: JSONArray()
    val removedJson = optJSONArray("removed_rows") ?: JSONArray()
    val fieldsJson = optJSONArray("field_diffs") ?: JSONArray()
    return DatabaseTableDiff(
        table = optString("table"),
        localRows = optInt("local_rows"),
        remoteRows = optInt("remote_rows"),
        added = optInt("added"),
        removed = optInt("removed"),
        modified = optInt("modified"),
        fieldChanges = optInt("field_changes"),
        addedRows = List(addedJson.length()) { index ->
            addedJson.getJSONObject(index).toDatabaseRowDiff()
        },
        removedRows = List(removedJson.length()) { index ->
            removedJson.getJSONObject(index).toDatabaseRowDiff()
        },
        fieldDiffs = List(fieldsJson.length()) { index ->
            fieldsJson.getJSONObject(index).let {
                DatabaseFieldDiff(
                    rowId = it.optString("row_id"),
                    column = it.optString("column"),
                    localValue = it.optValue("local_value"),
                    remoteValue = it.optValue("remote_value"),
                )
            }
        },
        truncatedAdded = optBoolean("truncated_added"),
        truncatedRemoved = optBoolean("truncated_removed"),
        truncatedModified = optBoolean("truncated_modified"),
    )
}

private fun JSONObject.toDatabaseRowDiff(): DatabaseRowDiff {
    val values = optJSONObject("values") ?: JSONObject()
    return DatabaseRowDiff(
        id = optString("id"),
        values = values.keys().asSequence().associateWith { values.optValue(it) },
    )
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
