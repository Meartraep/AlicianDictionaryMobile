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
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
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
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
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
fun WritingScreen(
    viewModel: MainViewModel,
    padding: PaddingValues,
    isActive: Boolean = true,
) {
    var text by rememberSaveable { mutableStateOf("") }
    var showSettings by remember { mutableStateOf(false) }
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val alicianFont = if (viewModel.alicianFontEnabled) {
        FontFamily(Font(R.font.alician_regular))
    } else {
        FontFamily.Default
    }
    val currentWritingResult = viewModel.writingResult?.takeIf {
        it.sourceText == text
    }
    val unknownTextColor = MaterialTheme.colorScheme.error
    val lowStatTextColor = if (MaterialTheme.colorScheme.surface.luminance() < 0.5f) {
        Color(0xFF64B5F6)
    } else {
        Color(0xFF1565C0)
    }
    val highlightTransformation = remember(
        currentWritingResult,
        unknownTextColor,
        lowStatTextColor,
    ) {
        currentWritingResult?.let {
            WritingHighlightVisualTransformation(
                result = it,
                unknownColor = unknownTextColor,
                lowStatColor = lowStatTextColor,
            )
        } ?: VisualTransformation.None
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

    LaunchedEffect(text, viewModel.writingSettings, isActive) {
        if (isActive) {
            delay(550)
            viewModel.checkWritingSilently(text)
        }
    }
    val landscape = isLandscapeLayout()
    val panePadding = PaddingValues(
        start = 16.dp,
        end = 16.dp,
        top = padding.calculateTopPadding() + if (landscape) 12.dp else 18.dp,
        bottom = padding.calculateBottomPadding() + if (landscape) 16.dp else 24.dp,
    )

    val editorPane: @Composable () -> Unit = {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = panePadding,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            writingEditorItems(
                text = text,
                onTextChanged = { text = it },
                alicianFont = alicianFont,
                highlightTransformation = highlightTransformation,
                onImport = { importLauncher.launch(arrayOf("text/plain", "text/*")) },
                onExport = { exportLauncher.launch("alician-writing.txt") },
                onSettings = { showSettings = true },
                onCheck = { viewModel.checkWriting(text) },
            )
        }
    }
    val resultPane: @Composable () -> Unit = {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = panePadding,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            writingResultItems(
                result = viewModel.writingResult,
                text = text,
                alicianFont = alicianFont,
                includePageHeader = landscape,
                onIssueClick = { viewModel.lookupWriting(it.display) },
            )
        }
    }

    if (landscape) {
        LandscapeTwoPane(
            primary = editorPane,
            secondary = resultPane,
            primaryWeight = 0.5f,
        )
    } else {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = panePadding,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            writingEditorItems(
                text = text,
                onTextChanged = { text = it },
                alicianFont = alicianFont,
                highlightTransformation = highlightTransformation,
                onImport = { importLauncher.launch(arrayOf("text/plain", "text/*")) },
                onExport = { exportLauncher.launch("alician-writing.txt") },
                onSettings = { showSettings = true },
                onCheck = { viewModel.checkWriting(text) },
            )
            writingResultItems(
                result = viewModel.writingResult,
                text = text,
                alicianFont = alicianFont,
                includePageHeader = false,
                onIssueClick = { viewModel.lookupWriting(it.display) },
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

private fun LazyListScope.writingEditorItems(
    text: String,
    onTextChanged: (String) -> Unit,
    alicianFont: FontFamily,
    highlightTransformation: VisualTransformation,
    onImport: () -> Unit,
    onExport: () -> Unit,
    onSettings: () -> Unit,
    onCheck: () -> Unit,
) {
        item {
            Text("写作助手", style = MaterialTheme.typography.headlineMedium)
            Text(
                "未知词直接标红，低频或低泛度词直接标蓝",
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
                    onClick = onImport,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Outlined.UploadFile, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("导入")
                }
                OutlinedButton(
                    onClick = onExport,
                    modifier = Modifier.weight(1f),
                    enabled = text.isNotEmpty(),
                ) {
                    Icon(Icons.Outlined.Download, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("导出")
                }
                OutlinedButton(
                    onClick = onSettings,
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
                onValueChange = onTextChanged,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(250.dp),
                label = { Text("爱丽丝语文本") },
                placeholder = { Text("输入或导入文本；停顿片刻后自动检查…") },
                textStyle = MaterialTheme.typography.bodyLarge.copy(fontFamily = alicianFont),
                visualTransformation = highlightTransformation,
            )
        }
        item {
            Button(
                onClick = onCheck,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Outlined.CheckCircle, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("立即检查")
            }
        }
}

private fun LazyListScope.writingResultItems(
    result: WritingResult?,
    text: String,
    alicianFont: FontFamily,
    includePageHeader: Boolean,
    onIssueClick: (WritingIssue) -> Unit,
) {
        if (includePageHeader) {
            item { SectionHeader("检查结果", "问题列表与编辑区可独立滚动") }
        }
        result?.let { result ->
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
            if (result.issues.isNotEmpty()) {
                item { SectionHeader("检查结果", "红色为未知词，蓝色为低频或低泛度词") }
                items(result.issues, key = { it.key }) { issue ->
                    WritingIssueCard(
                        issue = issue,
                        alicianFont = alicianFont,
                        onClick = { onIssueClick(issue) },
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

internal class WritingHighlightVisualTransformation(
    private val result: WritingResult,
    private val unknownColor: Color,
    private val lowStatColor: Color,
) : VisualTransformation {
    override fun filter(text: AnnotatedString): TransformedText = TransformedText(
        buildWritingHighlightedText(
            text = text.text,
            result = result,
            unknownColor = unknownColor,
            lowStatColor = lowStatColor,
        ),
        OffsetMapping.Identity,
    )
}

internal fun buildWritingHighlightedText(
    text: String,
    result: WritingResult,
    unknownColor: Color,
    lowStatColor: Color,
): AnnotatedString = buildAnnotatedString {
    append(text)
    result.lowStatRanges.forEach { range ->
        if (range.start in 0..text.length && range.end in range.start..text.length) {
            addStyle(SpanStyle(color = lowStatColor), range.start, range.end)
        }
    }
    // Unknown ranges are applied last, so red remains authoritative if the
    // backend ever reports overlapping categories.
    result.unknownRanges.forEach { range ->
        if (range.start in 0..text.length && range.end in range.start..text.length) {
            addStyle(SpanStyle(color = unknownColor), range.start, range.end)
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
    enabled: Boolean = true,
) {
    Row(modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.weight(1f)) {
            Text(
                title,
                style = MaterialTheme.typography.titleSmall,
                color = if (enabled) {
                    MaterialTheme.colorScheme.onSurface
                } else {
                    MaterialTheme.colorScheme.onSurface.copy(alpha = 0.38f)
                },
            )
            Text(
                detail,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(
                    alpha = if (enabled) 1f else 0.38f,
                ),
            )
        }
        Spacer(Modifier.width(12.dp))
        Switch(
            checked = checked,
            onCheckedChange = onCheckedChange,
            enabled = enabled,
        )
    }
}
