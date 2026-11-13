package com.meartraep.alician.mobile.data

import org.json.JSONArray
import org.json.JSONObject

internal fun JSONObject.requireOk() {
    if (!optBoolean("ok", false)) {
        throw IllegalStateException(optString("message", "操作失败"))
    }
}

internal fun JSONObject?.toIntMap(): Map<String, Int> {
    if (this == null) return emptyMap()
    return keys().asSequence().associateWith { optInt(it) }
}

internal fun JSONObject.toBackupEntry(): BackupEntry = BackupEntry(
    path = optString("path"),
    name = optString("name"),
    dbVersion = optInt("db_version"),
    size = optLong("size"),
    sha1 = optString("sha1"),
    createdAt = optString("created_at"),
    reason = optString("reason"),
)

internal fun JSONObject.toGlobalMatch(): GlobalMatch = GlobalMatch(
    table = optString("table"),
    id = optLong("id"),
    field = optString("field"),
    value = optValue("value"),
)

internal fun JSONObject.optValue(key: String): String {
    val value = opt(key)
    return if ((value == null) || (value === JSONObject.NULL)) "" else value.toString()
}

internal fun JSONArray.stringList(): List<String> =
    List(length()) { optString(it) }

internal fun JSONArray.ranges(): List<TextRange> =
    List(length()) { index ->
        getJSONArray(index).let { TextRange(it.optInt(0), it.optInt(1)) }
    }

internal fun JSONObject.toDatabaseInfo() = DatabaseInfo(
    path = optString("path"),
    size = optLong("size"),
    modified = optString("modified"),
    sha256 = optString("sha256"),
    tableCount = optInt("table_count"),
    wordCount = optInt("word_count"),
    songCount = optInt("song_count"),
)

internal fun JSONObject.toDictionaryResult(): DictionaryResult {
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

internal fun JSONObject.toDictionarySenses(): List<DictionarySense> {
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

internal fun JSONObject.toExampleResult(): ExampleResult {
    val array = optJSONArray("examples") ?: JSONArray()
    val stats = optJSONArray("song_stats") ?: JSONArray()
    return ExampleResult(
        word = optString("word"),
        examples = List(array.length()) { index ->
            array.getJSONObject(index).toLyricExample()
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

internal fun JSONObject.toLyricExample(): LyricExample {
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

internal fun JSONObject.toWritingResult(): WritingResult {
    val issuesJson = optJSONArray("sidebar_items") ?: JSONArray()
    return WritingResult(
        sourceText = optString("source_text"),
        unknownCount = optInt("unknown_count"),
        unknownRanges = (optJSONArray("unknown_ranges") ?: JSONArray()).ranges(),
        uncertainRanges = (optJSONArray("uncertain_ranges") ?: JSONArray()).ranges(),
        issues = List(issuesJson.length()) { index ->
            issuesJson.getJSONObject(index).let {
                WritingIssue(
                    key = it.optString("key"),
                    display = it.optString("display"),
                    type = it.optString("type"),
                    position = it.optInt("pos"),
                )
            }
        },
        status = optString("status"),
    )
}

internal fun JSONObject.toWritingSettings() = WritingSettings(
    strictCase = optBoolean("strict_case", true),
    maxUndoSteps = optInt("max_undo_steps", 100),
    excludedWords = (optJSONArray("excluded_words") ?: JSONArray()).stringList(),
    dictionaryFormatEnabled = optBoolean("dictionary_format_enabled"),
    dictionaryFormatSeparators =
        (optJSONArray("dictionary_format_separators") ?: JSONArray(listOf(":", "："))).stringList(),
)

internal fun JSONObject.toLookupResult(): LookupResult {
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

internal fun JSONObject.toTranslationResult(): TranslationResult {
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

internal fun dictionarySensesJson(
    senses: List<DictionarySense>,
    includeId: Boolean,
): JSONArray = JSONArray().apply {
    senses.forEach { (id, explanation, wordClass, englishGloss, japaneseGloss) ->
        put(
            JSONObject()
                .apply { if (includeId) put("id", id) }
                .put("explanation", explanation)
                .put("class", wordClass)
                .put("english", englishGloss)
                .put("japanese", japaneseGloss),
        )
    }
}

internal fun JSONObject.toDataFormMeta(): DataFormMeta {
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

internal fun JSONObject.toDataDeletePreview(): DataDeletePreview {
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

internal fun JSONObject.toDictionaryEntry(): DictionaryEntry = DictionaryEntry(
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

internal fun JSONObject.toDataTablePage(): DataTablePage {
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

internal fun JSONObject.toDatabaseTableDiff(): DatabaseTableDiff {
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
