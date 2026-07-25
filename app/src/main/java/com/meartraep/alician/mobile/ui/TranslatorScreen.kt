package com.meartraep.alician.mobile.ui

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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ArrowDownward
import androidx.compose.material.icons.outlined.ArrowUpward
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.SwapVert
import androidx.compose.material.icons.outlined.Translate
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.R
import com.meartraep.alician.mobile.data.TranslationResult
import com.meartraep.alician.mobile.data.TranslationToken

private val directionOptions = listOf(
    "auto" to "自动",
    "zh_to_alician" to "中 → A",
    "alician_to_zh" to "A → 中",
)

@Composable
fun TranslatorScreen(viewModel: MainViewModel, padding: PaddingValues) {
    var input by rememberSaveable { mutableStateOf("") }
    var direction by rememberSaveable { mutableStateOf("auto") }
    val alicianFont = if (viewModel.alicianFontEnabled) {
        FontFamily(Font(R.font.alician_regular))
    } else {
        FontFamily.Default
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 16.dp,
            end = 16.dp,
            top = padding.calculateTopPadding() + 18.dp,
            bottom = padding.calculateBottomPadding() + 24.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text("双向翻译器", style = MaterialTheme.typography.headlineMedium)
            Text(
                "Lite 词典匹配模式 · 语序规则与候选释义均来自本地语料",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                directionOptions.forEach { option ->
                    FilterChip(
                        selected = direction == option.first,
                        onClick = { direction = option.first },
                        label = { Text(option.second) },
                    )
                }
                if (direction != "auto") {
                    FilterChip(
                        selected = false,
                        onClick = {
                            direction = if (direction == "zh_to_alician") {
                                "alician_to_zh"
                            } else {
                                "zh_to_alician"
                            }
                        },
                        label = { Text("切换") },
                        leadingIcon = { Icon(Icons.Outlined.SwapVert, contentDescription = null) },
                    )
                }
            }
        }
        item {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(180.dp),
                label = { Text("原文") },
                placeholder = { Text("输入中文自然语言，或输入爱丽丝语文本…") },
                textStyle = MaterialTheme.typography.bodyLarge.copy(fontFamily = alicianFont),
            )
        }
        item {
            Button(
                onClick = { viewModel.translate(input, direction) },
                modifier = Modifier.fillMaxWidth(),
                enabled = input.isNotBlank(),
            ) {
                Icon(Icons.Outlined.Translate, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("翻译")
            }
        }

        viewModel.translationResult?.let { result ->
            item {
                TranslatorResultCard(result, alicianFont)
            }
            item {
                MetricRow(
                    "精确" to result.exact.toString(),
                    "近似" to result.approximate.toString(),
                    "未知" to result.unknown.toString(),
                )
            }
            item {
                SectionHeader("单词明细与语序", "选择候选释义；用上下箭头调整语义词顺序")
            }
            item {
                EditableTokenList(result, alicianFont)
            }
        } ?: item {
            EmptyState(
                icon = Icons.Outlined.Translate,
                title = "输入内容开始翻译",
                detail = "自动模式会根据是否包含中文字符判断方向。",
            )
        }
    }
}

@Composable
private fun TranslatorResultCard(
    result: TranslationResult,
    alicianFont: FontFamily,
) {
    val clipboard = LocalClipboard.current
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
        ),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Text(
                    "翻译结果",
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.titleSmall,
                )
                IconButton(
                    onClick = {
                        clipboard.nativeClipboard.setPrimaryClip(
                            android.content.ClipData.newPlainText("translation", result.resultText),
                        )
                    },
                ) {
                    Icon(Icons.Outlined.ContentCopy, contentDescription = "复制结果")
                }
            }
            SelectionContainer {
                Text(
                    result.resultText,
                    fontFamily = alicianFont,
                    style = MaterialTheme.typography.headlineSmall,
                )
            }
            Spacer(Modifier.height(8.dp))
            Text(
                result.message,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
        }
    }
}

@Composable
private fun EditableTokenList(
    result: TranslationResult,
    alicianFont: FontFamily,
) {
    var tokens by remember(result) { mutableStateOf(result.tokens) }
    var customized by remember(result) { mutableStateOf(false) }
    val customizedText = if (customized) tokens.joinToString("") { it.target } else result.resultText

    if (customized) {
        Card(
            colors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.secondaryContainer,
            ),
        ) {
            Column(Modifier.padding(16.dp)) {
                Text("调整后的结果", style = MaterialTheme.typography.labelLarge)
                Spacer(Modifier.height(6.dp))
                SelectionContainer {
                    Text(
                        customizedText,
                        fontFamily = alicianFont,
                        style = MaterialTheme.typography.titleLarge,
                    )
                }
            }
        }
        Spacer(Modifier.height(10.dp))
    }

    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        tokens.forEachIndexed { index, token ->
            TranslationTokenCard(
                token = token,
                alicianFont = alicianFont,
                canMoveUp = index > 0,
                canMoveDown = index < tokens.lastIndex,
                onMoveUp = {
                    tokens = tokens.toMutableList().also {
                        val moved = it.removeAt(index)
                        it.add(index - 1, moved)
                    }
                    customized = true
                },
                onMoveDown = {
                    tokens = tokens.toMutableList().also {
                        val moved = it.removeAt(index)
                        it.add(index + 1, moved)
                    }
                    customized = true
                },
                onAlternative = { target ->
                    tokens = tokens.toMutableList().also {
                        it[index] = it[index].copy(target = target)
                    }
                    customized = true
                },
            )
        }
    }
}

@Composable
private fun TranslationTokenCard(
    token: TranslationToken,
    alicianFont: FontFamily,
    canMoveUp: Boolean,
    canMoveDown: Boolean,
    onMoveUp: () -> Unit,
    onMoveDown: () -> Unit,
    onAlternative: (String) -> Unit,
) {
    val container = when (token.status) {
        "exact" -> MaterialTheme.colorScheme.primaryContainer
        "approximate" -> MaterialTheme.colorScheme.tertiaryContainer
        else -> MaterialTheme.colorScheme.errorContainer
    }
    Card(colors = CardDefaults.cardColors(containerColor = container)) {
        Column(Modifier.padding(14.dp)) {
            Row(Modifier.fillMaxWidth()) {
                Column(Modifier.weight(1f)) {
                    Text(
                        "${token.source} → ${token.target}",
                        fontFamily = alicianFont,
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        listOf(token.wordClass, token.method)
                            .filter(String::isNotBlank)
                            .joinToString(" · "),
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
                IconButton(onClick = onMoveUp, enabled = canMoveUp) {
                    Icon(Icons.Outlined.ArrowUpward, contentDescription = "上移")
                }
                IconButton(onClick = onMoveDown, enabled = canMoveDown) {
                    Icon(Icons.Outlined.ArrowDownward, contentDescription = "下移")
                }
            }
            if (token.explanation.isNotBlank()) {
                Text(token.explanation, style = MaterialTheme.typography.bodyMedium)
            }
            if (token.note.isNotBlank()) {
                Spacer(Modifier.height(5.dp))
                Text(
                    token.note,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (token.alternatives.size > 1) {
                Spacer(Modifier.height(8.dp))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState()),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    token.alternatives.forEach { alternative ->
                        AssistChip(
                            onClick = { onAlternative(alternative.target) },
                            label = {
                                Text(
                                    alternative.target,
                                    fontFamily = alicianFont,
                                )
                            },
                        )
                    }
                }
            }
        }
    }
}
