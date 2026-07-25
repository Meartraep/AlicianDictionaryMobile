package com.meartraep.alician.mobile.ui

import android.content.Context
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CheckCircle
import androidx.compose.material.icons.outlined.Description
import androidx.compose.material.icons.outlined.Download
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.UploadFile
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.R
import com.meartraep.alician.mobile.data.LookupResult
import com.meartraep.alician.mobile.data.WritingIssue
import com.meartraep.alician.mobile.data.WritingResult
import com.meartraep.alician.mobile.data.WritingSettings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun WritingScreen(viewModel: MainViewModel, padding: PaddingValues) {
    var text by rememberSaveable { mutableStateOf("") }
    var showSettings by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val alicianFont = if (viewModel.alicianFontEnabled) {
        FontFamily(Font(R.font.alician_regular))
    } else {
        FontFamily.Default
    }

    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri ->
        if (uri != null) {
            scope.launch {
                text = withContext(Dispatchers.IO) {
                    context.contentResolver.openInputStream(uri)?.bufferedReader()?.use {
                        it.readText()
                    }.orEmpty()
                }
            }
        }
    }
    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("text/plain"),
    ) { uri ->
        if (uri != null) {
            scope.launch(Dispatchers.IO) {
                context.contentResolver.openOutputStream(uri, "w")?.bufferedWriter()?.use {
                    it.write(text)
                }
            }
        }
    }

    LaunchedEffect(text, viewModel.writingSettings) {
        delay(550)
        viewModel.checkWritingSilently(text)
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
            Text("写作助手", style = MaterialTheme.typography.headlineMedium)
            Text(
                "自动识别拼写错误与低频词，点按问题项可查询释义",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    onClick = { importLauncher.launch(arrayOf("text/plain", "text/*")) },
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Outlined.UploadFile, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("导入")
                }
                OutlinedButton(
                    onClick = { exportLauncher.launch("alician-writing.txt") },
                    modifier = Modifier.weight(1f),
                    enabled = text.isNotEmpty(),
                ) {
                    Icon(Icons.Outlined.Download, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("导出")
                }
                OutlinedButton(
                    onClick = { showSettings = true },
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Outlined.Settings, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("设置")
                }
            }
        }
        item {
            OutlinedTextField(
                value = text,
                onValueChange = { text = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .height(250.dp),
                label = { Text("爱丽丝语文本") },
                placeholder = { Text("输入或导入文本；停顿片刻后自动检查…") },
                textStyle = MaterialTheme.typography.bodyLarge.copy(fontFamily = alicianFont),
            )
        }
        item {
            Button(
                onClick = { viewModel.checkWriting(text) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Outlined.CheckCircle, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("立即检查")
            }
        }

        viewModel.writingResult?.let { result ->
            item {
                MetricRow(
                    "未知词" to result.unknownCount.toString(),
                    "低频词" to result.issues.count { it.type == "lowstat" }.toString(),
                    "问题项" to result.issues.size.toString(),
                )
            }
            item {
                Text(
                    result.status,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (text.isNotEmpty()) {
                item {
                    HighlightPreview(text, result, alicianFont)
                }
            }
            if (result.issues.isNotEmpty()) {
                item { SectionHeader("检查结果", "红色为未知词，蓝色为低频或低泛度词") }
                items(result.issues, key = { it.key }) { issue ->
                    WritingIssueCard(
                        issue = issue,
                        alicianFont = alicianFont,
                        onClick = { viewModel.lookupWriting(issue.display) },
                    )
                }
            } else if (text.isNotBlank()) {
                item {
                    EmptyState(
                        icon = Icons.Outlined.CheckCircle,
                        title = "未发现问题",
                        detail = "当前大小写规则与排除词设置下，文本检查通过。",
                    )
                }
            }
        } ?: item {
            EmptyState(
                icon = Icons.Outlined.Description,
                title = "输入文本开始检查",
                detail = "写作检查同样完全在设备本地运行。",
            )
        }
    }

    if (showSettings) {
        WritingSettingsDialog(
            initial = viewModel.writingSettings,
            onDismiss = { showSettings = false },
            onSave = {
                showSettings = false
                viewModel.saveWritingSettings(it)
            },
        )
    }
    viewModel.lookupResult?.let {
        LookupSheet(it, alicianFont, viewModel::closeLookup)
    }
}

@Composable
private fun HighlightPreview(
    text: String,
    result: WritingResult,
    alicianFont: FontFamily,
) {
    val unknownBackground = MaterialTheme.colorScheme.errorContainer
    val unknownForeground = MaterialTheme.colorScheme.onErrorContainer
    val lowBackground = MaterialTheme.colorScheme.primaryContainer
    val lowForeground = MaterialTheme.colorScheme.onPrimaryContainer
    val annotated = remember(text, result, unknownBackground, lowBackground) {
        buildAnnotatedString {
            append(text)
            result.lowStatRanges.forEach { range ->
                if (range.start in 0..text.length && range.end in range.start..text.length) {
                    addStyle(
                        SpanStyle(background = lowBackground, color = lowForeground),
                        range.start,
                        range.end,
                    )
                }
            }
            result.unknownRanges.forEach { range ->
                if (range.start in 0..text.length && range.end in range.start..text.length) {
                    addStyle(
                        SpanStyle(background = unknownBackground, color = unknownForeground),
                        range.start,
                        range.end,
                    )
                }
            }
        }
    }
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text("高亮预览", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(8.dp))
            SelectionContainer {
                Text(
                    annotated,
                    fontFamily = alicianFont,
                    style = MaterialTheme.typography.bodyLarge,
                )
            }
        }
    }
}

