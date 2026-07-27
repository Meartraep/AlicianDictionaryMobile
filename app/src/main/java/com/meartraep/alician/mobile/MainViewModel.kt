package com.meartraep.alician.mobile

import android.app.Application
import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.meartraep.alician.mobile.data.AppUpdateInfo
import com.meartraep.alician.mobile.data.DatabaseInfo
import com.meartraep.alician.mobile.data.DbTablePage
import com.meartraep.alician.mobile.data.DictionaryResult
import com.meartraep.alician.mobile.data.ExampleResult
import com.meartraep.alician.mobile.data.GlobalMatch
import com.meartraep.alician.mobile.data.LookupResult
import com.meartraep.alician.mobile.data.PythonRepository
import com.meartraep.alician.mobile.data.RemoteComparison
import com.meartraep.alician.mobile.data.TranslationResult
import com.meartraep.alician.mobile.data.UiSettings
import com.meartraep.alician.mobile.data.WritingResult
import com.meartraep.alician.mobile.data.WritingSettings
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.File

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = PythonRepository(application)

    var ready by mutableStateOf(false)
        private set
    var busyMessage by mutableStateOf<String?>(null)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set
    var noticeMessage by mutableStateOf<String?>(null)
        private set

    var uiSettings by mutableStateOf(repository.uiSettings)
        private set
    var alicianFontEnabled by mutableStateOf(uiSettings.alicianFont)
        private set
    var dynamicColorsEnabled by mutableStateOf(uiSettings.dynamicColors)
        private set

    var dictionaryResult by mutableStateOf<DictionaryResult?>(null)
        private set
    var dictionaryExamples by mutableStateOf<ExampleResult?>(null)
        private set
    var history by mutableStateOf<List<String>>(emptyList())
        private set

    var writingResult by mutableStateOf<WritingResult?>(null)
        private set
    var writingSettings by mutableStateOf(WritingSettings())
        private set
    var lookupResult by mutableStateOf<LookupResult?>(null)
        private set

    var translationResult by mutableStateOf<TranslationResult?>(null)
        private set

    var dbTables by mutableStateOf<List<String>>(emptyList())
        private set
    var dbPage by mutableStateOf<DbTablePage?>(null)
        private set
    var globalMatches by mutableStateOf<List<GlobalMatch>>(emptyList())
        private set

    var databaseInfo by mutableStateOf(DatabaseInfo())
        private set
    var remoteComparison by mutableStateOf<RemoteComparison?>(null)
        private set
    var appUpdateInfo by mutableStateOf<AppUpdateInfo?>(null)
        private set
    var checkingAppUpdate by mutableStateOf(false)
        private set
    var appUpdateError by mutableStateOf<String?>(null)
        private set

    init {
        launchTask("正在初始化词典…") {
            val bootstrap = repository.initialize()
            applyBootstrap(bootstrap)
            ready = true
            viewModelScope.launch {
                refreshAppUpdate(showFeedback = false)
            }
        }
    }

    private fun applyBootstrap(json: JSONObject) {
        history = json.optJSONArray("history")?.let { array ->
            List(array.length()) { array.optString(it) }
        } ?: emptyList()
        writingSettings = json.optJSONObject("writing_settings")?.let {
            WritingSettings(
                strictCase = it.optBoolean("strict_case", true),
                maxUndoSteps = it.optInt("max_undo_steps", 100),
                excludedWords = it.optJSONArray("excluded_words")?.let { values ->
                    List(values.length()) { index -> values.optString(index) }
                } ?: emptyList(),
                dictionaryFormatEnabled = it.optBoolean("dictionary_format_enabled"),
                dictionaryFormatSeparators =
                    it.optJSONArray("dictionary_format_separators")?.let { values ->
                        List(values.length()) { index -> values.optString(index) }
                    } ?: listOf(":", "："),
            )
        } ?: WritingSettings()
        databaseInfo = json.optJSONObject("database")?.let {
            DatabaseInfo(
                path = it.optString("path"),
                size = it.optLong("size"),
                modified = it.optString("modified"),
                sha256 = it.optString("sha256"),
                tableCount = it.optInt("table_count"),
                wordCount = it.optInt("word_count"),
                songCount = it.optInt("song_count"),
            )
        } ?: DatabaseInfo()
    }

    private fun launchTask(label: String, block: suspend () -> Unit) {
        viewModelScope.launch {
            busyMessage = label
            errorMessage = null
            try {
                block()
            } catch (throwable: Throwable) {
                errorMessage = throwable.message ?: "操作失败"
            } finally {
                busyMessage = null
            }
        }
    }

    fun clearMessages() {
        errorMessage = null
        noticeMessage = null
    }

    fun searchDictionary(query: String, exact: Boolean, position: String) {
        if (query.isBlank()) return
        launchTask("正在查询…") {
            dictionaryResult = repository.dictionarySearch(query.trim(), exact, position)
            history = dictionaryResult?.history ?: history
        }
    }

    fun loadExamples(word: String, position: String) {
        launchTask("正在查找歌词例句…") {
            dictionaryExamples = repository.dictionaryExamples(word, position)
        }
    }

    fun closeExamples() {
        dictionaryExamples = null
    }

    fun updateLyric(title: String, album: String, lyric: String) {
        launchTask("正在保存歌词…") {
            noticeMessage = repository.updateLyric(title, album, lyric)
            dictionaryExamples = dictionaryExamples?.let {
                repository.dictionaryExamples(it.word, it.positionFilter)
            }
            refreshDatabaseInfo()
        }
    }

    fun checkWriting(text: String) {
        launchTask("正在检查文本…") {
            writingResult = repository.checkWriting(text)
        }
    }

    fun checkWritingSilently(text: String) {
        viewModelScope.launch {
            try {
                writingResult = repository.checkWriting(text)
            } catch (throwable: Throwable) {
                errorMessage = throwable.message ?: "写作检查失败"
            }
        }
    }

    fun lookupWriting(text: String) {
        launchTask("正在查询释义…") {
            lookupResult = repository.writingLookup(text)
        }
    }

    fun closeLookup() {
        lookupResult = null
    }

    fun saveWritingSettings(settings: WritingSettings) {
        launchTask("正在保存写作设置…") {
            writingSettings = repository.saveWritingSettings(settings)
            noticeMessage = "写作助手设置已保存。"
        }
    }

    fun translate(text: String, direction: String) {
        launchTask("正在翻译…") {
            translationResult = repository.translate(text, direction)
        }
    }

    fun loadDatabase(table: String? = null, keyword: String = "", exact: Boolean = false, offset: Int = 0) {
        launchTask("正在读取数据库…") {
            if (dbTables.isEmpty()) dbTables = repository.getTables()
            val selected = table ?: dbPage?.table ?: dbTables.firstOrNull()
            if (selected != null) {
                dbPage = repository.getTablePage(selected, keyword, exact, offset)
            }
        }
    }

    fun addRecord(table: String, values: Map<String, String>) {
        launchTask("正在新增记录…") {
            noticeMessage = repository.addRecord(table, values)
            dbPage = repository.getTablePage(table, "", false, dbPage?.offset ?: 0)
            refreshDatabaseInfo()
        }
    }

    fun updateRecord(table: String, id: Long, values: Map<String, String>) {
        launchTask("正在保存记录…") {
            noticeMessage = repository.updateRecord(table, id, values)
            dbPage = repository.getTablePage(table, "", false, dbPage?.offset ?: 0)
            refreshDatabaseInfo()
        }
    }

    fun deleteRecord(table: String, id: Long) {
        launchTask("正在删除记录…") {
            noticeMessage = repository.deleteRecord(table, id)
            dbPage = repository.getTablePage(table, "", false, dbPage?.offset ?: 0)
            refreshDatabaseInfo()
        }
    }

    fun globalSearch(keyword: String, exact: Boolean) {
        if (keyword.isBlank()) return
        launchTask("正在跨表搜索…") {
            globalMatches = repository.globalSearch(keyword, exact)
        }
    }

    fun globalReplace(keyword: String, replacement: String, selected: List<GlobalMatch>) {
        launchTask("正在批量替换…") {
            noticeMessage = repository.globalReplace(keyword, replacement, selected)
            globalMatches = repository.globalSearch(keyword, false)
            loadDatabase()
        }
    }

    fun updateWordCount() {
        launchTask("正在更新词频与泛度，可能需要片刻…") {
            noticeMessage = repository.updateWordCount()
            refreshDatabaseInfo()
        }
    }

    fun classifyWords() {
        launchTask("正在更新词性统计表…") {
            noticeMessage = repository.classifyWords()
            dbTables = repository.getTables()
            refreshDatabaseInfo()
        }
    }

    fun exportCsv(onReady: (File) -> Unit) {
        launchTask("正在生成 CSV 压缩包…") {
            onReady(repository.prepareCsvArchive())
        }
    }

    fun savePreparedFile(file: File, uri: Uri) {
        launchTask("正在导出文件…") {
            repository.copyFileTo(file, uri)
            noticeMessage = "导出完成。"
        }
    }

    fun exportDatabase(uri: Uri) {
        launchTask("正在导出数据库…") {
            repository.copyDatabaseTo(uri)
            noticeMessage = "数据库导出完成。"
        }
    }

    fun importDatabase(uri: Uri) {
        launchTask("正在验证并导入数据库…") {
            noticeMessage = repository.importDatabase(uri)
            afterDatabaseChanged()
        }
    }

    fun resetDatabase() {
        launchTask("正在恢复内置数据库…") {
            noticeMessage = repository.resetBundledDatabase()
            afterDatabaseChanged()
        }
    }

    fun checkRemoteUpdate() {
        launchTask("正在下载并检查云端数据库…") {
            remoteComparison = repository.checkRemoteUpdate()
        }
    }

    fun applyRemoteUpdate() {
        launchTask("正在备份并更新数据库…") {
            noticeMessage = repository.applyRemoteUpdate()
            remoteComparison = null
            afterDatabaseChanged()
        }
    }

    fun dismissRemoteComparison() {
        remoteComparison = null
    }

    fun checkAppUpdate() {
        if (checkingAppUpdate) return
        viewModelScope.launch {
            refreshAppUpdate(showFeedback = true)
        }
    }

    private suspend fun refreshAppUpdate(showFeedback: Boolean) {
        if (checkingAppUpdate) return
        checkingAppUpdate = true
        appUpdateError = null
        try {
            appUpdateInfo = repository.checkAppUpdate()
            if (showFeedback) {
                noticeMessage = appUpdateInfo?.message
            }
        } catch (throwable: Throwable) {
            appUpdateError = throwable.message ?: "程序更新检查失败"
            if (showFeedback) {
                errorMessage = appUpdateError
            }
        } finally {
            checkingAppUpdate = false
        }
    }

    fun setAlicianFont(enabled: Boolean) {
        updateUiSettings(uiSettings.copy(alicianFont = enabled))
    }

    fun setDynamicColors(enabled: Boolean) {
        updateUiSettings(uiSettings.copy(dynamicColors = enabled))
    }

    fun updateUiSettings(settings: UiSettings) {
        uiSettings = settings
        alicianFontEnabled = settings.alicianFont
        dynamicColorsEnabled = settings.dynamicColors
        repository.saveUiSettings(settings)
    }

    fun resetUiSettings() {
        updateUiSettings(UiSettings())
        noticeMessage = "UI 设置已恢复默认。"
    }

    private suspend fun refreshDatabaseInfo() {
        databaseInfo = repository.databaseInfo()
    }

    private suspend fun afterDatabaseChanged() {
        dictionaryResult = null
        dictionaryExamples = null
        writingResult = null
        translationResult = null
        globalMatches = emptyList()
        dbTables = repository.getTables()
        dbPage = null
        refreshDatabaseInfo()
    }
}
