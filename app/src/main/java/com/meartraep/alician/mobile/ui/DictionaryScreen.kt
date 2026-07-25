package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.LibraryBooks
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
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusManager
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.res.fontResource
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
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
                onValueChange = { query = it },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("爱丽丝语或中文") },
                placeholder = { Text("例如 Xia、爱、世界") },
                leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                trailingIcon = {
                    IconButton(
                        onClick = {
                            focusManager.clearFocus()
                            viewModel.searchDictionary(query, exact, position)
                        },
                    ) {
                        Icon(Icons.Outlined.Search, contentDescription = "查询")
                    }
                },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(
                    onSearch = {
                        focusManager.clearFocus()
                        viewModel.searchDictionary(query, exact, position)
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
                    onClick = { exact = !exact },
                    label = { Text("精确匹配") },
                    leadingIcon = { Icon(Icons.Outlined.Tune, contentDescription = null) },
                )
                positionOptions.forEach { option ->
                    FilterChip(
                        selected = position == option.first,
                        onClick = { position = option.first },
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
                                query = historyItem
                                viewModel.searchDictionary(historyItem, exact, position)
                            },
                            label = { Text(historyItem, fontFamily = alicianFont) },
                        )
                    }
                }
            }
        }

        val result = viewModel.dictionaryResult
        if (result == null) {
            item {
                EmptyState(
                    icon = Icons.Outlined.LibraryBooks,
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
                                    query = suggestion.word
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
                            query = entry.word
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

    viewModel.dictionaryExamples?.let { examples ->
        ExamplesSheet(
            result = examples,
            alicianFont = alicianFont,
            onDismiss = viewModel::closeExamples,
            onUpdateLyric = viewModel::updateLyric,
        )
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
    var viewing by remember { mutableStateOf<LyricExample?>(null) }
    var editing by remember { mutableStateOf<LyricExample?>(null) }
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
                    "歌曲 ${result.songStats} 首 · 去重前 ${result.totalBefore} · 当前 ${result.totalAfter}",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
            if (result.message.isNotBlank()) {
                item { InfoBanner(result.message, isError = result.examples.isEmpty()) }
            }
            items(result.examples, key = { "${it.title}:${it.id}" }) { example ->
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
                            example.paragraph,
                            fontFamily = alicianFont,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                        Spacer(Modifier.height(8.dp))
                        TextButton(onClick = { viewing = example }) {
                            Text("查看整首歌词")
                        }
                    }
                }
            }
            if (result.examples.isEmpty()) {
                item {
                    EmptyState(
                        icon = Icons.Outlined.LibraryBooks,
                        title = "没有符合条件的歌词",
                        detail = "可切换到“任意位置”后重新查询。",
                    )
                }
            }
        }
    }

    viewing?.let { example ->
        AlertDialog(
            onDismissRequest = { viewing = null },
            title = { Text(example.title) },
            text = {
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
                    ),
                ) {
                    SelectionContainer {
                        Text(
                            text = example.lyric,
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(420.dp)
                                .verticalScroll(rememberScrollState())
                                .padding(16.dp),
                            fontFamily = alicianFont,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            },
            confirmButton = {
                Button(
                    onClick = {
                        viewing = null
                        editing = example
                    },
                ) { Text("编辑") }
            },
            dismissButton = {
                OutlinedButton(onClick = { viewing = null }) { Text("关闭") }
            },
        )
    }

    editing?.let { example ->
        var lyric by remember(example) { mutableStateOf(example.lyric) }
        AlertDialog(
            onDismissRequest = { editing = null },
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
                        editing = null
                    },
                ) { Text("保存") }
            },
            dismissButton = {
                OutlinedButton(onClick = { editing = null }) { Text("取消") }
            },
        )
    }
}
