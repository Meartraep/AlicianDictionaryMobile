package com.meartraep.alician.mobile.ui

import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.CloudDownload
import androidx.compose.material.icons.outlined.FolderOpen
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.RestartAlt
import androidx.compose.material.icons.outlined.Save
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.data.BackupEntry
import com.meartraep.alician.mobile.data.DatabaseRowDiff
import com.meartraep.alician.mobile.data.DatabaseTableDiff
import com.meartraep.alician.mobile.data.RemoteComparison
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * 数据库治理页（P4）：版本与身份 / 更新 / 恢复点与回退 / 发布 / 数据来源。
 *
 * 原设置页里的数据库区块整体迁到这里；所有写入仍走统一写守卫与恢复点链路，
 * 危险操作先确认、失败内联显示。
 */
@Composable
fun DatabaseGovernanceScreen(
    viewModel: MainViewModel,
    onBack: () -> Unit,
    padding: PaddingValues = PaddingValues(),
) {
    BackHandler(onBack = onBack)
    var showPublishTokenDialog by rememberSaveable { mutableStateOf(false) }
    var showPublishAppDialog by rememberSaveable { mutableStateOf(false) }
    var showPublishDialog by rememberSaveable { mutableStateOf(false) }
    var showCreateBackupConfirm by rememberSaveable { mutableStateOf(false) }
    var restorePath by rememberSaveable { mutableStateOf("") }
    var confirmReset by rememberSaveable { mutableStateOf(false) }
    val backupCreateState = remember { DataMutationUiState() }
    val backupRestoreState = remember { DataMutationUiState() }

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

    LaunchedEffect(Unit) {
        viewModel.refreshGovIdentity()
        viewModel.refreshGovBackups()
    }
    // 恢复内置库 / 导入 / 上游更新成功后 databaseInfo 会变；此时同步刷新治理信息。
    LaunchedEffect(viewModel.databaseInfo.sha256) {
        val identity = viewModel.govIdentity ?: return@LaunchedEffect
        if (viewModel.databaseInfo.sha256.isNotBlank() &&
            identity.sha256 != viewModel.databaseInfo.sha256
        ) {
            viewModel.refreshGovIdentity()
            viewModel.refreshGovBackups()
        }
    }

    // 成功/失败都在对话框内联显示，由用户点「完成/取消」关闭（与词典维护对话框一致）。
    DataMutationEffect(
        mutation = viewModel.dataMutation,
        state = backupCreateState,
        onConsume = viewModel::consumeDataMutation,
        onSuccess = {},
    )
    DataMutationEffect(
        mutation = viewModel.dataMutation,
        state = backupRestoreState,
        onConsume = viewModel::consumeDataMutation,
        onSuccess = {},
    )

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
                    Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "返回设置")
                }
                Spacer(Modifier.width(4.dp))
                Column(Modifier.weight(1f)) {
                    Text("数据库", style = MaterialTheme.typography.headlineMedium)
                    Text(
                        "版本、更新、恢复点、发布与数据来源",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        // ---- 1. 版本与身份 ----
        item { SectionHeader("版本与身份", "本机数据库的只读身份与本地修改计数") }
        item {
            SettingsCard {
                val identity = viewModel.govIdentity
                if (identity == null) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(
                            modifier = Modifier
                                .width(18.dp)
                                .height(18.dp),
                            strokeWidth = 2.dp,
                        )
                        Spacer(Modifier.width(10.dp))
                        Text("正在读取数据库信息…", style = MaterialTheme.typography.bodySmall)
                    }
                } else {
                    DatabaseMetricLine(
                        "版本",
                        "v${identity.dbVersion}" +
                            if (identity.format.isNotBlank()) " · ${identity.format}" else "",
                    )
                    DatabaseMetricLine("发布", identity.publishedAt.ifBlank { "未知" })
                    DatabaseMetricLine(
                        "本地修改",
                        if (identity.localModified) "${identity.localEdits} 处" else "无",
                    )
                    if (identity.localModified) {
                        InfoBanner(
                            "本地已有 ${identity.localEdits} 处修改：更新数据库会覆盖这些修改，" +
                                "建议先创建恢复点。",
                            isError = true,
                        )
                    }
                    DatabaseMetricLine(
                        "词头 / 歌曲 / 数据表",
                        "${identity.wordCount} / ${identity.songCount} / ${identity.tableCount}",
                    )
                    DatabaseMetricLine("大小", formatBytes(identity.size))
                    DatabaseMetricLine("修改时间", identity.modified.ifBlank { "未知" })
                    DatabaseMetricLine(
                        "SHA-256",
                        identity.sha256.take(16).ifBlank { "尚未读取" } +
                            if (identity.sha256.length > 16) "…" else "",
                    )
                    DatabaseMetricLine(
                        "恢复点",
                        "${identity.backupCount} 个" +
                            (identity.latestBackup?.let {
                                " · 最近 " + formatBackupTime(it.createdAt)
                            } ?: ""),
                    )
                    if (identity.notes.isNotBlank()) {
                        Text(
                            "发布说明：${identity.notes}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }
        item {
            OutlinedButton(
                onClick = {
                    viewModel.refreshGovIdentity()
                    viewModel.refreshGovBackups()
                },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Outlined.Refresh, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("刷新")
            }
        }

        // ---- 2. 更新 ----
        item { SectionHeader("数据库更新", "每次启动自动检查 GitHub 上的发布清单") }
        item {
            SettingsCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("启动时自动检查", style = MaterialTheme.typography.titleSmall)
                        Text(
                            "发现新版本时弹出提示，确认后才下载",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(
                        checked = viewModel.autoDatabaseUpdateCheck,
                        onCheckedChange = viewModel::updateAutoDatabaseUpdateCheck,
                    )
                }
                DatabaseMetricLine("本地数据库版本", "v" + viewModel.localDatabaseVersion)
                viewModel.latestPublishedManifest?.let { manifest ->
                    DatabaseMetricLine("云端版本", "v${manifest.dbVersion}")
                }
                DatabaseMetricLine("最近检查", formatLastCheck(viewModel.lastDatabaseCheckAt))
                viewModel.databaseUpdateError?.let { message ->
                    Text(
                        message,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }
        item {
            Button(
                onClick = viewModel::checkDatabaseUpdate,
                modifier = Modifier.fillMaxWidth(),
                enabled = !viewModel.checkingDatabaseUpdate,
            ) {
                Icon(Icons.Outlined.CloudDownload, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(if (viewModel.checkingDatabaseUpdate) "正在检查…" else "立即检查数据库更新")
            }
        }

        // ---- 3. 恢复点与回退 ----
        item { SectionHeader("恢复点与回退", "恢复前会先为当前数据库创建安全备份") }
        item {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(
                    onClick = {
                        backupCreateState.reset()
                        showCreateBackupConfirm = true
                    },
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Outlined.Save, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("创建恢复点")
                }
                OutlinedButton(
                    onClick = { viewModel.refreshGovBackups() },
                    modifier = Modifier.weight(1f),
                ) {
                    Icon(Icons.Outlined.Refresh, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("刷新列表")
                }
            }
        }
        if (viewModel.govBackups.isEmpty()) {
            item {
                InfoBanner("还没有恢复点。编辑、删除、维护、发布前都会自动创建恢复点。")
            }
        } else {
            items(viewModel.govBackups, key = { it.path }) { backup ->
                RestorePointCard(
                    backup = backup,
                    onRestore = {
                        backupRestoreState.reset()
                        restorePath = backup.path
                    },
                )
            }
        }
        item {
            OutlinedButton(
                onClick = { confirmReset = true },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Outlined.RestartAlt, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("恢复 APK 内置数据库", color = MaterialTheme.colorScheme.error)
            }
        }

        // ---- 4. 发布 ----
        item {
            SectionHeader(
                "手机端发布",
                "手机写入版本号并用设备密钥签名；CI 只做校验",
            )
        }
        item {
            PublishSigningCard(
                ready = viewModel.publishSigningReady,
                keyId = viewModel.publishSigningKeyId,
                requiresAuth = viewModel.publishSigningRequiresAuth,
                deviceIsSecure = viewModel.publishDeviceIsSecure,
                onCreate = viewModel::createPublishSigningKey,
                onCopy = viewModel::publishSigningPublicKey,
                onClear = viewModel::clearPublishSigningKey,
            )
        }
        item {
            DatabasePublishCard(
                credential = viewModel.publishCredential,
                authMode = viewModel.publishAuthMode,
                onConfigure = { showPublishTokenDialog = true },
                onAppLogin = { showPublishAppDialog = true },
                onAppSignOut = viewModel::signOutPublishApp,
                onClear = viewModel::clearPublishToken,
                onPublish = {
                    viewModel.prepareDatabasePublish()
                    showPublishDialog = true
                },
            )
        }

        // ---- 5. 数据来源 ----
        item {
            SectionHeader(
                "数据来源",
                "Meartraep/Alician_dictionary 的全量数据，不含官方日/英译词",
            )
        }
        item {
            SettingsCard {
                Text(
                    "上游完整数据库与 APK 内置库分开：检查上游后可以查看逐表差异，" +
                        "采纳前会自动备份当前数据库。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedButton(
                    onClick = viewModel::checkRemoteUpdate,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(Icons.Outlined.CloudDownload, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("检查并导入上游完整数据库")
                }
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
                        Text("导入本地文件")
                    }
                    OutlinedButton(
                        onClick = { exportLauncher.launch("translated.db") },
                        modifier = Modifier.weight(1f),
                    ) {
                        Icon(Icons.Outlined.Save, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text("导出当前数据库")
                    }
                }
            }
        }
    }

    if (showCreateBackupConfirm) {
        MaintenanceConfirmDialog(
            title = "创建恢复点？",
            message = "会立即为当前数据库创建一个可回退的恢复点（数据库文件 + 校验信息）。",
            submitting = backupCreateState.submitting,
            successMessage = backupCreateState.successMessage,
            errorMessage = backupCreateState.errorMessage,
            onConfirm = {
                backupCreateState.begin()
                viewModel.createGovBackup()
            },
            onDismiss = {
                backupCreateState.reset()
                showCreateBackupConfirm = false
            },
        )
    }

    val restoreBackup = viewModel.govBackups.firstOrNull { it.path == restorePath }
    if (restoreBackup != null) {
        MaintenanceConfirmDialog(
            title = "恢复到此恢复点？",
            message = "将用「${formatBackupTime(restoreBackup.createdAt)} · v${restoreBackup.dbVersion}」" +
                "替换当前数据库；恢复前会先为当前数据库创建安全备份。",
            submitting = backupRestoreState.submitting,
            successMessage = backupRestoreState.successMessage,
            errorMessage = backupRestoreState.errorMessage,
            onConfirm = {
                backupRestoreState.begin()
                viewModel.restoreGovBackup(restoreBackup.path)
            },
            onDismiss = {
                backupRestoreState.reset()
                restorePath = ""
            },
        )
    }

    if (confirmReset) {
        MaintenanceConfirmDialog(
            title = "恢复内置数据库？",
            message = "当前数据库会先自动备份，然后恢复为此 APK 附带的版本。" +
                "当前编辑不会丢失，但需要通过备份文件手动恢复。",
            submitting = false,
            successMessage = null,
            errorMessage = null,
            onConfirm = {
                confirmReset = false
                viewModel.resetDatabase()
            },
            onDismiss = { confirmReset = false },
        )
    }

    if (showPublishTokenDialog) {
        PublishTokenDialog(
            onSave = { token ->
                showPublishTokenDialog = false
                viewModel.savePublishToken(token)
            },
            onDismiss = { showPublishTokenDialog = false },
        )
    }
    if (showPublishAppDialog) {
        PublishAppLoginDialog(
            clientId = viewModel.publishClientId,
            code = viewModel.deviceFlowCode,
            message = viewModel.deviceFlowMessage,
            running = viewModel.deviceFlowRunning,
            onStart = viewModel::startDeviceFlowLogin,
            onDismiss = {
                showPublishAppDialog = false
                viewModel.cancelDeviceFlowLogin()
            },
        )
    }
    if (showPublishDialog) {
        DatabasePublishDialog(
            viewModel = viewModel,
            onDismiss = {
                showPublishDialog = false
                viewModel.dismissPublishDialog()
            },
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

/** 一条恢复点：时间、原因、版本与大小 + 恢复按钮。 */
@Composable
private fun RestorePointCard(
    backup: BackupEntry,
    onRestore: () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(
            modifier = Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(
                        formatBackupTime(backup.createdAt),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(
                        backupReasonLabel(backup.reason) + " · v${backup.dbVersion} · " +
                            formatBytes(backup.size),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                TextButton(onClick = onRestore) {
                    Text("恢复", color = MaterialTheme.colorScheme.error)
                }
            }
            Text(
                backup.name,
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun RemoteUpdateDialog(
    comparison: RemoteComparison,
    onApply: () -> Unit,
    onDismiss: () -> Unit,
) {
    if (comparison.upToDate) {
        androidx.compose.material3.AlertDialog(
            onDismissRequest = onDismiss,
            modifier = Modifier.imePadding(),
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

private fun formatBackupTime(createdAt: String): String =
    createdAt.replace('T', ' ').take(16).ifBlank { "未知时间" }

private fun backupReasonLabel(reason: String): String = when (reason) {
    "", "manual" -> "手动创建"
    "before_restore" -> "恢复前安全备份"
    "before_delete" -> "删除记录前"
    "before_delete_word" -> "删除词条前"
    "before_delete_sense" -> "删除义项前"
    "before_replace" -> "全局替换前"
    "before_maintenance_word_count" -> "重算词频前"
    "before_maintenance_class" -> "更新词性统计前"
    "before_maintenance_no_class" -> "重建 no_class 前"
    else -> reason
}

private fun formatLastCheck(timestamp: Long): String =
    if (timestamp <= 0L) {
        "尚未检查"
    } else {
        SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date(timestamp))
    }

private fun formatBytes(size: Long): String = when {
    size >= 1024 * 1024 -> String.format(Locale.US, "%.1f MB", size / 1024.0 / 1024.0)
    size >= 1024 -> String.format(Locale.US, "%.1f KB", size / 1024.0)
    else -> "$size B"
}
