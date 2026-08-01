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
import com.meartraep.alician.mobile.data.StudyCard
import com.meartraep.alician.mobile.data.StudyOverview
import com.meartraep.alician.mobile.data.StudyRating
import com.meartraep.alician.mobile.data.StudyRatingPreview
import com.meartraep.alician.mobile.data.StudyRepository
import com.meartraep.alician.mobile.data.StudySettings
import com.meartraep.alician.mobile.data.TranslationResult
import com.meartraep.alician.mobile.data.UiSettings
import com.meartraep.alician.mobile.data.WritingResult
import com.meartraep.alician.mobile.data.WritingSettings
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import org.json.JSONObject
import java.io.File

internal class LatestTranslationRequestGate {
    private var serial = 0L

    fun next(): Long {
        serial += 1
        return serial
    }

    fun invalidate() {
        serial += 1
    }

    fun isCurrent(requestSerial: Long): Boolean = requestSerial == serial
}

data class StudySessionState(
    val queue: List<StudyCard> = emptyList(),
    val plannedDue: Int = 0,
    val plannedNew: Int = 0,
    val answerRevealed: Boolean = false,
    val answerCount: Int = 0,
    val rememberedCount: Int = 0,
    val againCount: Int = 0,
) {
    val currentCard: StudyCard? get() = queue.firstOrNull()
    val isComplete: Boolean get() = queue.isEmpty()
}

class MainViewModel(application: Application) : AndroidViewModel(application) {
    private val repository = PythonRepository(application)
    private val studyRepository = StudyRepository(application, repository.databasePath)
    private var translationJob: Job? = null
    private var studyRefreshJob: Job? = null
    private var studySessionJob: Job? = null
    private var studyReviewJob: Job? = null
    private var studyRefreshSerial = 0L
    private var studyDeckRevision = 0L
    private val translationRequests = LatestTranslationRequestGate()

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
    var semanticExpansionsEnabled by mutableStateOf(repository.semanticExpansionsEnabled)
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
    var translationResultRevision by mutableStateOf(0L)
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

    var studySettings by mutableStateOf(studyRepository.settings)
        private set
    var studyOverview by mutableStateOf(StudyOverview())
        private set
    var studySession by mutableStateOf<StudySessionState?>(null)
        private set
    var studyLoading by mutableStateOf(false)
        private set
    var studyReviewing by mutableStateOf(false)
        private set

