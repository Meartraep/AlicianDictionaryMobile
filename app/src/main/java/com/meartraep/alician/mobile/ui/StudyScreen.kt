package com.meartraep.alician.mobile.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.AutoStories
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.EmojiEvents
import androidx.compose.material.icons.outlined.FontDownload
import androidx.compose.material.icons.outlined.Psychology
import androidx.compose.material.icons.outlined.RestartAlt
import androidx.compose.material.icons.outlined.Schedule
import androidx.compose.material.icons.outlined.School
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.LifecycleResumeEffect
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.R
import com.meartraep.alician.mobile.StudySessionState
import com.meartraep.alician.mobile.data.StudyCard
import com.meartraep.alician.mobile.data.StudyContent
import com.meartraep.alician.mobile.data.StudyOrder
import com.meartraep.alician.mobile.data.StudyOverview
import com.meartraep.alician.mobile.data.StudyRating
import com.meartraep.alician.mobile.data.StudyRatingPreview
import com.meartraep.alician.mobile.data.StudyScope
import com.meartraep.alician.mobile.data.StudySettings
import kotlinx.coroutines.delay
import java.util.Calendar
import kotlin.math.roundToInt
import kotlin.random.Random

private val studyDailyLimits = listOf(5, 10, 20, 30)
private const val alphabetQuizSize = 10
private const val alphabetPassScore = 8

