package com.meartraep.alician.mobile.ui

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material.icons.outlined.ArrowForward
import androidx.compose.material.icons.outlined.Build
import androidx.compose.material.icons.outlined.DataObject
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.Download
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.FindInPage
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.R
import com.meartraep.alician.mobile.data.DbTablePage
import com.meartraep.alician.mobile.data.GlobalMatch
import kotlinx.coroutines.launch
import java.io.File

@Composable
fun DatabaseScreen(
    viewModel: MainViewModel,
    padding: PaddingValues,
    onBack: () -> Unit,
) {
    BackHandler(onBack = onBack)
    var query by rememberSaveable { mutableStateOf("") }
    var exact by rememberSaveable { mutableStateOf(false) }
    var showGlobal by rememberSaveable { mutableStateOf(false) }
    var globalQuery by rememberSaveable { mutableStateOf("") }
    var globalExact by rememberSaveable { mutableStateOf(false) }
    var editingRow by remember { mutableStateOf<Map<String, String>?>(null) }
    var adding by remember { mutableStateOf(false) }
    var deletingRow by remember { mutableStateOf<Map<String, String>?>(null) }
    var pendingCsv by remember { mutableStateOf<File?>(null) }
    val alicianFont = if (viewModel.alicianFontEnabled) {
        FontFamily(Font(R.font.alician_regular))
    } else {
        FontFamily.Default
    }

    val csvLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/zip"),
    ) { uri ->
        val file = pendingCsv
        if (uri != null && file != null) viewModel.savePreparedFile(file, uri)
        pendingCsv = null
    }
    val databaseLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/vnd.sqlite3"),
    ) { uri ->
        if (uri != null) viewModel.exportDatabase(uri)
    }

    LaunchedEffect(Unit) {
        if (viewModel.dbTables.isEmpty()) viewModel.loadDatabase()
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
            Row(verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) {
                    Icon(
                        Icons.AutoMirrored.Outlined.ArrowBack,
                        contentDescription = "返回设置",
                    )
                }
                Spacer(Modifier.width(4.dp))
                Column(Modifier.weight(1f)) {
                    Text("数据库管理", style = MaterialTheme.typography.headlineMedium)
                    Text(
                        "移动端分页视图 · 修改直接写入应用私有数据库",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                DatabaseActionMenu(
                    onRefresh = { viewModel.loadDatabase() },
                    onGlobal = { showGlobal = true },
                    onUpdateCounts = viewModel::updateWordCount,
                    onClassify = viewModel::classifyWords,
                    onExportCsv = {
                        viewModel.exportCsv { file ->
                            pendingCsv = file
                            csvLauncher.launch("AlicianDictionaryCsv.zip")
                        }
                    },
                    onExportDatabase = {
                        databaseLauncher.launch("translated.db")
                    },
                )
            }
        }

        val page = viewModel.dbPage
        if (viewModel.dbTables.isNotEmpty()) {
            item {
                SelectField(
                    label = "数据表",
                    value = page?.table ?: viewModel.dbTables.first(),
                    options = viewModel.dbTables,
                    display = { it },
                    onSelected = {
                        query = ""
                        viewModel.loadDatabase(table = it)
                    },
                )
            }
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedTextField(
                        value = query,
                        onValueChange = { query = it },
                        label = { Text("搜索当前表") },
                        leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                        modifier = Modifier.weight(1f),
                        singleLine = true,
                    )
                    IconButton(
                        onClick = {
                            page?.table?.let {
                                viewModel.loadDatabase(it, query, exact, 0)
                            }
                        },
                    ) {
                        Icon(Icons.Outlined.Search, contentDescription = "搜索")
                    }
                }
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
                        label = { Text("精确") },
                    )
                    OutlinedButton(
                        onClick = {
                            query = ""
                            page?.table?.let { viewModel.loadDatabase(it) }
                        },
                    ) { Text("显示全部") }
                    Button(
                        onClick = { adding = true },
                        enabled = page != null,
                    ) {
                        Icon(Icons.Outlined.Add, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text("新增")
                    }
                }
            }
        }

        if (page == null) {
            item {
                EmptyState(
                    icon = Icons.Outlined.DataObject,
                    title = "正在读取数据表",
                    detail = "数据库共 ${viewModel.databaseInfo.tableCount} 张业务表。",
                )
            }
        } else {
            item {
                MetricRow(
                    "记录" to page.total.toString(),
                    "字段" to page.fields.size.toString(),
                    "本页" to page.rows.size.toString(),
                )
            }
            items(
                page.rows,
                key = { row ->
                    "${page.table}:${row["id"] ?: row["rowid"] ?: row.hashCode()}"
                },
            ) { row ->
                DatabaseRowCard(
                    row = row,
                    fields = page.fields,
                    alicianFont = alicianFont,
                    onEdit = { editingRow = row },
                    onDelete = { deletingRow = row },
                )
            }
            if (page.rows.isEmpty()) {
                item {
                    EmptyState(
                        icon = Icons.Outlined.FindInPage,
                        title = "当前页没有记录",
                        detail = "修改搜索条件，或切换到其他数据表。",
                    )
                }
            }
            item {
                PaginationControls(
                    page = page,
                    onPrevious = {
                        viewModel.loadDatabase(
                            page.table,
                            query,
                            exact,
                            (page.offset - page.limit).coerceAtLeast(0),
                        )
                    },
                    onNext = {
                        viewModel.loadDatabase(
                            page.table,
                            query,
                            exact,
                            page.offset + page.limit,
                        )
                    },
                )
            }
        }
    }

    val page = viewModel.dbPage
    if (adding && page != null) {
        RecordEditorDialog(
            title = "新增 ${page.table} 记录",
            fields = page.fields.filterNot { it == "id" || it == "rowid" },
            initial = emptyMap(),
            onDismiss = { adding = false },
            onSave = {
                adding = false
                viewModel.addRecord(page.table, it)
            },
        )
    }
    editingRow?.let { row ->
        if (page != null) {
            RecordEditorDialog(
                title = "编辑 ${page.table} 记录",
                fields = page.fields.filterNot { it == "id" || it == "rowid" },
                initial = row,
                onDismiss = { editingRow = null },
                onSave = { values ->
                    editingRow = null
                    row.recordId()?.let { viewModel.updateRecord(page.table, it, values) }
                },
            )
        }
    }
    deletingRow?.let { row ->
        if (page != null) {
            ConfirmActionDialog(
                title = "删除记录？",
                message = "将从 ${page.table} 永久删除 ID ${row.recordId()}。建议先导出数据库备份。",
                confirmText = "删除",
                destructive = true,
                onConfirm = {
                    deletingRow = null
                    row.recordId()?.let { viewModel.deleteRecord(page.table, it) }
                },
                onDismiss = { deletingRow = null },
            )
        }
    }
    if (showGlobal) {
        GlobalSearchSheet(
            query = globalQuery,
            exact = globalExact,
            matches = viewModel.globalMatches,
            onQueryChange = { globalQuery = it },
            onExactChange = { globalExact = it },
            onSearch = { viewModel.globalSearch(globalQuery, globalExact) },
            onReplace = { replacement, selected ->
                viewModel.globalReplace(globalQuery, replacement, selected)
            },
            onDismiss = { showGlobal = false },
        )
    }
}

