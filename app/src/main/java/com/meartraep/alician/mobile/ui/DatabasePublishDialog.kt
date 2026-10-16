package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CloudUpload
import androidx.compose.material.icons.outlined.Key
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.data.PublishCredential
import com.meartraep.alician.mobile.data.PublishLogic
import com.meartraep.alician.mobile.data.PublishStage
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// Kept outside the composable: reading the locale during composition is not
// observable and lint rejects it (NonObservableLocale).
private fun formatVerifiedAt(timestamp: Long): String =
    if (timestamp > 0L) {
        SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.getDefault()).format(Date(timestamp))
    } else {
        "尚未校验"
    }

/** Settings entry point for publishing the database from this phone. */
@Composable
fun DatabasePublishCard(
    credential: PublishCredential,
    onConfigure: () -> Unit,
    onClear: () -> Unit,
    onPublish: () -> Unit,
) {
    SettingsCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Outlined.CloudUpload, contentDescription = null)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("发布数据库到 GitHub", style = MaterialTheme.typography.titleSmall)
                Text(
                    "只上传本地数据库；版本号、台账与清单由 CI 自动生成",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        if (credential.configured) {
            DatabaseMetricLine("访问令牌", credential.maskedToken.ifBlank { "已保存" })
            DatabaseMetricLine("上次校验", formatVerifiedAt(credential.verifiedAt))
        }
        Text(
            if (credential.configured) {
                "令牌以 Android Keystore 加密保存在本机，不会随备份同步。"
            } else {
                "需要一次性配置细粒度访问令牌（仅本仓库、仅 Contents 读写）。"
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onConfigure, modifier = Modifier.weight(1f)) {
                Icon(Icons.Outlined.Key, contentDescription = null)
                Spacer(Modifier.width(6.dp))
                Text(if (credential.configured) "更换令牌" else "配置令牌")
            }
            if (credential.configured) {
                OutlinedButton(onClick = onClear, modifier = Modifier.weight(1f)) {
                    Text("清除令牌")
                }
            }
        }
        Button(
            onClick = onPublish,
            modifier = Modifier.fillMaxWidth(),
            enabled = credential.configured,
        ) {
            Icon(Icons.Outlined.CloudUpload, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("发布新版本")
        }
    }
}

/** One-time entry of the fine-grained GitHub token. */
@Composable
fun PublishTokenDialog(onSave: (String) -> Unit, onDismiss: () -> Unit) {
    var token by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        icon = { Icon(Icons.Outlined.Key, contentDescription = null) },
        title = { Text("配置发布令牌") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "在 GitHub 创建 fine-grained token：仅授权本仓库，权限只勾选 " +
                        "Contents: Read and write，有效期尽量短。",
                    style = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(
                    value = token,
                    onValueChange = { token = it },
                    label = { Text("GitHub 访问令牌") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                    modifier = Modifier.fillMaxWidth(),
                )
                Text(
                    "令牌会先用 Android Keystore 生成的密钥加密，再存入独立的首选项文件，" +
                        "并已排除出系统备份。随时可在此清除。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            Button(onClick = { onSave(token) }, enabled = token.isNotBlank()) { Text("保存并校验") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("取消") } },
    )
}

/**
 * Publishing wizard: local preview, upload progress, then the pull request the CI
 * pipeline stamps and verifies.
 */
@Composable
fun DatabasePublishDialog(viewModel: MainViewModel, onDismiss: () -> Unit) {
    val uriHandler = LocalUriHandler.current
    val preview = viewModel.publishPreview
    val outcome = viewModel.publishOutcome
    val progress = viewModel.publishProgress
    val pullRequest = viewModel.publishPullRequest
    var notes by rememberSaveable { mutableStateOf("") }
    val uploading = progress.stage == PublishStage.VERIFYING ||
        progress.stage == PublishStage.UPLOADING ||
        progress.stage == PublishStage.OPENING_PULL_REQUEST

    AlertDialog(
        onDismissRequest = { if (!uploading) onDismiss() },
        icon = { Icon(Icons.Outlined.CloudUpload, contentDescription = null) },
        title = {
            Text(
                when {
                    outcome != null -> "发布请求已创建"
                    uploading -> "正在发布…"
                    else -> "发布数据库"
                },
            )
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                viewModel.publishError?.let { message ->
                    Text(message, color = MaterialTheme.colorScheme.error)
                }
                if (outcome == null && preview == null) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(modifier = Modifier.height(18.dp).width(18.dp))
                        Spacer(Modifier.width(10.dp))
                        Text("正在读取本地数据库…", style = MaterialTheme.typography.bodySmall)
                    }
                }
                preview?.let { value ->
                    Text(
                        "本地数据库 v" + value.localVersion + " · " +
                            PublishLogic.formatMegabytes(value.localSize),
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    Text(
                        "本地指纹 " + value.localSha1.take(12) + "…",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Text(
                        "已发布指纹 " + value.publishedSha1.take(12) + "…",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    value.blockingReason?.let { reason ->
                        Text(reason, color = MaterialTheme.colorScheme.error)
                    }
                }
                if (uploading) {
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    Text(progress.detail, style = MaterialTheme.typography.bodySmall)
                }
                if (outcome != null) {
                    Text(
                        "合并请求 #" + outcome.pullRequestNumber,
                        style = MaterialTheme.typography.titleSmall,
                    )
                    Text(
                        "CI 会为该数据库分配下一个版本号（v" +
                            ((preview?.publishedVersion ?: 0) + 1) +
                            "）、追加台账并校验全部不变式。通过后合并即可对所有客户端生效。",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    pullRequest?.let { state ->
                        Text(
                            "状态：" + state.state + " · " + state.mergeableState,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                if (outcome == null && preview?.blockingReason == null && !uploading) {
                    OutlinedTextField(
                        value = notes,
                        onValueChange = { notes = it },
                        label = { Text("版本说明（会显示在更新提示里）") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        },
        confirmButton = {
            when {
                outcome != null -> Button(onClick = { uriHandler.openUri(outcome.pullRequestUrl) }) {
                    Text("打开合并请求")
                }
                preview?.blockingReason != null -> Button(onClick = onDismiss) { Text("关闭") }
                else -> Button(
                    onClick = { viewModel.publishDatabase(notes) },
                    enabled = !uploading && preview != null,
                ) { Text("开始上传") }
            }
        },
        dismissButton = {
            if (outcome != null) {
                Row {
                    TextButton(onClick = { viewModel.refreshPublishPullRequest() }) { Text("检查状态") }
                    TextButton(onClick = { viewModel.mergePublishPullRequest() }) { Text("合并") }
                    TextButton(onClick = onDismiss) { Text("完成") }
                }
            } else {
                TextButton(onClick = onDismiss, enabled = !uploading) { Text("取消") }
            }
        },
    )
}