@Composable
fun StudyScreen(viewModel: MainViewModel, padding: PaddingValues) {
    var showingAlphabet by rememberSaveable {
        mutableStateOf(!viewModel.studySettings.alphabetCompleted)
    }

    LifecycleResumeEffect(viewModel.ready) {
        if (viewModel.ready) viewModel.refreshStudyOverview()
        onPauseOrDispose { }
    }

    val showingStudyOverview = viewModel.ready &&
        viewModel.studySession == null &&
        viewModel.studySettings.alphabetCompleted &&
        !showingAlphabet
    LaunchedEffect(showingStudyOverview) {
        while (showingStudyOverview) {
            delay(millisecondsUntilNextLocalDay(System.currentTimeMillis()) + 250L)
            viewModel.refreshStudyOverview()
        }
    }
    LaunchedEffect(showingStudyOverview, viewModel.studyOverview.nextDueAtEpochMillis) {
        val dueAt = viewModel.studyOverview.nextDueAtEpochMillis
        if (showingStudyOverview && dueAt != null) {
            delay((dueAt - System.currentTimeMillis()).coerceAtLeast(0L) + 250L)
            viewModel.refreshStudyOverview()
        }
    }

    when {
        viewModel.studySession != null -> StudySession(
            session = viewModel.studySession!!,
            overview = viewModel.studyOverview,
            padding = padding,
            reviewing = viewModel.studyReviewing,
            ratingPreview = viewModel::previewStudyRatings,
            onReveal = viewModel::revealStudyAnswer,
            onRate = viewModel::rateStudyCard,
            onClose = viewModel::closeStudySession,
        )
        showingAlphabet || !viewModel.studySettings.alphabetCompleted -> AlphabetLesson(
            padding = padding,
            canGoBack = viewModel.studySettings.alphabetCompleted,
            onBack = { showingAlphabet = false },
            onComplete = {
                viewModel.completeAlphabetLesson()
                showingAlphabet = false
            },
        )
        else -> StudyOverview(
            settings = viewModel.studySettings,
            overview = viewModel.studyOverview,
            padding = padding,
            ready = viewModel.ready,
            loading = viewModel.studyLoading,
            onSettingsChanged = viewModel::updateStudySettings,
            onStart = viewModel::startStudySession,
            onOpenAlphabet = { showingAlphabet = true },
            onReset = viewModel::resetStudyProgress,
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun StudyOverview(
    settings: StudySettings,
    overview: StudyOverview,
    padding: PaddingValues,
    ready: Boolean,
    loading: Boolean,
    onSettingsChanged: (StudySettings) -> Unit,
    onStart: () -> Unit,
    onOpenAlphabet: () -> Unit,
    onReset: () -> Unit,
) {
    var confirmReset by rememberSaveable { mutableStateOf(false) }
    val availableNow = overview.dueCount + overview.newRemainingToday
    val dailyProgress = if (settings.dailyNewLimit == 0) {
        0f
    } else {
        (overview.newSeenToday.toFloat() / settings.dailyNewLimit).coerceIn(0f, 1f)
    }

    val landscape = isLandscapeLayout()
    LazyVerticalGrid(
        columns = GridCells.Fixed(if (landscape) 2 else 1),
        modifier = Modifier
            .fillMaxSize()
            .testTag("study_overview_list"),
        contentPadding = PaddingValues(
            start = 16.dp,
            end = 16.dp,
            top = padding.calculateTopPadding() + 18.dp,
            bottom = padding.calculateBottomPadding() + 24.dp,
        ),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Text("爱丽丝语背诵", style = MaterialTheme.typography.headlineMedium)
            Text(
                "字符识读 · 主动回忆 · 间隔重复",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        item {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                ),
            ) {
                Column(
                    modifier = Modifier.padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Outlined.Psychology, contentDescription = null)
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text("今日学习", style = MaterialTheme.typography.titleLarge)
                            Text(
                                when {
                                    !ready -> "正在准备本地词典…"
                                    availableNow == 0 -> nextDueMessage(overview)
                                    overview.dueCount > 0 ->
                                        "先完成 ${overview.dueCount} 张到期复习，再学新词。"
                                    else -> "今天可以学习 ${overview.newRemainingToday} 张新卡。"
                                },
                                style = MaterialTheme.typography.bodyMedium,
                            )
                        }
                    }
                    LinearProgressIndicator(
                        progress = { dailyProgress },
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Text(
                        "今日新卡 ${overview.newSeenToday} / ${settings.dailyNewLimit}",
                        style = MaterialTheme.typography.labelMedium,
                    )
                    Button(
                        onClick = onStart,
                        enabled = ready && !loading,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("study_start_session"),
                    ) {
                        Icon(Icons.Outlined.School, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            if (availableNow == 0) "查看今日结果" else "开始 · $availableNow 张",
                        )
                    }
                }
            }
        }

        item {
            MetricRow(
                "到期复习" to overview.dueCount.toString(),
                "已掌握" to overview.masteredCount.toString(),
                "连续学习" to "${overview.streakDays} 天",
            )
        }

        item(span = { GridItemSpan(maxLineSpan) }) {
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
                ),
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Outlined.EmojiEvents,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                        )
                        Spacer(Modifier.width(10.dp))
                        Text("学习进度", style = MaterialTheme.typography.titleMedium)
                    }
                    Text(
                        "已接触 ${overview.learnedCount} / ${overview.totalCards} 张 · " +
                            "学习中 ${overview.learningCount} 张 · 未学 ${overview.unseenCount} 张",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        if (overview.reviewedToday == 0) {
                            "今天还没有评分记录。"
                        } else {
                            "今日回忆 ${overview.reviewedToday} 次 · 记住率 " +
                                "${(overview.retentionToday * 100).roundToInt()}%"
                        },
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        item { SectionHeader("牌组范围", "词组会和单词使用同一套复习计划") }
        item {
            SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                listOf(
                    StudyContent.ALL to "全部",
                    StudyContent.WORDS to "单词",
                    StudyContent.PHRASES to "词组",
                ).forEachIndexed { index, option ->
                    SegmentedButton(
                        selected = settings.content == option.first,
                        onClick = {
                            onSettingsChanged(settings.copy(content = option.first))
                        },
                        shape = SegmentedButtonDefaults.itemShape(index, 3),
                        modifier = Modifier.weight(1f),
                        label = { Text(option.second) },
                    )
                }
            }
        }

        item { SectionHeader("新卡顺序", "到期复习始终优先；这里仅控制尚未学过的卡片") }
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                listOf(
                    StudyOrder.FREQUENCY to "高词频 / 泛度优先",
                    StudyOrder.ALPHABETICAL to "字母顺序",
                    StudyOrder.RANDOM to "乱序",
                ).forEach { option ->
                    FilterChip(
                        selected = settings.order == option.first,
                        onClick = {
                            onSettingsChanged(settings.copy(order = option.first))
                        },
                        label = { Text(option.second) },
                    )
                }
            }
        }

        item { SectionHeader("每日新卡", "稳步增加比一次塞入大量生词更利于长期记忆") }
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                studyDailyLimits.forEach { limit ->
                    FilterChip(
                        selected = settings.dailyNewLimit == limit,
                        onClick = {
                            onSettingsChanged(settings.copy(dailyNewLimit = limit))
                        },
                        modifier = Modifier.weight(1f),
                        label = { Text(limit.toString()) },
                    )
                }
            }
        }

        item {
            InfoBanner(
                "先回忆再翻面，并按真实难度评分。新卡会在数分钟内加固，" +
                    "稳定记住后间隔逐步扩展；遗忘卡会自动进入重学。",
            )
        }

        item {
            OutlinedButton(
                onClick = onOpenAlphabet,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Outlined.FontDownload, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("重新练习爱丽丝语字符")
            }
        }
        item {
            TextButton(
                onClick = { confirmReset = true },
                enabled = !loading,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Outlined.RestartAlt, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("清空学习进度")
            }
        }
    }

    if (confirmReset) {
        ConfirmActionDialog(
            title = "清空学习进度？",
            message = "所有词卡的间隔、评分与连续学习记录都会删除。字符入门完成状态会保留。",
            confirmText = "确认清空",
            destructive = true,
            onConfirm = {
                confirmReset = false
                onReset()
            },
            onDismiss = { confirmReset = false },
        )
    }
}