@Composable
private fun WritingIssueCard(
    issue: WritingIssue,
    alicianFont: FontFamily,
    onClick: () -> Unit,
) {
    val isUnknown = issue.type == "unknown"
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = if (isUnknown) {
                MaterialTheme.colorScheme.errorContainer
            } else {
                MaterialTheme.colorScheme.primaryContainer
            },
        ),
    ) {
        Row(Modifier.padding(16.dp)) {
            Icon(
                if (isUnknown) Icons.Outlined.ErrorOutline else Icons.Outlined.Description,
                contentDescription = null,
            )
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    issue.display,
                    style = MaterialTheme.typography.titleMedium,
                    fontFamily = alicianFont,
                )
                Text(
                    if (isUnknown) {
                        "未知词 · 点按查询相近词"
                    } else {
                        "词频 ${issue.count} · 泛度 ${issue.variety}"
                    },
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}

@Composable
private fun WritingSettingsDialog(
    initial: WritingSettings,
    onDismiss: () -> Unit,
    onSave: (WritingSettings) -> Unit,
) {
    var strictCase by remember { mutableStateOf(initial.strictCase) }
    var maxUndo by remember { mutableStateOf(initial.maxUndoSteps.toString()) }
    var excluded by remember { mutableStateOf(initial.excludedWords.joinToString("\n")) }
    var dictionaryFormat by remember { mutableStateOf(initial.dictionaryFormatEnabled) }
    var separators by remember {
        mutableStateOf(initial.dictionaryFormatSeparators.joinToString(", "))
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("写作检查设置") },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                SettingSwitchRow(
                    title = "严格区分大小写",
                    detail = "关闭后按小写形式匹配已知词",
                    checked = strictCase,
                    onCheckedChange = { strictCase = it },
                )
                OutlinedTextField(
                    value = maxUndo,
                    onValueChange = { maxUndo = it.filter(Char::isDigit) },
                    label = { Text("最大撤销步数") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = excluded,
                    onValueChange = { excluded = it },
                    label = { Text("排除词（每行一个）") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                )
                SettingSwitchRow(
                    title = "词表格式",
                    detail = "忽略分隔符右侧的释义文本",
                    checked = dictionaryFormat,
                    onCheckedChange = { dictionaryFormat = it },
                )
                OutlinedTextField(
                    value = separators,
                    onValueChange = { separators = it },
                    label = { Text("释义分隔符") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSave(
                        WritingSettings(
                            strictCase = strictCase,
                            maxUndoSteps = maxUndo.toIntOrNull()?.coerceIn(1, 1000) ?: 100,
                            excludedWords = excluded.lines().map(String::trim).filter(String::isNotEmpty),
                            dictionaryFormatEnabled = dictionaryFormat,
                            dictionaryFormatSeparators = separators
                                .split(',', '，', '\n')
                                .map(String::trim)
                                .filter(String::isNotEmpty),
                        ),
                    )
                },
            ) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LookupSheet(
    result: LookupResult,
    alicianFont: FontFamily,
    onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        LazyColumn(
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { Text("释义与拼写建议", style = MaterialTheme.typography.headlineSmall) }
            items(result.explanations, key = { it.word }) { explanation ->
                Card {
                    Column(Modifier.padding(16.dp)) {
                        Text(
                            explanation.word,
                            fontFamily = alicianFont,
                            style = MaterialTheme.typography.titleLarge,
                        )
                        if (explanation.partOfSpeech.isNotBlank()) {
                            Text(
                                explanation.partOfSpeech,
                                color = MaterialTheme.colorScheme.primary,
                                style = MaterialTheme.typography.labelLarge,
                            )
                        }
                        Spacer(Modifier.height(6.dp))
                        Text(explanation.explanation)
                    }
                }
            }
            if (result.similarWords.isNotEmpty()) {
                item { SectionHeader("相近词") }
                items(result.similarWords, key = { "${it.word}:${it.similarWord}" }) { similar ->
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.secondaryContainer,
                        ),
                    ) {
                        Column(Modifier.padding(16.dp)) {
                            Text(
                                "${similar.word} → ${similar.similarWord}",
                                fontFamily = alicianFont,
                                style = MaterialTheme.typography.titleMedium,
                            )
                            Text(similar.explanation)
                            Text(
                                "相似度 ${(similar.score * 100).toInt()}%",
                                style = MaterialTheme.typography.labelMedium,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun SettingSwitchRow(
    title: String,
    detail: String,
    checked: Boolean,
    onCheckedChange: (Boolean) -> Unit,
) {
    Row(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleSmall)
            Text(
                detail,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.width(12.dp))
        Switch(checked = checked, onCheckedChange = onCheckedChange)
    }
}