@Composable
private fun DatabaseActionMenu(
    onRefresh: () -> Unit,
    onGlobal: () -> Unit,
    onUpdateCounts: () -> Unit,
    onClassify: () -> Unit,
    onExportCsv: () -> Unit,
    onExportDatabase: () -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick = { expanded = true }) {
            Icon(Icons.Outlined.MoreVert, contentDescription = "数据库操作")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text("刷新当前表") },
                leadingIcon = { Icon(Icons.Outlined.Refresh, contentDescription = null) },
                onClick = { expanded = false; onRefresh() },
            )
            DropdownMenuItem(
                text = { Text("全局搜索与替换") },
                leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                onClick = { expanded = false; onGlobal() },
            )
            DropdownMenuItem(
                text = { Text("更新词频 / 泛度") },
                leadingIcon = { Icon(Icons.Outlined.Build, contentDescription = null) },
                onClick = { expanded = false; onUpdateCounts() },
            )
            DropdownMenuItem(
                text = { Text("更新词性统计") },
                leadingIcon = { Icon(Icons.Outlined.Build, contentDescription = null) },
                onClick = { expanded = false; onClassify() },
            )
            DropdownMenuItem(
                text = { Text("导出全部 CSV（ZIP）") },
                leadingIcon = { Icon(Icons.Outlined.Download, contentDescription = null) },
                onClick = { expanded = false; onExportCsv() },
            )
            DropdownMenuItem(
                text = { Text("导出 SQLite 数据库") },
                leadingIcon = { Icon(Icons.Outlined.Download, contentDescription = null) },
                onClick = { expanded = false; onExportDatabase() },
            )
        }
    }
}

@Composable
private fun DatabaseRowCard(
    row: Map<String, String>,
    fields: List<String>,
    alicianFont: FontFamily,
    onEdit: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "#${row.recordId() ?: "?"}",
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
                IconButton(onClick = onEdit) {
                    Icon(Icons.Outlined.Edit, contentDescription = "编辑")
                }
                IconButton(onClick = onDelete) {
                    Icon(Icons.Outlined.Delete, contentDescription = "删除")
                }
            }
            fields.filterNot { it == "id" || it == "rowid" }.forEach { field ->
                val value = row[field].orEmpty()
                if (value.isNotEmpty()) {
                    Text(
                        field,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        value,
                        style = MaterialTheme.typography.bodyMedium,
                        fontFamily = if (field.equals("words", true) ||
                            field.equals("phrase", true) ||
                            field.contains("lyric", true)
                        ) {
                            alicianFont
                        } else {
                            FontFamily.Default
                        },
                        maxLines = 5,
                    )
                    Spacer(Modifier.height(7.dp))
                }
            }
        }
    }
}