@Composable
private fun StudySession(
    session: StudySessionState,
    overview: StudyOverview,
    padding: PaddingValues,
    reviewing: Boolean,
    ratingPreview: (StudyCard) -> List<StudyRatingPreview>,
    onReveal: () -> Unit,
    onRate: (StudyRating) -> Unit,
    onClose: () -> Unit,
) {
    BackHandler(onBack = onClose)
    if (session.isComplete) {
        StudySessionComplete(session, overview, padding, onClose)
        return
    }

    val card = session.currentCard ?: return
    var showTranscription by rememberSaveable(card.item.id) { mutableStateOf(false) }
    val completedFraction = session.answerCount.toFloat() /
        (session.answerCount + session.queue.size).coerceAtLeast(1)
    val previews = remember(card, session.answerRevealed) {
        if (session.answerRevealed) ratingPreview(card) else emptyList()
    }
    val alicianFont = FontFamily(Font(R.font.alician_regular))

    val landscape = isLandscapeLayout()
    LazyVerticalGrid(
        columns = GridCells.Fixed(if (landscape) 2 else 1),
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 16.dp,
            end = 16.dp,
            top = padding.calculateTopPadding() + 8.dp,
            bottom = padding.calculateBottomPadding() + 24.dp,
        ),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onClose) {
                    Icon(
                        Icons.AutoMirrored.Outlined.ArrowBack,
                        contentDescription = "退出本轮学习",
                    )
                }
                Spacer(Modifier.width(4.dp))
                Column(Modifier.weight(1f)) {
                    Text("主动回忆", style = MaterialTheme.typography.headlineSmall)
                    Text(
                        "剩余 ${session.queue.size} 张 · 已评分 ${session.answerCount} 次",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        item(span = { GridItemSpan(maxLineSpan) }) {
            LinearProgressIndicator(
                progress = { completedFraction },
                modifier = Modifier.fillMaxWidth(),
            )
        }
        item(
            span = {
                GridItemSpan(
                    if (landscape && session.answerRevealed) 1 else maxLineSpan,
                )
            },
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
                ),
            ) {
                Column(
                    modifier = Modifier.padding(horizontal = 20.dp, vertical = 24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(14.dp),
                ) {
                    Surface(
                        color = MaterialTheme.colorScheme.secondaryContainer,
                        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
                        shape = MaterialTheme.shapes.small,
                    ) {
                        Text(
                            listOfNotNull(
                                if (card.item.scope == StudyScope.PHRASE) "词组" else "单词",
                                if (card.isNew) "新卡" else phaseLabel(card),
                            ).joinToString(" · "),
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                            style = MaterialTheme.typography.labelLarge,
                        )
                    }
                    Text(
                        alicianDisplayText(card.item.text, alicianFont),
                        modifier = Modifier.fillMaxWidth(),
                        style = MaterialTheme.typography.displaySmall,
                        color = MaterialTheme.colorScheme.primary,
                        textAlign = TextAlign.Center,
                    )
                    if (showTranscription) {
                        Text(
                            "拉丁转写：${card.item.text}",
                            style = MaterialTheme.typography.titleMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            textAlign = TextAlign.Center,
                        )
                    } else {
                        TextButton(onClick = { showTranscription = true }) {
                            Icon(Icons.Outlined.Visibility, contentDescription = null)
                            Spacer(Modifier.width(6.dp))
                            Text("查看拉丁转写")
                        }
                    }

                    if (!session.answerRevealed) {
                        Text(
                            "先在心中说出中文含义；想清楚后再揭晓。",
                            style = MaterialTheme.typography.bodyLarge,
                            textAlign = TextAlign.Center,
                        )
                        Spacer(Modifier.height(6.dp))
                        Button(
                            onClick = onReveal,
                            modifier = Modifier
                                .fillMaxWidth()
                                .testTag("study_reveal_answer"),
                        ) {
                            Text("显示释义")
                        }
                    } else {
                        HorizontalDivider()
                        Text(
                            card.item.explanation,
                            modifier = Modifier.fillMaxWidth(),
                            style = MaterialTheme.typography.titleLarge,
                            textAlign = TextAlign.Center,
                        )
                        if (card.item.wordClass.isNotBlank()) {
                            Text(
                                "词性 ${card.item.wordClass}",
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.secondary,
                            )
                        }
                        Text(
                            "词频 ${card.item.frequency} · 泛度 ${card.item.variety}",
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }

        if (session.answerRevealed) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text(
                        "你的回忆有多稳？",
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        "按真实感受评分，按钮下方是预计下次出现时间。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    RatingButtons(
                        previews = previews,
                        enabled = !reviewing,
                        onRate = onRate,
                    )
                }
            }
        }
    }
}

