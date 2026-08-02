package com.meartraep.alician.mobile.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.AutoStories
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.RestartAlt
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.meartraep.alician.mobile.R
import kotlin.random.Random

private const val alphabetQuizSize = 10
private const val alphabetPassScore = 8

@Composable
internal fun AlphabetLesson(
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
