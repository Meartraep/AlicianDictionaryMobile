package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Build
import androidx.compose.material.icons.outlined.DataObject
import androidx.compose.material.icons.outlined.Download
import androidx.compose.material.icons.outlined.MoreVert
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.data.DataDiagnosis
import com.meartraep.alician.mobile.data.GlobalMatch

/** 数据工作区「维护」菜单里的动作。 */
internal enum class MaintenanceAction {
    RECOUNT_WORDS,
    REBUILD_NO_CLASS,
    GLOBAL_REPLACE,
    EXPORT_CSV,
    EXPORT_SQLITE,
    DIAGNOSE,
}

/**
 * 「维护」入口：维护动作与导出都从词典数据区进入（数据库管理页只保留浏览）。
 */
@Composable
internal fun MaintenanceMenu(
    onAction: (MaintenanceAction) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    Box(modifier = modifier) {
        OutlinedButton(onClick = { expanded = true }) {
            Icon(Icons.Outlined.MoreVert, contentDescription = null)
            Spacer(Modifier.width(4.dp))
            Text("维护")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DropdownMenuItem(
                text = { Text("重算词频与泛度") },
                leadingIcon = { Icon(Icons.Outlined.Refresh, contentDescription = null) },
                onClick = {
                    expanded = false
                    onAction(MaintenanceAction.RECOUNT_WORDS)
                },
            )
            DropdownMenuItem(
                text = { Text("重建 no_class") },
                leadingIcon = { Icon(Icons.Outlined.Build, contentDescription = null) },
                onClick = {
                    expanded = false
                    onAction(MaintenanceAction.REBUILD_NO_CLASS)
                },
            )
            DropdownMenuItem(
                text = { Text("全局替换…") },
                leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                onClick = {
                    expanded = false
                    onAction(MaintenanceAction.GLOBAL_REPLACE)
                },
            )
            DropdownMenuItem(
                text = { Text("导出全部 CSV（ZIP）") },
                leadingIcon = { Icon(Icons.Outlined.Download, contentDescription = null) },
                onClick = {
                    expanded = false
                    onAction(MaintenanceAction.EXPORT_CSV)
                },
            )
            DropdownMenuItem(
                text = { Text("导出 SQLite 数据库") },
                leadingIcon = { Icon(Icons.Outlined.Download, contentDescription = null) },
                onClick = {
                    expanded = false
                    onAction(MaintenanceAction.EXPORT_SQLITE)
                },
            )
            DropdownMenuItem(
                text = { Text("数据库诊断") },
                leadingIcon = { Icon(Icons.Outlined.DataObject, contentDescription = null) },
                onClick = {
                    expanded = false
                    onAction(MaintenanceAction.DIAGNOSE)
                },
            )
        }
    }
}

/**
 * 维护动作的确认框：说明 + 恢复点提示 + 内联错误/成功（沿用 DataMutation 协议）。
 * 成功后不自动关闭，用户看到结果后点「完成」。
 */