@Composable
private fun RatingButtons(
    previews: List<StudyRatingPreview>,
    enabled: Boolean,
    onRate: (StudyRating) -> Unit,
) {
    val previewsByRating = previews.associateBy(StudyRatingPreview::rating)
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            RatingButton(
                rating = StudyRating.AGAIN,
                label = "忘记",
                preview = previewsByRating[StudyRating.AGAIN],
                enabled = enabled,
                primary = false,
                modifier = Modifier.weight(1f),
                onRate = onRate,
            )
            RatingButton(
                rating = StudyRating.HARD,
                label = "困难",
                preview = previewsByRating[StudyRating.HARD],
                enabled = enabled,
                primary = false,
                modifier = Modifier.weight(1f),
                onRate = onRate,
            )
        }
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            RatingButton(
                rating = StudyRating.GOOD,
                label = "记得",
                preview = previewsByRating[StudyRating.GOOD],
                enabled = enabled,
                primary = true,
                modifier = Modifier.weight(1f),
                onRate = onRate,
            )
            RatingButton(
                rating = StudyRating.EASY,
                label = "很熟",
                preview = previewsByRating[StudyRating.EASY],
                enabled = enabled,
                primary = true,
                modifier = Modifier.weight(1f),
                onRate = onRate,
            )
        }
    }
}