@Composable
private fun PaginationControls(
    page: DbTablePage,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        OutlinedButton(onClick = onPrevious, enabled = page.offset > 0) {
            Icon(Icons.Outlined.ArrowBack, contentDescription = null)
            Spacer(Modifier.width(5.dp))
            Text("上一页")
        }
        Text(
            "${page.offset + 1}–${(page.offset + page.rows.size).coerceAtMost(page.total)} / ${page.total}",
            style = MaterialTheme.typography.labelLarge,
        )
        OutlinedButton(
            onClick = onNext,
            enabled = page.offset + page.rows.size < page.total,
        ) {
            Text("下一页")
            Spacer(Modifier.width(5.dp))
            Icon(Icons.Outlined.ArrowForward, contentDescription = null)
        }
    }
}

@Composable
private fun RecordEditorDialog(
    title: String,
    fields: List<String>,
    initial: Map<String, String>,
    onDismiss: () -> Unit,
    onSave: (Map<String, String>) -> Unit,
) {
    val values = remember(fields, initial) {
        mutableStateListOf<Pair<String, String>>().apply {
            fields.forEach { add(it to initial[it].orEmpty()) }
        }
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            LazyColumn(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(460.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                items(values.size) { index ->
                    val item = values[index]
                    OutlinedTextField(
                        value = item.second,
                        onValueChange = { values[index] = item.first to it },
                        label = { Text(item.first) },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = if (
                            item.first.contains("lyric", true) ||
                            item.first.contains("explanation", true)
                        ) 3 else 1,
                    )
                }
            }
        },
        confirmButton = {
            Button(onClick = { onSave(values.toMap()) }) { Text("保存") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun GlobalSearchSheet(
    query: String,
    exact: Boolean,
    matches: List<GlobalMatch>,
    onQueryChange: (String) -> Unit,
    onExactChange: (Boolean) -> Unit,
    onSearch: () -> Unit,
    onReplace: (String, List<GlobalMatch>) -> Unit,
    onDismiss: () -> Unit,
) {
    var replacement by rememberSaveable { mutableStateOf("") }
    val selected = remember(matches) { mutableStateListOf<String>() }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        LazyColumn(
            modifier = Modifier.fillMaxWidth(),
            contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 36.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                Text("全局搜索与替换", style = MaterialTheme.typography.headlineSmall)
                Text(
                    "跨所有数据表和字段搜索；仅替换勾选项。",
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            item {
                OutlinedTextField(
                    value = query,
                    onValueChange = onQueryChange,
                    label = { Text("查找内容") },
                    modifier = Modifier.fillMaxWidth(),
                    singleLine = true,
                )
            }
            item {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    FilterChip(
                        selected = exact,
                        onClick = { onExactChange(!exact) },
                        label = { Text("精确匹配") },
                    )
                    Button(onClick = onSearch, enabled = query.isNotBlank()) {
                        Text("搜索")
                    }
                    TextButton(
                        onClick = {
                            selected.clear()
                            selected.addAll(matches.map(GlobalMatch::selectionKey))
                        },
                        enabled = matches.isNotEmpty(),
                    ) { Text("全选") }
                }
            }
            if (matches.isNotEmpty()) {
                item {
                    OutlinedTextField(
                        value = replacement,
                        onValueChange = { replacement = it },
                        label = { Text("替换为") },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                    )
                }
                item {
                    Button(
                        onClick = {
                            onReplace(
                                replacement,
                                matches.filter { it.selectionKey() in selected },
                            )
                        },
                        enabled = selected.isNotEmpty(),
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("替换所选 ${selected.size} 项") }
                }
                items(matches, key = GlobalMatch::selectionKey) { match ->
                    val key = match.selectionKey()
                    Card {
                        Row(
                            modifier = Modifier.padding(10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Checkbox(
                                checked = key in selected,
                                onCheckedChange = {
                                    if (it) selected.add(key) else selected.remove(key)
                                },
                            )
                            Spacer(Modifier.width(8.dp))
                            Column {
                                Text(
                                    "${match.table} · #${match.id} · ${match.field}",
                                    style = MaterialTheme.typography.labelLarge,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                                Text(match.value, maxLines = 4)
                            }
                        }
                    }
                }
            } else {
                item {
                    EmptyState(
                        icon = Icons.Outlined.Search,
                        title = "尚无全局搜索结果",
                        detail = "输入查找内容后执行搜索。",
                    )
                }
            }
        }
    }
}

private fun Map<String, String>.recordId(): Long? =
    (get("id") ?: get("rowid"))?.toLongOrNull()

private fun GlobalMatch.selectionKey(): String = "$table:$id:$field"