    init {
        launchTask("正在初始化词典…") {
            val bootstrap = repository.initialize()
            applyBootstrap(bootstrap)
            studyOverview = studyRepository.loadOverview(studySettings)
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

    fun refreshStudyOverview() {
        if (!ready) return
        val requestSerial = ++studyRefreshSerial
        studyRefreshJob?.cancel()
        studyRefreshJob = viewModelScope.launch {
            if (requestSerial == studyRefreshSerial) studyLoading = true
            try {
                val overview = studyRepository.loadOverview(studySettings)
                if (requestSerial == studyRefreshSerial) {
                    studyOverview = overview
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (throwable: Throwable) {
                if (requestSerial == studyRefreshSerial) {
                    errorMessage = throwable.message ?: "学习数据读取失败"
                }
            } finally {
                if (requestSerial == studyRefreshSerial) {
                    studyLoading = false
                    studyRefreshJob = null
                }
            }
        }
    }

    fun updateStudySettings(settings: StudySettings) {
        val normalized = settings.copy(dailyNewLimit = settings.dailyNewLimit.coerceIn(5, 30))
        if (studySettings == normalized) return
        invalidatePendingStudyDeckWork()
        studySettings = normalized
        studyRepository.saveSettings(normalized)
        refreshStudyOverview()
    }

    fun completeAlphabetLesson() {
        updateStudySettings(studySettings.copy(alphabetCompleted = true))
        noticeMessage = "字符入门已完成，可以开始主动回忆词卡了。"
    }

    fun startStudySession() {
        if (!ready || studyLoading || studyReviewing) return
        val deckRevision = studyDeckRevision
        studySessionJob?.cancel()
        studySessionJob = viewModelScope.launch {
            studyLoading = true
            errorMessage = null
            try {
                val plan = studyRepository.buildSession(studySettings)
                if (deckRevision == studyDeckRevision) {
                    studySession = StudySessionState(
                        queue = plan.cards,
                        plannedDue = plan.dueCount,
                        plannedNew = plan.newCount,
                    )
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (throwable: Throwable) {
                if (deckRevision == studyDeckRevision) {
                    errorMessage = throwable.message ?: "学习牌组读取失败"
                }
            } finally {
                if (deckRevision == studyDeckRevision) studyLoading = false
            }
        }
    }

    fun revealStudyAnswer() {
        studySession = studySession?.copy(answerRevealed = true)
    }

    fun previewStudyRatings(card: StudyCard): List<StudyRatingPreview> =
        studyRepository.ratingPreview(card)

    fun rateStudyCard(rating: StudyRating) {
        if (studyReviewing) return
        val previousState = studySession ?: return
        val card = previousState.currentCard ?: return
        if (!previousState.answerRevealed) return
        val deckRevision = studyDeckRevision
        studyReviewJob?.cancel()
        studyReviewJob = viewModelScope.launch {
            studyReviewing = true
            errorMessage = null
            try {
                studyRepository.review(card, rating)
                if (deckRevision != studyDeckRevision) return@launch
                val remaining = previousState.queue.drop(1)
                val nextState = previousState.copy(
                    queue = remaining,
                    answerRevealed = false,
                    answerCount = previousState.answerCount + 1,
                    rememberedCount = previousState.rememberedCount +
                        if (rating == StudyRating.AGAIN) 0 else 1,
                    againCount = previousState.againCount +
                        if (rating == StudyRating.AGAIN) 1 else 0,
                )
                studySession = nextState
                if (nextState.isComplete) {
                    studyOverview = studyRepository.loadOverview(studySettings)
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (throwable: Throwable) {
                if (deckRevision == studyDeckRevision) {
                    errorMessage = throwable.message ?: "复习记录保存失败"
                }
            } finally {
                if (deckRevision == studyDeckRevision) studyReviewing = false
            }
        }
    }

    fun closeStudySession() {
        if (studyReviewing) return
        studySession = null
        refreshStudyOverview()
    }

    fun resetStudyProgress() {
        if (studyLoading || studyReviewing) return
        invalidateStudyRefresh()
        viewModelScope.launch {
            studyLoading = true
            errorMessage = null
            try {
                studyRepository.resetProgress()
                studySession = null
                studyOverview = studyRepository.loadOverview(studySettings)
                noticeMessage = "学习进度已清空，字符入门记录已保留。"
            } catch (throwable: Throwable) {
                errorMessage = throwable.message ?: "学习进度重置失败"
            } finally {
                studyLoading = false
            }
        }
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
        val requestSerial = translationRequests.next()
        translationJob?.cancel()
        translationResult = null
        translationJob = viewModelScope.launch {
            busyMessage = "正在翻译…"
            errorMessage = null
            try {
                val result = repository.translate(
                    text,
                    direction,
                    semanticExpansionsEnabled,
                )
                if (translationRequests.isCurrent(requestSerial)) {
                    translationResult = result
                    translationResultRevision = requestSerial
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (throwable: Throwable) {
                if (translationRequests.isCurrent(requestSerial)) {
                    errorMessage = throwable.message ?: "翻译失败"
                }
            } finally {
                if (translationRequests.isCurrent(requestSerial)) {
                    busyMessage = null
                }
            }
        }
    }

    private fun invalidateTranslation() {
        translationRequests.invalidate()
        translationJob?.cancel()
        translationJob = null
        translationResult = null
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
            if (affectsStudyDeck(table)) refreshStudyAfterDeckChanged()
            dbPage = repository.getTablePage(table, "", false, dbPage?.offset ?: 0)
            refreshDatabaseInfo()
        }
    }

    fun updateRecord(table: String, id: Long, values: Map<String, String>) {
        launchTask("正在保存记录…") {
            noticeMessage = repository.updateRecord(table, id, values)
            if (affectsStudyDeck(table)) refreshStudyAfterDeckChanged()
            dbPage = repository.getTablePage(table, "", false, dbPage?.offset ?: 0)
            refreshDatabaseInfo()
        }
    }

    fun deleteRecord(table: String, id: Long) {
        launchTask("正在删除记录…") {
            noticeMessage = repository.deleteRecord(table, id)
            if (affectsStudyDeck(table)) refreshStudyAfterDeckChanged()
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
            val studyDeckChanged = selected.any { affectsStudyDeck(it.table) }
            noticeMessage = repository.globalReplace(keyword, replacement, selected)
            if (studyDeckChanged) refreshStudyAfterDeckChanged()
            globalMatches = repository.globalSearch(keyword, false)
            loadDatabase()
        }
    }

    fun updateWordCount() {
        launchTask("正在更新词频与泛度，可能需要片刻…") {
            noticeMessage = repository.updateWordCount()
            refreshStudyAfterDeckChanged()
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

    fun updateSemanticExpansionsEnabled(enabled: Boolean) {
        if (semanticExpansionsEnabled == enabled) return
        semanticExpansionsEnabled = enabled
        invalidateTranslation()
        repository.setSemanticExpansionsEnabled(enabled)
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

    private fun affectsStudyDeck(table: String): Boolean =
        table.equals("dictionary_headwords", ignoreCase = true) ||
            table.equals("phrase", ignoreCase = true)

    private fun invalidateStudyRefresh() {
        studyRefreshSerial += 1
        studyRefreshJob?.cancel()
        studyRefreshJob = null
    }

    private fun invalidatePendingStudyDeckWork(): List<Job> {
        studyDeckRevision += 1
        invalidateStudyRefresh()
        val pendingJobs = listOfNotNull(studySessionJob, studyReviewJob)
        pendingJobs.forEach { it.cancel() }
        studySessionJob = null
        studyReviewJob = null
        studySession = null
        studyLoading = false
        studyReviewing = false
        return pendingJobs
    }

    private suspend fun refreshStudyAfterDeckChanged() {
        val pendingJobs = invalidatePendingStudyDeckWork()
        pendingJobs.forEach { it.cancelAndJoin() }
        studyLoading = true
        try {
            studyRepository.pruneOrphanedProgress()
            studyOverview = studyRepository.loadOverview(studySettings)
        } finally {
            studyLoading = false
        }
    }

    private suspend fun afterDatabaseChanged() {
        refreshStudyAfterDeckChanged()
        dictionaryResult = null
        dictionaryExamples = null
        writingResult = null
        invalidateTranslation()
        globalMatches = emptyList()
        dbTables = repository.getTables()
        dbPage = null
        refreshDatabaseInfo()
    }
}