@Composable
private fun RatingButton(
    rating: StudyRating,
    label: String,
    preview: StudyRatingPreview?,
    enabled: Boolean,
    primary: Boolean,
    modifier: Modifier,
    onRate: (StudyRating) -> Unit,
) {
    val content: @Composable () -> Unit = {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(label, fontWeight = FontWeight.SemiBold)
            Text(
                preview?.let { formatInterval(it.intervalMillis) }.orEmpty(),
                style = MaterialTheme.typography.labelSmall,
            )
        }
    }
    if (primary) {
        FilledTonalButton(
            onClick = { onRate(rating) },
            enabled = enabled,
            modifier = modifier.testTag("study_rating_${rating.name}"),
            content = { content() },
        )
    } else {
        OutlinedButton(
            onClick = { onRate(rating) },
            enabled = enabled,
            modifier = modifier.testTag("study_rating_${rating.name}"),
            content = { content() },
        )
    }
}

@Composable
private fun StudySessionComplete(
    session: StudySessionState,
    overview: StudyOverview,
    padding: PaddingValues,
    onClose: () -> Unit,
) {
    val rememberedRate = if (session.answerCount == 0) 0 else {
        session.rememberedCount * 100 / session.answerCount
    }
    val landscape = isLandscapeLayout()
    LazyVerticalGrid(
        columns = GridCells.Fixed(if (landscape) 2 else 1),
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 16.dp,
            end = 16.dp,
            top = padding.calculateTopPadding() + 28.dp,
            bottom = padding.calculateBottomPadding() + 28.dp,
        ),
        horizontalArrangement = Arrangement.spacedBy(18.dp),
        verticalArrangement = Arrangement.spacedBy(18.dp),
    ) {
        item {
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(16.dp),
            ) {
                Icon(
                    Icons.Outlined.CheckCircle,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
                Text(
                    if (session.answerCount == 0) "今天的任务已清空" else "本轮完成",
                    style = MaterialTheme.typography.headlineMedium,
                    textAlign = TextAlign.Center,
                )
                Text(
                    if (session.answerCount == 0) {
                        nextDueMessage(overview)
                    } else {
                        "大脑在将主动回忆转为长期记忆。下一次按计划回来即可。"
                    },
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    textAlign = TextAlign.Center,
                )
            }
        }
        item {
            Column(verticalArrangement = Arrangement.spacedBy(18.dp)) {
                if (session.answerCount > 0) {
                    MetricRow(
                        "评分次数" to session.answerCount.toString(),
                        "记住率" to "$rememberedRate%",
                        "再次学习" to session.againCount.toString(),
                    )
                }
                Button(onClick = onClose, modifier = Modifier.fillMaxWidth()) {
                    Text("返回学习总览")
                }
            }
        }
    }
}

