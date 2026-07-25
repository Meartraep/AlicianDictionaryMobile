package com.meartraep.alician.mobile.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CloudDownload
import androidx.compose.material.icons.outlined.FolderOpen
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.RestartAlt
import androidx.compose.material.icons.outlined.Save
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.BuildConfig
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.data.RemoteComparison
import java.util.Locale

@Composable
fun SettingsScreen(viewModel: MainViewModel, padding: PaddingValues) {
    var confirmReset by remember { mutableStateOf(false) }
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
        item { SectionHeader("显示") }
        item {
            SettingsCard {
                SettingSwitchRow(
                    title = "显示爱丽丝语原字体",
                    detail = "应用于词典词头、写作文本、歌词和翻译内容",
                    checked = viewModel.alicianFontEnabled,
                    onCheckedChange = viewModel::setAlicianFont,
                )
                SettingSwitchRow(
                    title = "Material You 动态配色",
                    detail = "Android 12 及以上使用系统壁纸色彩",
                    checked = viewModel.dynamicColorsEnabled,
                    onCheckedChange = viewModel::setDynamicColors,
                )
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
    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(if (comparison.upToDate) "数据库已是最新" else "发现数据库更新")
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(comparison.message)
                if (!comparison.upToDate) {
                    Text(
                        "本地 → 云端",
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    val labels = mapOf(
                        "words" to "词头",
                        "senses" to "释义",
                        "songs" to "歌曲",
                        "phrases" to "词组",
                    )
                    labels.forEach { (key, label) ->
                        DatabaseMetricLine(
                            label,
                            "${comparison.localCounts[key] ?: 0} → " +
                                "${comparison.remoteCounts[key] ?: 0}",
                        )
                    }
                    Text(
                        "应用更新会先备份当前数据库，再替换为云端版本。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        },
        confirmButton = {
            if (!comparison.upToDate) {
                Button(onClick = onApply) { Text("备份并更新") }
            } else {
                Button(onClick = onDismiss) { Text("完成") }
            }
        },
        dismissButton = {
            if (!comparison.upToDate) {
                TextButton(onClick = onDismiss) { Text("稍后") }
            }
        },
    )
}

private fun formatBytes(size: Long): String = when {
    size >= 1024 * 1024 -> String.format(Locale.US, "%.1f MB", size / 1024.0 / 1024.0)
    size >= 1024 -> String.format(Locale.US, "%.1f KB", size / 1024.0)
    else -> "$size B"
}