@Composable
internal fun MaintenanceConfirmDialog(
    title: String,
    message: String,
    submitting: Boolean,
    successMessage: String?,
    errorMessage: String?,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    val done = successMessage != null
    AlertDialog(
        onDismissRequest = { if (!submitting) onDismiss() },
        modifier = Modifier.imePadding(),
        title = { Text(title) },
        text = {
            Column(
                modifier = Modifier
                    .heightIn(max = 380.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(message, style = MaterialTheme.typography.bodyMedium)
                if (successMessage != null) {
                    InfoBanner(successMessage)
                } else if (errorMessage != null) {
                    InfoBanner(errorMessage, isError = true)
                }
                InfoBanner("执行前会自动创建恢复点，可在 设置 → 数据库 中回退。")
            }
        },
        confirmButton = {
            Button(
                onClick = { if (done) onDismiss() else onConfirm() },
                enabled = !submitting,
            ) {
                when {
                    submitting -> {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp,
                        )
                        Spacer(Modifier.width(6.dp))
                        Text("执行中…")
                    }
                    done -> Text("完成")
                    else -> Text("开始执行")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !submitting) { Text("取消") }
        },
    )
}

/**
 * 全局替换：关键词 + 替换为 + 预览（命中数与前 20 条），应用走 DataMutation 协议。
 * 预览结果在 ViewModel；输入变化时由宿主清空预览，避免“预览后改词”造成错配。
 */
@Composable
internal fun ReplaceDialog(
    keyword: String,
    replacement: String,
    matches: List<GlobalMatch>,
    previewLoaded: Boolean,
    submitting: Boolean,
    successMessage: String?,
    errorMessage: String?,
    onKeywordChange: (String) -> Unit,
    onReplacementChange: (String) -> Unit,
    onPreview: () -> Unit,
    onApply: () -> Unit,
    onDismiss: () -> Unit,
) {
    val done = successMessage != null
    val previewMatches = remember(matches) { matches.take(20) }
    AlertDialog(
        onDismissRequest = { if (!submitting) onDismiss() },
        modifier = Modifier.imePadding(),
        title = { Text("全局替换") },
        text = {
            Column(
                modifier = Modifier
                    .heightIn(max = 460.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                InfoBanner("只替换可编辑表；执行前会自动创建恢复点，可在 设置 → 数据库 中回退。")
                OutlinedTextField(
                    value = keyword,
                    onValueChange = onKeywordChange,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("查找内容") },
                    singleLine = true,
                    enabled = !submitting && !done,
                )
                // 后端是区分大小写的子串替换（"Xia" 与 "xia" 是不同词条），故明确提示。
                Text(
                    "区分大小写；先预览确认再替换",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = replacement,
                    onValueChange = onReplacementChange,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("替换为") },
                    singleLine = true,
                    enabled = !submitting && !done,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedButton(
                        onClick = onPreview,
                        enabled = keyword.isNotBlank() && !submitting && !done,
                    ) { Text("预览") }
                    when {
                        previewLoaded && matches.isEmpty() -> Text(
                            "没有匹配内容",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        matches.isNotEmpty() -> Text(
                            "命中 ${matches.size} 处",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        else -> Text(
                            "先预览再替换",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                if (matches.isNotEmpty()) {
                    Text(
                        "预览（最多显示 20 条）",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    previewMatches.forEach { match ->
                        Text(
                            "${match.table} · ${match.field}：${match.value}",
                            style = MaterialTheme.typography.bodySmall,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
                if (successMessage != null) {
                    InfoBanner(successMessage)
                } else if (errorMessage != null) {
                    InfoBanner(errorMessage, isError = true)
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { if (done) onDismiss() else onApply() },
                enabled = !submitting && (done || matches.isNotEmpty()),
            ) {
                when {
                    submitting -> {
                        CircularProgressIndicator(
                            modifier = Modifier.size(16.dp),
                            strokeWidth = 2.dp,
                        )
                        Spacer(Modifier.width(6.dp))
                        Text("替换中…")
                    }
                    done -> Text("完成")
                    else -> Text("替换 ${matches.size} 处")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !submitting) {
                Text(if (done) "关闭" else "取消")
            }
        },
    )
}

/** 数据库诊断：完整性、外键、孤儿行、表行数 top、本地修改与 pragma。 */
@Composable
internal fun DiagnosisDialog(
    diagnosis: DataDiagnosis?,
    onRefresh: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        modifier = Modifier.imePadding(),
        title = { Text("数据库诊断") },
        text = {
            if (diagnosis == null) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("正在检查数据库…")
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }
            } else {
                Column(
                    modifier = Modifier
                        .heightIn(max = 460.dp)
                        .verticalScroll(rememberScrollState()),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    val healthy = diagnosis.integrity.equals("ok", ignoreCase = true) &&
                        diagnosis.foreignKeyViolations == 0
                    InfoBanner(
                        if (healthy) {
                            "完整性检查通过（${diagnosis.integrity}），外键违规 " +
                                "${diagnosis.foreignKeyViolations}。"
                        } else {
                            "发现问题：完整性 ${diagnosis.integrity}，外键违规 " +
                                "${diagnosis.foreignKeyViolations}。"
                        },
                        isError = !healthy,
                    )
                    Text(
                        "本地修改：${diagnosis.localEdits} 条记录",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text("孤儿行", style = MaterialTheme.typography.titleSmall)
                    diagnosis.orphans.forEach { orphan ->
                        Row(modifier = Modifier.fillMaxWidth()) {
                            Text(
                                orphan.label,
                                modifier = Modifier.weight(1f),
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Text(
                                orphan.count.toString(),
                                style = MaterialTheme.typography.bodyMedium,
                                color = if (orphan.count > 0) {
                                    MaterialTheme.colorScheme.error
                                } else {
                                    MaterialTheme.colorScheme.onSurfaceVariant
                                },
                            )
                        }
                    }
                    Text("表行数（前 10）", style = MaterialTheme.typography.titleSmall)
                    diagnosis.tables
                        .sortedByDescending { it.rows }
                        .take(10)
                        .forEach { table ->
                            Row(modifier = Modifier.fillMaxWidth()) {
                                Text(
                                    "${table.name}（${table.group}）",
                                    modifier = Modifier.weight(1f),
                                    style = MaterialTheme.typography.bodySmall,
                                )
                                Text(
                                    table.rows.toString(),
                                    style = MaterialTheme.typography.bodySmall,
                                )
                            }
                        }
                    Text("Pragma", style = MaterialTheme.typography.titleSmall)
                    diagnosis.pragmas.toSortedMap().forEach { (key, value) ->
                        Text(
                            "$key = $value",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("关闭") } },
        dismissButton = { TextButton(onClick = onRefresh) { Text("重新检查") } },
    )
}