@Composable
private fun AlphabetLesson(
    padding: PaddingValues,
    canGoBack: Boolean,
    onBack: () -> Unit,
    onComplete: () -> Unit,
) {
    var quizSeed by rememberSaveable { mutableStateOf<Long?>(null) }
    val questions = remember(quizSeed) {
        quizSeed?.let(::buildAlphabetQuiz).orEmpty()
    }
    var questionIndex by rememberSaveable { mutableIntStateOf(0) }
    var correctCount by rememberSaveable { mutableIntStateOf(0) }
    var selectedAnswerText by rememberSaveable { mutableStateOf<String?>(null) }
    var quizFinished by rememberSaveable { mutableStateOf(false) }
    val selectedAnswer = selectedAnswerText?.singleOrNull()

    BackHandler(enabled = canGoBack, onBack = onBack)

    fun restartQuiz() {
        quizSeed = System.nanoTime().takeUnless { it == 0L } ?: 1L
        questionIndex = 0
        correctCount = 0
        selectedAnswerText = null
        quizFinished = false
    }

    if (questions.isNotEmpty()) {
        AlphabetQuiz(
            questions = questions,
            questionIndex = questionIndex,
            correctCount = correctCount,
            selectedAnswer = selectedAnswer,
            finished = quizFinished,
            padding = padding,
            canGoBack = canGoBack,
            onBack = if (canGoBack) onBack else {
                {
                    quizSeed = null
                    questionIndex = 0
                    correctCount = 0
                    selectedAnswerText = null
                    quizFinished = false
                }
            },
            onAnswer = { answer ->
                if (selectedAnswer == null) {
                    selectedAnswerText = answer.toString()
                    if (answer == questions[questionIndex].letter) correctCount += 1
                }
            },
            onNext = {
                if (questionIndex == questions.lastIndex) {
                    quizFinished = true
                } else {
                    questionIndex += 1
                    selectedAnswerText = null
                }
            },
            onRetry = { restartQuiz() },
            onComplete = onComplete,
        )
        return
    }

    val alicianFont = FontFamily(Font(R.font.alician_regular))
    val landscape = isLandscapeLayout()
    LazyVerticalGrid(
        columns = GridCells.Fixed(if (landscape) 2 else 1),
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 16.dp,
            end = 16.dp,
            top = padding.calculateTopPadding() + 8.dp,
            bottom = padding.calculateBottomPadding() + 24.dp,
        ),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                if (canGoBack) {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Outlined.ArrowBack,
                            contentDescription = "返回学习总览",
                        )
                    }
                    Spacer(Modifier.width(4.dp))
                }
                Column {
                    Text("先认识爱丽丝语字符", style = MaterialTheme.typography.headlineMedium)
                    Text(
                        "理解字形后再背词，避免把识字困难误判成遗忘。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        item {
            InfoBanner(
                "爱丽丝语专用字体改变的是 A–Z 的字形，底层仍是普通拉丁字母。" +
                    "你可以用系统键盘输入，字典排序也按拉丁转写进行。",
            )
        }

        item {
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                ),
            ) {
                Column(
                    modifier = Modifier.padding(18.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    Text("同一个词，两种显示", style = MaterialTheme.typography.titleLarge)
                    Text("普通转写　Shelista", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "Shelista",
                        fontFamily = alicianFont,
                        fontSize = 34.sp,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Text(
                        "学习卡默认显示专用字形；需要时可点“查看拉丁转写”。",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
        }

        item(span = { GridItemSpan(maxLineSpan) }) {
            SectionHeader("字符对照", "上方是键盘字母，下方是爱丽丝语字形")
        }
        item { AlphabetGrid(alicianFont) }

        item {
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
                ),
            ) {
                Column(
                    modifier = Modifier.padding(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.Outlined.AutoStories,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.primary,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text("识字小测", style = MaterialTheme.typography.titleMedium)
                    }
                    Text(
                        "随机辨认 $alphabetQuizSize 个字形，答对 $alphabetPassScore 个即可进入词卡。" +
                            "不要求记住字母名称或额外发音规则。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Button(
                        onClick = { restartQuiz() },
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("alphabet_start_quiz"),
                    ) {
                        Text("开始字符小测")
                    }
                }
            }
        }
    }
}

