package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material.icons.automirrored.outlined.LibraryBooks
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.R
import com.meartraep.alician.mobile.data.DictionaryEntry
import com.meartraep.alician.mobile.data.ExampleResult
import com.meartraep.alician.mobile.data.LyricExample

private val positionOptions = listOf(
    "any" to "任意位置",
    "start" to "句首",
    "end" to "句尾",
)

@Composable
fun DictionaryScreen(viewModel: MainViewModel, padding: PaddingValues) {
    var query by rememberSaveable { mutableStateOf("") }
    var exact by rememberSaveable { mutableStateOf(false) }
    var position by rememberSaveable { mutableStateOf("any") }
    val focusManager = LocalFocusManager.current
    val alicianFont = if (viewModel.alicianFontEnabled) {
        FontFamily(Font(R.font.alician_regular))
    } else {
        FontFamily.Default
    }
    val landscape = isLandscapeLayout()
    val panePadding = PaddingValues(
        start = 16.dp,
        end = 16.dp,
        top = padding.calculateTopPadding() + if (landscape) 12.dp else 18.dp,
        bottom = padding.calculateBottomPadding() + if (landscape) 16.dp else 24.dp,
    )

    val searchPane: @Composable () -> Unit = {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = panePadding,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            dictionarySearchItems(
                query = query,
                onQueryChanged = { query = it },
                exact = exact,
                onExactChanged = { exact = it },
                position = position,
                onPositionChanged = { position = it },
                viewModel = viewModel,
                alicianFont = alicianFont,
                onSearch = {
                    focusManager.clearFocus()
                    viewModel.searchDictionary(it, exact, position)
                },
            )
        }
    }
    val resultPane: @Composable () -> Unit = {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = panePadding,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            dictionaryResultItems(
                viewModel = viewModel,
                alicianFont = alicianFont,
                includePageHeader = landscape,
                onQueryChanged = { query = it },
                exact = exact,
                position = position,
            )
        }
    }

    if (landscape) {
        LandscapeTwoPane(
            primary = searchPane,
            secondary = resultPane,
            primaryWeight = 0.44f,
        )
    } else {
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = panePadding,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            dictionarySearchItems(
                query = query,
                onQueryChanged = { query = it },
                exact = exact,
                onExactChanged = { exact = it },
                position = position,
                onPositionChanged = { position = it },
                viewModel = viewModel,
                alicianFont = alicianFont,
                onSearch = {
                    focusManager.clearFocus()
                    viewModel.searchDictionary(it, exact, position)
                },
            )
            dictionaryResultItems(
                viewModel = viewModel,
                alicianFont = alicianFont,
                includePageHeader = false,
                onQueryChanged = { query = it },
                exact = exact,
                position = position,
            )
        }
    }

    viewModel.dictionaryExamples?.let { examples ->
        ExamplesSheet(
            result = examples,
            alicianFont = alicianFont,
            onDismiss = viewModel::closeExamples,
            onUpdateLyric = viewModel::updateLyric,
        )
    }
}

private fun LazyListScope.dictionarySearchItems(
    query: String,
    onQueryChanged: (String) -> Unit,
    exact: Boolean,
    onExactChanged: (Boolean) -> Unit,
    position: String,
    onPositionChanged: (String) -> Unit,
    viewModel: MainViewModel,
    alicianFont: FontFamily,
    onSearch: (String) -> Unit,
) {
        item {
            Text("爱丽丝语词典", style = MaterialTheme.typography.headlineMedium)
            Text(
                "Lite 本地词典 · 支持中文反查、拼写建议和歌词上下文",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        item {
            OutlinedTextField(
                value = query,
                onValueChange = onQueryChanged,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("爱丽丝语或中文") },
                placeholder = { Text("例如 Xia、爱、世界") },
                leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                trailingIcon = {
                    IconButton(
                        onClick = {
                            onSearch(query)
                        },
                    ) {
                        Icon(Icons.Outlined.Search, contentDescription = "查询")
                    }
                },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(
                    onSearch = {
                        onSearch(query)
                    },
                ),
            )
        }
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FilterChip(
                    selected = exact,
                    onClick = { onExactChanged(!exact) },
                    label = { Text("精确匹配") },
                    leadingIcon = { Icon(Icons.Outlined.Tune, contentDescription = null) },
                )
                positionOptions.forEach { option ->
                    FilterChip(
                        selected = position == option.first,
                        onClick = { onPositionChanged(option.first) },
                        label = { Text(option.second) },
                    )
                }
            }
        }
        if (viewModel.history.isNotEmpty()) {
            item {
                Row {
                    Icon(Icons.Outlined.History, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("最近查询", style = MaterialTheme.typography.titleSmall)
                }
            }
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(viewModel.history, key = { it }) { historyItem ->
                        AssistChip(
                            onClick = {
                                onQueryChanged(historyItem)
                                viewModel.searchDictionary(historyItem, exact, position)
                            },
                            label = { Text(historyItem, fontFamily = alicianFont) },
                        )
                    }
                }
            }
        }
}

