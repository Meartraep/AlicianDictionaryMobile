package com.meartraep.alician.mobile.ui

import androidx.activity.compose.BackHandler
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
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.R
import com.meartraep.alician.mobile.StudySessionState
import com.meartraep.alician.mobile.data.StudyCard
import com.meartraep.alician.mobile.data.StudyOverview
import com.meartraep.alician.mobile.data.StudyRating
import com.meartraep.alician.mobile.data.StudyRatingPreview
import com.meartraep.alician.mobile.data.StudyScope
import kotlin.math.roundToInt

@Composable
internal fun StudySession(
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