@Composable
private fun AlphabetGrid(alicianFont: FontFamily) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        ('A'..'Z').toList().chunked(5).forEach { rowLetters ->
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                rowLetters.forEach { letter ->
                    Surface(
                        modifier = Modifier.weight(1f),
                        color = MaterialTheme.colorScheme.surfaceContainer,
                        shape = MaterialTheme.shapes.medium,
                    ) {
                        Column(
                            modifier = Modifier.padding(vertical = 10.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Text(
                                "$letter ${letter.lowercaseChar()}",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                "$letter${letter.lowercaseChar()}",
                                fontFamily = alicianFont,
                                fontSize = 27.sp,
                                color = MaterialTheme.colorScheme.primary,
                            )
                        }
                    }
                }
                repeat(5 - rowLetters.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun AlphabetQuiz(
    questions: List<AlphabetQuestion>,
    questionIndex: Int,
    correctCount: Int,
    selectedAnswer: Char?,
    finished: Boolean,
    padding: PaddingValues,
    canGoBack: Boolean,
    onBack: () -> Unit,
    onAnswer: (Char) -> Unit,
    onNext: () -> Unit,
    onRetry: () -> Unit,
    onComplete: () -> Unit,
) {
    BackHandler(onBack = onBack)
    val alicianFont = FontFamily(Font(R.font.alician_regular))
    val question = questions[questionIndex]
    val passed = correctCount >= alphabetPassScore

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 16.dp,
            end = 16.dp,
            top = padding.calculateTopPadding() + 8.dp,
            bottom = padding.calculateBottomPadding() + 24.dp,
        ),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(
                        Icons.AutoMirrored.Outlined.ArrowBack,
                        contentDescription = if (canGoBack) "返回学习总览" else "返回字符表",
                    )
                }
                Spacer(Modifier.width(4.dp))
                Column(Modifier.weight(1f)) {
                    Text("字符识读", style = MaterialTheme.typography.headlineSmall)
                    Text(
                        if (finished) "测验结果" else "第 ${questionIndex + 1} / ${questions.size} 题",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        item {
            LinearProgressIndicator(
                progress = {
                    if (finished) 1f else questionIndex.toFloat() / questions.size
                },
                modifier = Modifier.fillMaxWidth(),
            )
        }

        if (finished) {
            item {
                Icon(
                    if (passed) Icons.Outlined.CheckCircle else Icons.Outlined.RestartAlt,
                    contentDescription = null,
                    tint = if (passed) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.tertiary
                    },
                )
            }
            item {
                Text(
                    "$correctCount / ${questions.size}",
                    style = MaterialTheme.typography.displayMedium,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            item {
                Text(
                    if (passed) {
                        "字符基础已经够用了。遇到生疏字形时，词卡仍可随时显示拉丁转写。"
                    } else {
                        "再看一遍字符对照，然后换一组题巩固；重复辨认会比死记更牢。"
                    },
                    style = MaterialTheme.typography.bodyLarge,
                    textAlign = TextAlign.Center,
                )
            }
            item {
                Button(
                    onClick = if (passed) onComplete else onRetry,
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag(if (passed) "alphabet_complete" else "alphabet_retry"),
                ) {
                    Text(if (passed) "进入词卡学习" else "换一组再试")
                }
            }
        } else {
            item {
                Text(
                    "这个爱丽丝语字形对应哪个键盘字母？",
                    style = MaterialTheme.typography.titleMedium,
                    textAlign = TextAlign.Center,
                )
            }
            item {
                Card(
                    modifier = Modifier.testTag("alphabet_question_${question.letter}"),
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.primaryContainer,
                    ),
                ) {
                    Text(
                        question.glyph.toString(),
                        modifier = Modifier
                            .padding(horizontal = 52.dp, vertical = 30.dp)
                            .clearAndSetSemantics {
                                contentDescription =
                                    "爱丽丝语视觉字形，请从下方选择对应的键盘字母"
                            },
                        fontFamily = alicianFont,
                        fontSize = 72.sp,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
            }
            item {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    question.options.chunked(2).forEach { options ->
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            options.forEach { option ->
                                val isCorrect = option == question.letter
                                val wasSelected = selectedAnswer == option
                                val label = when {
                                    selectedAnswer != null && isCorrect -> "$option　✓"
                                    wasSelected -> "$option　×"
                                    else -> option.toString()
                                }
                                OutlinedButton(
                                    onClick = { onAnswer(option) },
                                    enabled = selectedAnswer == null,
                                    modifier = Modifier
                                        .weight(1f)
                                        .testTag("alphabet_option_$option"),
                                ) { Text(label) }
                            }
                        }
                    }
                }
            }
            if (selectedAnswer != null) {
                item {
                    Text(
                        if (selectedAnswer == question.letter) {
                            "正确，这是 ${question.letter}。"
                        } else {
                            "这是 ${question.letter}；把字形和键位再配对一次。"
                        },
                        color = if (selectedAnswer == question.letter) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.error
                        },
                        style = MaterialTheme.typography.bodyLarge,
                    )
                }
                item {
                    Button(
                        onClick = onNext,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag("alphabet_next"),
                    ) {
                        Text(if (questionIndex == questions.lastIndex) "查看结果" else "下一题")
                    }
                }
            }
        }
    }
}

internal data class AlphabetQuestion(
    val glyph: Char,
    val letter: Char,
    val options: List<Char>,
)

internal fun buildAlphabetQuiz(seed: Long): List<AlphabetQuestion> {
    val alphabet = ('A'..'Z').toList()
    val random = Random(seed)
    return alphabet.shuffled(random).take(alphabetQuizSize).mapIndexed { index, target ->
        val alternatives = alphabet.filter { it != target }.shuffled(random).take(3)
        AlphabetQuestion(
            glyph = if (index % 2 == 0) target else target.lowercaseChar(),
            letter = target,
            options = (alternatives + target).shuffled(random),
        )
    }
}

internal fun millisecondsUntilNextLocalDay(nowEpochMillis: Long): Long {
    val nextDay = Calendar.getInstance().apply {
        timeInMillis = nowEpochMillis
        add(Calendar.DAY_OF_YEAR, 1)
        set(Calendar.HOUR_OF_DAY, 0)
        set(Calendar.MINUTE, 0)
        set(Calendar.SECOND, 0)
        set(Calendar.MILLISECOND, 0)
    }
    return (nextDay.timeInMillis - nowEpochMillis).coerceAtLeast(1L)
}

private fun alicianDisplayText(text: String, alicianFont: FontFamily): AnnotatedString =
    buildAnnotatedString {
        append(text)
        Regex("[A-Za-z]+").findAll(text).forEach { match ->
            addStyle(
                style = SpanStyle(fontFamily = alicianFont),
                start = match.range.first,
                end = match.range.last + 1,
            )
        }
    }

private fun phaseLabel(card: StudyCard): String = when (card.progress?.phase) {
    com.meartraep.alician.mobile.data.StudyPhase.LEARNING -> "学习中"
    com.meartraep.alician.mobile.data.StudyPhase.RELEARNING -> "重学"
    com.meartraep.alician.mobile.data.StudyPhase.REVIEW -> "复习"
    null -> "新卡"
}

private fun nextDueMessage(overview: StudyOverview): String {
    val dueAt = overview.nextDueAtEpochMillis ?: return "暂无待学习卡片。"
    val remaining = (dueAt - System.currentTimeMillis()).coerceAtLeast(0L)
    return "本轮已完成，下次复习约在 ${formatInterval(remaining)}后。"
}

internal fun formatInterval(intervalMillis: Long): String {
    val minutes = (intervalMillis / 60_000.0).roundToInt().coerceAtLeast(1)
    return when {
        minutes < 60 -> "${minutes}分钟"
        minutes < 24 * 60 -> "${(minutes / 60.0).roundToInt()}小时"
        minutes < 30 * 24 * 60 -> "${(minutes / (24.0 * 60)).roundToInt()}天"
        minutes < 365 * 24 * 60 -> "${(minutes / (30.0 * 24 * 60)).roundToInt()}个月"
        else -> "${(minutes / (365.0 * 24 * 60)).roundToInt()}年"
    }
}