private fun LazyListScope.dictionaryResultItems(
    viewModel: MainViewModel,
    alicianFont: FontFamily,
    includePageHeader: Boolean,
    onQueryChanged: (String) -> Unit,
    exact: Boolean,
    position: String,
) {
        if (includePageHeader) {
            item { SectionHeader("查询结果", "筛选区与结果区可独立滚动") }
        }
        val result = viewModel.dictionaryResult
        if (result == null) {
            item {
                EmptyState(
                    icon = Icons.AutoMirrored.Outlined.LibraryBooks,
                    title = if (viewModel.ready) "开始查询" else "正在准备词典",
                    detail = "结果完全在本机数据库中生成，无需联网。",
                )
            }
        } else {
            if (result.message.isNotBlank()) {
                item { InfoBanner(result.message, isError = result.sections.isEmpty()) }
            }
            if (result.suggestions.isNotEmpty()) {
                item {
                    SectionHeader("你是否想查", "Lite 版基于编辑距离提供拼写纠错")
                }
                item {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(result.suggestions, key = { it.word }) { suggestion ->
                            AssistChip(
                                onClick = {
                                    onQueryChanged(suggestion.word)
                                    viewModel.searchDictionary(suggestion.word, exact, position)
                                },
                                label = { Text(suggestion.word, fontFamily = alicianFont) },
                            )
                        }
                    }
                }
            }
            result.sections.forEach { section ->
                item {
                    SectionHeader(section.title, "${section.entries.size} 条结果")
                }
                items(
                    section.entries,
                    key = { "${section.kind}:${it.word}:${it.explanation}" },
                ) { entry ->
                    DictionaryEntryCard(
                        entry = entry,
                        alicianFont = alicianFont,
                        onClick = {
                            onQueryChanged(entry.word)
                            viewModel.loadExamples(entry.word, position)
                        },
                    )
                }
            }
            if (result.sections.isEmpty() && result.suggestions.isEmpty()) {
                item {
                    EmptyState(
                        icon = Icons.Outlined.Search,
                        title = "没有找到结果",
                        detail = "可关闭精确匹配，或检查拼写后再试。",
                    )
                }
            }
        }
}

