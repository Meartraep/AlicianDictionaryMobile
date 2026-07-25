package com.meartraep.alician.mobile.data

import android.app.Application
import android.net.Uri
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import com.meartraep.alician.mobile.BuildConfig
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
    private var bridgeReady = false

    val databasePath: String get() = databaseFile.absolutePath
    val alicianFontEnabled: Boolean
        get() = preferences.getBoolean("alician_font", false)
    val dynamicColorsEnabled: Boolean
        get() = preferences.getBoolean("dynamic_colors", true)

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
            preferences.edit()
                .putString("database_asset_version", BuildConfig.DATABASE_ASSET_VERSION)
                .apply()
        }
        val config = File(dataDirectory, "word_checker_config.json")
        if (!config.exists()) {
            application.assets.open("word_checker_config.json").use { input ->
                config.outputStream().use(input::copyTo)
            }
        }
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
    ): DictionaryResult {
        val json = invoke(
            "dictionary_search",
            JSONObject().put("query", query).put("exact", exact).put("position", position),
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

    suspend fun translate(text: String, direction: String): TranslationResult =
        invoke(
            "translate",
            JSONObject().put("text", text).put("direction", direction),
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

    suspend fun checkRemoteUpdate(): RemoteComparison {
        val json = invoke("check_remote_update")
        val comparison = json.optJSONObject("comparison") ?: JSONObject()
        return RemoteComparison(
            upToDate = json.optBoolean("up_to_date"),
            message = json.optString("message"),
            localSha1 = json.optString("local_sha1"),
            remoteSha1 = json.optString("remote_sha1"),
            localCounts = comparison.optJSONObject("local").toIntMap(),
            remoteCounts = comparison.optJSONObject("remote").toIntMap(),
        )
    }

    suspend fun applyRemoteUpdate(): String =
        invoke("apply_remote_update").optString("message")

    fun setAlicianFontEnabled(enabled: Boolean) {
        preferences.edit().putBoolean("alician_font", enabled).apply()
    }

    fun setDynamicColorsEnabled(enabled: Boolean) {
        preferences.edit().putBoolean("dynamic_colors", enabled).apply()
    }
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
            suggestionsJson.getJSONObject(index).let {
                Suggestion(
                    word = it.optString("word"),
                    explanation = it.optString("explanation"),
                    score = it.optDouble("score", it.optDouble("similarity", 0.0)),
                )
            }
        },
        history = (optJSONArray("history") ?: JSONArray()).stringList(),
        message = optString("message"),
    )
}

private fun JSONObject.toExampleResult(): ExampleResult {
    val array = optJSONArray("examples") ?: JSONArray()
    return ExampleResult(
        word = optString("word"),
        examples = List(array.length()) { index ->
            array.getJSONObject(index).let {
                LyricExample(
                    id = it.optInt("id"),
                    paragraph = it.optString("paragraph"),
                    title = it.optString("title"),
                    album = it.optString("album"),
                    lyric = it.optString("lyric"),
                    start = it.optInt("start"),
                    end = it.optInt("end"),
                )
            }
        },
        positionFilter = optString("position_filter", "any"),
            songStats = optJSONArray("song_stats")?.length() ?: optInt("song_stats"),
        totalBefore = optInt("total_before"),
        totalAfter = optInt("total_after"),
        deduplicationRate = optDouble("deduplication_rate"),
        message = optString("message"),
    )
}

private fun JSONObject.toWritingResult(): WritingResult {
    val issuesJson = optJSONArray("sidebar_items") ?: JSONArray()
    return WritingResult(
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
                )
            }
        },
        exact = stats.optInt("exact"),
        approximate = stats.optInt("approximate"),
        unknown = stats.optInt("unknown"),
        message = optString("message"),
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
