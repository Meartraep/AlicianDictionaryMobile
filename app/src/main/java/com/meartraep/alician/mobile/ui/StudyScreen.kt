package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.EmojiEvents
import androidx.compose.material.icons.outlined.FontDownload
import androidx.compose.material.icons.outlined.Psychology
import androidx.compose.material.icons.outlined.RestartAlt
import androidx.compose.material.icons.outlined.School
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.LifecycleResumeEffect
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.data.StudyContent
import com.meartraep.alician.mobile.data.StudyOrder
import com.meartraep.alician.mobile.data.StudyOverview
import com.meartraep.alician.mobile.data.StudySettings
import kotlinx.coroutines.delay
import java.util.Calendar
import kotlin.math.roundToInt

private val studyDailyLimits = listOf(5, 10, 20, 30)

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

internal fun nextDueMessage(overview: StudyOverview): String {
    val dueAt = overview.nextDueAtEpochMillis ?: return "暂无待学习卡片。"
    val remaining = (dueAt - System.currentTimeMillis()).coerceAtLeast(0L)
    return "本轮已完成，下次复习约在 ${formatInterval(remaining)}后。"
}