@Composable
private fun DictionaryEntryCard(
    entry: DictionaryEntry,
    alicianFont: FontFamily,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(modifier = Modifier.fillMaxWidth()) {
                Text(
                    entry.word,
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.titleLarge,
                    fontFamily = alicianFont,
                    color = MaterialTheme.colorScheme.primary,
                )
                if (entry.wordClass.isNotBlank()) {
                    Text(
                        entry.wordClass,
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }
            Spacer(Modifier.height(7.dp))
            Text(entry.explanation, style = MaterialTheme.typography.bodyLarge)
            Spacer(Modifier.height(10.dp))
            Text(
                "词频 ${entry.count} · 泛度 ${entry.variety}　点按查看歌词例句",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ExamplesSheet(
    result: ExampleResult,
    alicianFont: FontFamily,
    onDismiss: () -> Unit,
    onUpdateLyric: (String, String, String) -> Unit,
) {
    var contextIndex by rememberSaveable(result.word) { mutableIntStateOf(-1) }
    var editingIndex by rememberSaveable(result.word) { mutableIntStateOf(-1) }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 36.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Text(
                    "${result.word} 的歌词例句",
                    style = MaterialTheme.typography.headlineSmall,
                    fontFamily = alicianFont,
                )
                Text(
                    "歌曲 ${result.songStats.size} 首 · 去重前 ${result.totalBefore} · " +
                        "去重后 ${result.totalAfter} · 去重率 " +
                        "${"%.1f".format(result.deduplicationRate)}%",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            if (result.message.isNotBlank()) {
                item { InfoBanner(result.message, isError = result.examples.isEmpty()) }
            }
            if (result.examples.isNotEmpty()) {
                item { SectionHeader("全部例句", "点按可在整首歌词中自动定位") }
            }
            items(
                count = result.examples.size,
                key = { index ->
                    result.examples[index].let { "${it.album}:${it.title}:${it.id}:$index" }
                },
            ) { index ->
                val example = result.examples[index]
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceContainer,
                    ),
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Text(example.title, style = MaterialTheme.typography.titleMedium)
                        Text(
                            example.album,
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Spacer(Modifier.height(10.dp))
                        Text(
                            highlightedText(
                                text = example.paragraph,
                                word = result.word,
                                background = MaterialTheme.colorScheme.errorContainer,
                                foreground = MaterialTheme.colorScheme.onErrorContainer,
                            ),
                            fontFamily = alicianFont,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                        Spacer(Modifier.height(8.dp))
                        TextButton(onClick = { contextIndex = index }) {
                            Text("查看整首歌词并定位")
                        }
                    }
                }
            }
            if (result.examples.isEmpty()) {
                item {
                    EmptyState(
                        icon = Icons.AutoMirrored.Outlined.LibraryBooks,
                        title = "没有符合条件的歌词",
                        detail = "可切换到“任意位置”后重新查询。",
                    )
                }
            }
            if (result.songStats.isNotEmpty()) {
                item { SectionHeader("例句来源分布", "查重前 / 查重后") }
                items(
                    result.songStats,
                    key = { "${it.album}:${it.title}" },
                ) { stats ->
                    Row(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.weight(1f)) {
                            Text(stats.title, style = MaterialTheme.typography.titleSmall)
                            Text(
                                stats.album,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Text(
                            "${stats.before} / ${stats.after}",
                            style = MaterialTheme.typography.labelLarge,
                            color = MaterialTheme.colorScheme.primary,
                        )
                    }
                }
            }
        }
    }

    if (contextIndex in result.examples.indices) {
        LyricContextDialog(
            result = result,
            currentIndex = contextIndex,
            alicianFont = alicianFont,
            onIndexChanged = { contextIndex = it },
            onEdit = {
                editingIndex = contextIndex
                contextIndex = -1
            },
            onDismiss = { contextIndex = -1 },
        )
    }

    if (editingIndex in result.examples.indices) {
        val example = result.examples[editingIndex]
        var lyric by remember(example) { mutableStateOf(example.lyric) }
        AlertDialog(
            onDismissRequest = { editingIndex = -1 },
            title = { Text(example.title) },
            text = {
                OutlinedTextField(
                    value = lyric,
                    onValueChange = { lyric = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(420.dp),
                    textStyle = MaterialTheme.typography.bodyMedium.copy(fontFamily = alicianFont),
                    label = { Text("完整歌词") },
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        onUpdateLyric(example.title, example.album, lyric)
                        editingIndex = -1
                    },
                ) { Text("保存") }
            },
            dismissButton = {
                OutlinedButton(onClick = { editingIndex = -1 }) { Text("取消") }
            },
        )
    }
}

@Composable
private fun LyricContextDialog(
    result: ExampleResult,
    currentIndex: Int,
    alicianFont: FontFamily,
    onIndexChanged: (Int) -> Unit,
    onEdit: () -> Unit,
    onDismiss: () -> Unit,
) {
    val example = result.examples[currentIndex]
    Dialog(
        onDismissRequest = onDismiss,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Surface(
            modifier = Modifier
                .fillMaxSize()
                .padding(12.dp),
            shape = MaterialTheme.shapes.extraLarge,
            tonalElevation = 6.dp,
        ) {
            Column(
                modifier = Modifier.padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                Text(
                    "完整歌词 · ${result.word}",
                    style = MaterialTheme.typography.headlineSmall,
                    fontFamily = alicianFont,
                )
                Text(
                    "${example.album} - ${example.title}",
                    style = MaterialTheme.typography.titleMedium,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                ) {
                    OutlinedButton(
                        onClick = { onIndexChanged(currentIndex - 1) },
                        enabled = currentIndex > 0,
                    ) {
                        Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = null)
                        Spacer(Modifier.width(5.dp))
                        Text("上一句")
                    }
                    Text(
                        "${currentIndex + 1} / ${result.examples.size}",
                        modifier = Modifier.padding(vertical = 12.dp),
                        style = MaterialTheme.typography.labelLarge,
                    )
                    OutlinedButton(
                        onClick = { onIndexChanged(currentIndex + 1) },
                        enabled = currentIndex < result.examples.lastIndex,
                    ) {
                        Text("下一句")
                        Spacer(Modifier.width(5.dp))
                        Icon(Icons.AutoMirrored.Outlined.ArrowForward, contentDescription = null)
                    }
                }
                Text(
                    "红色为查询词，整块底色为当前例句；切换上一句/下一句可跨歌曲跳转。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                FocusedLyric(
                    example = example,
                    word = result.word,
                    alicianFont = alicianFont,
                    modifier = Modifier.weight(1f),
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f),
                    ) { Text("关闭") }
                    Button(
                        onClick = onEdit,
                        modifier = Modifier.weight(1f),
                    ) { Text("编辑歌词") }
                }
            }
        }
    }
}

