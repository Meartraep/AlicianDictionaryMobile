package com.meartraep.alician.mobile.ui

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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.OpenInNew
import androidx.compose.material.icons.outlined.CloudDownload
import androidx.compose.material.icons.outlined.ChevronRight
import androidx.compose.material.icons.outlined.FolderOpen
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.NewReleases
import androidx.compose.material.icons.outlined.Palette
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.RestartAlt
import androidx.compose.material.icons.outlined.Save
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
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
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.meartraep.alician.mobile.BuildConfig
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.data.AppUpdateInfo
import com.meartraep.alician.mobile.data.ColorPalette
import com.meartraep.alician.mobile.data.DatabaseRowDiff
import com.meartraep.alician.mobile.data.DatabaseTableDiff
import com.meartraep.alician.mobile.data.RemoteComparison
import com.meartraep.alician.mobile.data.ThemeMode
import com.meartraep.alician.mobile.data.TypographySize
import com.meartraep.alician.mobile.data.UiSettings
import java.util.Locale

@Composable
fun SettingsScreen(viewModel: MainViewModel, padding: PaddingValues) {
    var showUiSettings by rememberSaveable { mutableStateOf(false) }
    if (showUiSettings) {
        UiSettingsScreen(
            settings = viewModel.uiSettings,
            padding = padding,
            onBack = { showUiSettings = false },
            onSettingsChanged = viewModel::updateUiSettings,
            onReset = viewModel::resetUiSettings,
        )
        return
    }

    var confirmReset by remember { mutableStateOf(false) }
    val uriHandler = LocalUriHandler.current
    val importLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.OpenDocument(),
    ) { uri ->
        if (uri != null) viewModel.importDatabase(uri)
    }
    val exportLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.CreateDocument("application/vnd.sqlite3"),
    ) { uri ->
        if (uri != null) viewModel.exportDatabase(uri)
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
            Text("设置", style = MaterialTheme.typography.headlineMedium)
            Text(
                "显示、数据维护与版本信息",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        item { SectionHeader("界面") }
        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { showUiSettings = true },
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                ),
            ) {
                Row(
                    modifier = Modifier.padding(18.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Outlined.Palette, contentDescription = null)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text("UI 设置", style = MaterialTheme.typography.titleMedium)
                        Text(
                            uiSettingsSummary(viewModel.uiSettings),
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    Icon(Icons.Outlined.ChevronRight, contentDescription = "进入 UI 设置")
                }
            }
        }
        item { SectionHeader("词典数据库", "更新或导入前均会自动创建本地备份") }
        item {
            SettingsCard {
                DatabaseMetricLine("词头", viewModel.databaseInfo.wordCount.toString())
                DatabaseMetricLine("歌曲", viewModel.databaseInfo.songCount.toString())
                DatabaseMetricLine("数据表", viewModel.databaseInfo.tableCount.toString())
                DatabaseMetricLine("文件大小", formatBytes(viewModel.databaseInfo.size))
                DatabaseMetricLine("修改时间", viewModel.databaseInfo.modified.ifBlank { "未知" })
                DatabaseMetricLine(
                    "SHA-256",
                    viewModel.databaseInfo.sha256.take(16).ifBlank { "尚未读取" } +
                        if (viewModel.databaseInfo.sha256.length > 16) "…" else "",
                )
            }
        }
        item {
            Button(
                onClick = viewModel::checkRemoteUpdate,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Outlined.CloudDownload, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("检查云端数据库更新")
            }
        }
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    onClick = {
                        importLauncher.launch(
                            arrayOf(
                                "application/vnd.sqlite3",
                                "application/octet-stream",
                                "*/*",
                            ),
                        )
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Outlined.FolderOpen, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("导入")
                }
                OutlinedButton(
                    onClick = { exportLauncher.launch("translated.db") },
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Outlined.Save, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("导出")
                }
            }
        }
        item {
            OutlinedButton(
                onClick = { confirmReset = true },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Outlined.RestartAlt, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("恢复 APK 内置数据库")
            }
        }
        item {
            SectionHeader("程序更新", "每次启动自动检查 GitHub 最新正式 Release")
        }
        item {
            AppUpdateCard(
                info = viewModel.appUpdateInfo,
                error = viewModel.appUpdateError,
                checking = viewModel.checkingAppUpdate,
                onCheck = viewModel::checkAppUpdate,
                onOpenRelease = { url -> uriHandler.openUri(url) },
            )
        }
        item { SectionHeader("关于") }
        item {
            SettingsCard {
                Row {
                    Icon(Icons.Outlined.Info, contentDescription = null)
                    Spacer(Modifier.width(12.dp))
                    Column {
                        Text(
                            "Alician Dictionary Mobile",
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Text(
                            "版本 ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Text(
                            "最低 Android 7.0 · 支持 arm64-v8a / x86_64",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
        item {
            InfoBanner(
                "本应用基于 Meartraep/Alician_dictionary 的 Lite 版开发，遵循 " +
                    "CC BY-NC-SA 4.0，限非商业用途。移动端保留词典、歌词上下文、" +
                    "写作检查、双向翻译、数据库管理和数据更新能力。",
            )
        }
    }

    if (confirmReset) {
        ConfirmActionDialog(
            title = "恢复内置数据库？",
            message = "当前数据库会先自动备份，然后恢复为此 APK 附带的版本。当前编辑不会丢失，但需要通过备份文件手动恢复。",
            confirmText = "恢复",
            destructive = true,
            onConfirm = {
                confirmReset = false
                viewModel.resetDatabase()
            },
            onDismiss = { confirmReset = false },
        )
    }
    viewModel.remoteComparison?.let { comparison ->
        RemoteUpdateDialog(
            comparison = comparison,
            onApply = viewModel::applyRemoteUpdate,
            onDismiss = viewModel::dismissRemoteComparison,
        )
    }
}

@Composable
private fun AppUpdateCard(
    info: AppUpdateInfo?,
    error: String?,
    checking: Boolean,
    onCheck: () -> Unit,
    onOpenRelease: (String) -> Unit,
) {
    val releaseInfo = info?.takeIf { it.updateAvailable }
    val updateAvailable = releaseInfo != null
    val cardModifier = if (updateAvailable) {
        Modifier
            .fillMaxWidth()
            .clickable { onOpenRelease(releaseInfo.releaseUrl) }
    } else {
        Modifier.fillMaxWidth()
    }
    Card(
        modifier = cardModifier,
        colors = CardDefaults.cardColors(
            containerColor = when {
                updateAvailable -> MaterialTheme.colorScheme.errorContainer
                error != null -> MaterialTheme.colorScheme.tertiaryContainer
                else -> MaterialTheme.colorScheme.surfaceContainerLow
            },
            contentColor = when {
                updateAvailable -> MaterialTheme.colorScheme.onErrorContainer
                error != null -> MaterialTheme.colorScheme.onTertiaryContainer
                else -> MaterialTheme.colorScheme.onSurface
            },
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    Icons.Outlined.NewReleases,
                    contentDescription = null,
                    tint = if (updateAvailable) {
                        MaterialTheme.colorScheme.error
                    } else {
                        MaterialTheme.colorScheme.primary
                    },
                )
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        when {
                            checking -> "正在检查程序更新…"
                            updateAvailable ->
                                "发现新版本 ${releaseInfo.latestVersion}"
                            error != null -> "程序更新检查失败"
                            info != null -> info.message
                            else -> "等待自动检查"
                        },
                        style = MaterialTheme.typography.titleMedium,
                    )
                    Text(
                        "当前版本 ${BuildConfig.VERSION_NAME}",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
                if (checking) {
                    CircularProgressIndicator(
                        modifier = Modifier
                            .width(22.dp)
                            .height(22.dp),
                        strokeWidth = 2.dp,
                    )
                }
            }
            when {
                updateAvailable -> {
                    if (!releaseInfo.releaseName.isNullOrBlank()) {
                        Text(
                            releaseInfo.releaseName,
                            style = MaterialTheme.typography.bodyLarge,
                        )
                    }
                    if (!releaseInfo.publishedAt.isNullOrBlank()) {
                        Text(
                            "发布时间：${releaseInfo.publishedAt.take(10)}",
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    Text(
                        "点按此卡片或下方按钮前往 GitHub Release 页面，手动下载安装新版本。",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                error != null -> Text(error, style = MaterialTheme.typography.bodyMedium)
                info?.hasRelease == true -> Text(
                    "GitHub 最新版本：${info.latestVersion}",
                    style = MaterialTheme.typography.bodyMedium,
                )
                info != null -> Text(info.message, style = MaterialTheme.typography.bodyMedium)
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedButton(
                    onClick = onCheck,
                    enabled = !checking,
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Outlined.Refresh, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text(if (checking) "检查中" else "检查更新")
                }
                if (updateAvailable) {
                    Button(
                        onClick = { onOpenRelease(releaseInfo.releaseUrl) },
                        modifier = Modifier.weight(1f),
                    ) {
                        Icon(Icons.AutoMirrored.Outlined.OpenInNew, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text("前往下载")
                    }
                }
            }
        }
    }
}

@Composable
private fun SettingsCard(content: @Composable () -> Unit) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            content()
        }
    }
}

@Composable
private fun DatabaseMetricLine(label: String, value: String) {
    Row(Modifier.fillMaxWidth()) {
        Text(
            label,
            modifier = Modifier.weight(1f),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(value, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
private fun RemoteUpdateDialog(
    comparison: RemoteComparison,
    onApply: () -> Unit,
    onDismiss: () -> Unit,
) {
    if (comparison.upToDate) {
        AlertDialog(
            onDismissRequest = onDismiss,
            title = { Text("数据库已是最新") },
            text = { Text(comparison.message) },
            confirmButton = {
                Button(onClick = onDismiss) { Text("完成") }
            },
        )
        return
    }

    val changedTables = comparison.diff.tables
    var selectedTable by remember(comparison.remoteSha1) {
        mutableStateOf(changedTables.firstOrNull()?.table.orEmpty())
    }
    val selected = changedTables.firstOrNull { it.table == selectedTable }

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
                Text("数据库更新 — 全部差异", style = MaterialTheme.typography.headlineSmall)
                Text(
                    comparison.message,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                MetricRow(
                    "新增行" to comparison.diff.totalAdded.toString(),
                    "删除行" to comparison.diff.totalRemoved.toString(),
                )
                MetricRow(
                    "修改行" to comparison.diff.totalModified.toString(),
                    "字段变更" to comparison.diff.totalFieldChanges.toString(),
                )
                Text(
                    "涉及 ${changedTables.size} 张表；选择表后可逐行、逐字段查看。",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.primary,
                )
                if (changedTables.isNotEmpty()) {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(changedTables, key = DatabaseTableDiff::table) { table ->
                            FilterChip(
                                selected = selectedTable == table.table,
                                onClick = { selectedTable = table.table },
                                label = {
                                    Text(
                                        "${table.table}  +${table.added} −${table.removed} " +
                                            "~${table.modified}",
                                    )
                                },
                            )
                        }
                    }
                }
                if (selected == null) {
                    InfoBanner(
                        "文件内容不同，但没有检测到可显示的逐行数据差异；可能仅有数据库元数据或结构变化。",
                    )
                    Spacer(Modifier.weight(1f))
                } else {
                    DatabaseTableDiffDetails(
                        table = selected,
                        modifier = Modifier.weight(1f),
                    )
                }
                HorizontalDivider()
                Text(
                    "采纳更新前会自动备份当前数据库。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f),
                    ) { Text("放弃更新") }
                    Button(
                        onClick = onApply,
                        modifier = Modifier.weight(1f),
                    ) { Text("备份并更新") }
                }
            }
        }
    }
}

@Composable
private fun DatabaseTableDiffDetails(
    table: DatabaseTableDiff,
    modifier: Modifier = Modifier,
) {
    LazyColumn(
        modifier = modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Text("表：${table.table}", style = MaterialTheme.typography.titleLarge)
            Text(
                "本地 ${table.localRows} 行 → 云端 ${table.remoteRows} 行　" +
                    "新增 ${table.added} · 删除 ${table.removed} · 修改 ${table.modified} · " +
                    "字段 ${table.fieldChanges}",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (table.addedRows.isNotEmpty()) {
            item {
                SectionHeader(
                    "新增行",
                    diffDisplayCount(
                        shown = table.addedRows.size,
                        total = table.added,
                        truncated = table.truncatedAdded,
                    ),
                )
            }
            itemsIndexed(
                table.addedRows,
                key = { index, row -> "added:${row.id}:$index" },
            ) { _, row ->
                DatabaseRowDiffCard(
                    prefix = "+",
                    row = row,
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.tertiaryContainer,
                        contentColor = MaterialTheme.colorScheme.onTertiaryContainer,
                    ),
                )
            }
        }
        if (table.removedRows.isNotEmpty()) {
            item {
                SectionHeader(
                    "删除行",
                    diffDisplayCount(
                        shown = table.removedRows.size,
                        total = table.removed,
                        truncated = table.truncatedRemoved,
                    ),
                )
            }
            itemsIndexed(
                table.removedRows,
                key = { index, row -> "removed:${row.id}:$index" },
            ) { _, row ->
                DatabaseRowDiffCard(
                    prefix = "−",
                    row = row,
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.errorContainer,
                        contentColor = MaterialTheme.colorScheme.onErrorContainer,
                    ),
                )
            }
        }
        if (table.fieldDiffs.isNotEmpty()) {
            item {
                SectionHeader(
                    "修改详情",
                    diffDisplayCount(
                        shown = table.fieldDiffs.size,
                        total = table.fieldChanges,
                        truncated = table.truncatedModified,
                    ),
                )
            }
            itemsIndexed(
                table.fieldDiffs,
                key = { index, field -> "${field.rowId}:${field.column}:$index" },
            ) { _, field ->
                Card(
                    colors = CardDefaults.cardColors(
                        containerColor = MaterialTheme.colorScheme.secondaryContainer,
                        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
                    ),
                ) {
                    Column(
                        modifier = Modifier.padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(5.dp),
                    ) {
                        Text(
                            "~ 行 ${field.rowId}　[${field.column}]",
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Text("本地：${field.localValue}")
                        Text("云端：${field.remoteValue}")
                    }
                }
            }
        }
        if (
            table.addedRows.isEmpty() &&
            table.removedRows.isEmpty() &&
            table.fieldDiffs.isEmpty()
        ) {
            item {
                InfoBanner("此表有数量差异，但没有可显示的明细。")
            }
        }
    }
}

@Composable
private fun DatabaseRowDiffCard(
    prefix: String,
    row: DatabaseRowDiff,
    colors: androidx.compose.material3.CardColors,
) {
    Card(colors = colors) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(5.dp),
        ) {
            Text("$prefix 行 ${row.id}", style = MaterialTheme.typography.titleSmall)
            row.values.forEach { (field, value) ->
                Text(field, style = MaterialTheme.typography.labelMedium)
                Text(value, style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

private fun diffDisplayCount(shown: Int, total: Int, truncated: Boolean): String =
    if (truncated) "显示 $shown / $total 项（与原版一致，单类最多 2000 项）"
    else "共 $total 项"

private fun uiSettingsSummary(settings: UiSettings): String {
    val mode = when (settings.themeMode) {
        ThemeMode.SYSTEM -> "跟随系统"
        ThemeMode.LIGHT -> "浅色"
        ThemeMode.DARK -> "深色"
    }
    val colors = if (settings.dynamicColors) {
        "动态配色"
    } else {
        when (settings.colorPalette) {
            ColorPalette.ALICIAN -> "爱丽丝紫"
            ColorPalette.OCEAN -> "海洋蓝"
            ColorPalette.FOREST -> "森林绿"
            ColorPalette.ROSE -> "玫瑰红"
        }
    }
    val type = when (settings.typographySize) {
        TypographySize.COMPACT -> "紧凑字号"
        TypographySize.STANDARD -> "标准字号"
        TypographySize.LARGE -> "大号字体"
    }
    return "$mode · $colors · $type"
}

private fun formatBytes(size: Long): String = when {
    size >= 1024 * 1024 -> String.format(Locale.US, "%.1f MB", size / 1024.0 / 1024.0)
    size >= 1024 -> String.format(Locale.US, "%.1f KB", size / 1024.0)
    else -> "$size B"
}
