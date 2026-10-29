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
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items as gridItems
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material.icons.outlined.ArrowForward
import androidx.compose.material.icons.outlined.Build
import androidx.compose.material.icons.outlined.DataObject
import androidx.compose.material.icons.outlined.Download
import androidx.compose.material.icons.outlined.FindInPage
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
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
import java.io.File

/**
 * 数据库管理页：P2 起只做只读浏览、维护动作与导出。
 * 行级编辑/删除已迁移到 词典 → 数据 工作区（统一写守卫 + 恢复点）。
 */
@Composable
fun DatabaseScreen(
    viewModel: MainViewModel,
    padding: PaddingValues,
    onBack: () -> Unit,
) {
    BackHandler(onBack = onBack)
    var query by rememberSaveable { mutableStateOf("") }
    var exact by rememberSaveable { mutableStateOf(false) }
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

    val landscape = isLandscapeLayout()
    LazyVerticalGrid(
        columns = GridCells.Fixed(if (landscape) 2 else 1),
        modifier = Modifier.fillMaxSize(),
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
                        "只读浏览 · 编辑已迁移到 词典 → 数据",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                DatabaseActionMenu(
                    onRefresh = { viewModel.loadDatabase() },
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
            item(span = { GridItemSpan(maxLineSpan) }) {
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
            item(span = { GridItemSpan(maxLineSpan) }) {
                MetricRow(
                    "记录" to page.total.toString(),
                    "字段" to page.fields.size.toString(),
                    "本页" to page.rows.size.toString(),
                )
            }
            gridItems(
                page.rows,
                key = { row ->
                    "${page.table}:${row["id"] ?: row["rowid"] ?: row.hashCode()}"
                },
            ) { row ->
                DatabaseRowCard(
                    row = row,
                    fields = page.fields,
                    alicianFont = alicianFont,
                )
            }
            if (page.rows.isEmpty()) {
                item(span = { GridItemSpan(maxLineSpan) }) {
                    EmptyState(
                        icon = Icons.Outlined.FindInPage,
                        title = "当前页没有记录",
                        detail = "修改搜索条件，或切换到其他数据表。",
                    )
                }
            }
            item(span = { GridItemSpan(maxLineSpan) }) {
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
}

@Composable
private fun DatabaseActionMenu(
    onRefresh: () -> Unit,
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
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(Modifier.padding(14.dp)) {
            Text(
                "#${row.recordId() ?: "?"}",
                modifier = Modifier.fillMaxWidth(),
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
            )
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

private fun Map<String, String>.recordId(): Long? =
    (get("id") ?: get("rowid"))?.toLongOrNull()