@Composable
private fun FocusedLyric(
    example: LyricExample,
    word: String,
    alicianFont: FontFamily,
    modifier: Modifier = Modifier,
) {
    val start = example.start.coerceIn(0, example.lyric.length)
    val end = example.end.coerceIn(start, example.lyric.length)
    val before = example.lyric.substring(0, start)
    val focused = example.lyric.substring(start, end)
    val after = example.lyric.substring(end)
    val requester = remember(example.id, example.title, start, end) {
        BringIntoViewRequester()
    }
    val hitBackground = MaterialTheme.colorScheme.errorContainer
    val hitForeground = MaterialTheme.colorScheme.onErrorContainer

    LaunchedEffect(requester) {
        requester.bringIntoView()
    }

    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        SelectionContainer {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
            ) {
                if (before.isNotEmpty()) {
                    Text(
                        highlightedText(before, word, hitBackground, hitForeground),
                        fontFamily = alicianFont,
                        style = MaterialTheme.typography.bodyLarge,
                    )
                }
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .bringIntoViewRequester(requester)
                        .background(
                            MaterialTheme.colorScheme.secondaryContainer,
                            MaterialTheme.shapes.small,
                        )
                        .border(
                            1.dp,
                            MaterialTheme.colorScheme.secondary,
                            MaterialTheme.shapes.small,
                        )
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                ) {
                    Text(
                        highlightedText(focused, word, hitBackground, hitForeground),
                        fontFamily = alicianFont,
                        style = MaterialTheme.typography.bodyLarge,
                    )
                }
                if (after.isNotEmpty()) {
                    Text(
                        highlightedText(after, word, hitBackground, hitForeground),
                        fontFamily = alicianFont,
                        style = MaterialTheme.typography.bodyLarge,
                    )
                }
            }
        }
    }
}

@Composable
private fun highlightedText(
    text: String,
    word: String,
    background: Color,
    foreground: Color,
): AnnotatedString = buildAnnotatedString {
    append(text)
    wordMatchRanges(text, word).forEach { range ->
        addStyle(
            SpanStyle(background = background, color = foreground),
            range.first,
            range.last + 1,
        )
    }
}

internal fun wordMatchRanges(text: String, word: String): List<IntRange> {
    val target = word.trim()
    if (target.isEmpty()) return emptyList()
    return Regex(
        pattern = "\\b${Regex.escape(target)}\\b",
        option = RegexOption.IGNORE_CASE,
    ).findAll(text).map { it.range }.toList()
}
