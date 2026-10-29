package com.meartraep.alician.mobile.ui

import android.app.Activity
import android.app.KeyguardManager
import android.content.Context
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CloudUpload
import androidx.compose.material.icons.outlined.ContentCopy
import androidx.compose.material.icons.outlined.Key
import androidx.compose.material.icons.outlined.VerifiedUser
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
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.data.DeviceCode
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
    authMode: String,
    onConfigure: () -> Unit,
    onAppLogin: () -> Unit,
    onAppSignOut: () -> Unit,
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
                    "手机写入版本号并提交数据库、台账与清单；CI 只做校验",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        DatabaseMetricLine(
            "登录方式",
            when (authMode) {
                "app" -> "GitHub App（短时令牌，自动刷新）"
                "token" -> "长期访问令牌"
                else -> "未登录"
            },
        )
        if (credential.configured) {
            DatabaseMetricLine("访问令牌", credential.maskedToken.ifBlank { "已保存" })
            DatabaseMetricLine("上次校验", formatVerifiedAt(credential.verifiedAt))
        }
        Text(
            when (authMode) {
                "app" -> "手机只保存可轮换的刷新令牌；在 GitHub 卸载该 App 即可一次性吊销。"
                "token" -> "凭据以 Android Keystore 加密保存在本机，不会随备份同步。"
                else -> "推荐用 GitHub App 登录（无需长期令牌）；也可以配置细粒度访问令牌。"
            },
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (authMode == "app") {
                OutlinedButton(onClick = onAppSignOut, modifier = Modifier.weight(1f)) {
                    Text("退出 App 登录")
                }
            } else {
                OutlinedButton(onClick = onAppLogin, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Outlined.VerifiedUser, contentDescription = null)
                    Spacer(Modifier.width(6.dp))
                    Text("用 GitHub App 登录")
                }
            }
            OutlinedButton(onClick = onConfigure, modifier = Modifier.weight(1f)) {
                Icon(Icons.Outlined.Key, contentDescription = null)
                Spacer(Modifier.width(6.dp))
                Text(if (credential.configured) "更换令牌" else "配置令牌")
            }
        }
        Button(
            onClick = onPublish,
            modifier = Modifier.fillMaxWidth(),
            enabled = authMode != "none",
        ) {
            Icon(Icons.Outlined.CloudUpload, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text("发布新版本")
        }
        if (authMode != "none") {
            OutlinedButton(onClick = onClear, modifier = Modifier.fillMaxWidth()) {
                Text("清除全部凭据")
            }
        }
    }
}

/**
 * GitHub App device flow: the user approves the app once in a browser; afterwards
 * the phone only holds short-lived tokens and a rotating refresh token.
 */
@Composable
fun PublishAppLoginDialog(
    clientId: String,
    code: DeviceCode?,
    message: String,
    running: Boolean,
    onStart: (String) -> Unit,
    onDismiss: () -> Unit,
) {
    var field by rememberSaveable { mutableStateOf(clientId) }
    val uriHandler = LocalUriHandler.current
    AlertDialog(
        modifier = Modifier.imePadding(),
        onDismissRequest = { if (!running) onDismiss() },
        icon = { Icon(Icons.Outlined.VerifiedUser, contentDescription = null) },
        title = { Text(if (code == null) "用 GitHub App 登录" else "在浏览器中确认") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (code == null) {
                    Text(
                        "填入 GitHub App 的 Client ID（公开信息）。App 需要 Contents: Read and write " +
                            "权限，并已安装到本仓库。",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    OutlinedTextField(
                        value = field,
                        onValueChange = { field = it },
                        label = { Text("Client ID") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                } else {
                    Text("在浏览器输入这个用户码：", style = MaterialTheme.typography.bodySmall)
                    Text(code.userCode, style = MaterialTheme.typography.headlineSmall)
                    Text(message, style = MaterialTheme.typography.bodySmall)
                    OutlinedButton(
                        onClick = { uriHandler.openUri(code.verificationUri) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("打开 " + code.verificationUri)
                    }
                    if (running) {
                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    }
                }
            }
        },
        confirmButton = {
            if (code == null) {
                Button(onClick = { onStart(field) }, enabled = field.isNotBlank()) { Text("获取设备码") }
            } else {
                TextButton(onClick = onDismiss, enabled = !running) { Text("完成") }
            }
        },
        dismissButton = {
            if (code == null) {
                TextButton(onClick = onDismiss) { Text("取消") }
            } else {
                TextButton(onClick = { uriHandler.openUri(code.verificationUri) }) { Text("重新打开") }
            }
        },
    )
}

/** The device key that authorises publications. */
@Composable
fun PublishSigningCard(
    ready: Boolean,
    keyId: String?,
    requiresAuth: Boolean,
    deviceIsSecure: Boolean,
    onCreate: () -> String?,
    onCopy: () -> String?,
    onClear: () -> Unit,
) {
    val clipboard = LocalClipboardManager.current
    var copied by remember { mutableStateOf(false) }
    SettingsCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Outlined.VerifiedUser, contentDescription = null)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text("发布签名密钥", style = MaterialTheme.typography.titleSmall)
                Text(
                    if (ready) {
                        "已生成，私钥不可导出，只存在于本机 Keystore"
                    } else {
                        "尚未生成，无法发布数据库"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        if (ready) {
            DatabaseMetricLine("密钥指纹", keyId.orEmpty())
            DatabaseMetricLine(
                "签名保护",
                if (requiresAuth) "需要设备锁屏验证" else "未绑定锁屏（本机未设置锁屏）",
            )
        } else if (!deviceIsSecure) {
            Text(
                "本机没有设置锁屏：密钥仍然不可导出，但无法要求发布前验证设备。",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.error,
            )
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(
                onClick = {
                    val pem = if (ready) onCopy() else onCreate()
                    if (!pem.isNullOrBlank()) {
                        clipboard.setText(AnnotatedString(pem))
                        copied = true
                    }
                },
                modifier = Modifier.weight(1f),
            ) {
                Icon(Icons.Outlined.ContentCopy, contentDescription = null)
                Spacer(Modifier.width(6.dp))
                Text(if (ready) "复制公钥" else "生成密钥")
            }
            if (ready) {
                OutlinedButton(onClick = onClear, modifier = Modifier.weight(1f)) {
                    Text("删除密钥")
                }
            }
        }
        Text(
            if (copied) {
                "公钥已复制。请用一个普通 PR 提交为 .github/db-publish-pubkey.pem（CI 从 main 读取）。"
            } else {
                "生成后需把公钥登记到 main：CI 只接受用这把密钥签名的发布。"
            },
            style = MaterialTheme.typography.bodySmall,
            color = if (copied) {
                MaterialTheme.colorScheme.primary
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            },
        )
    }
}

/** One-time entry of the fine-grained GitHub token. */
@Composable
fun PublishTokenDialog(onSave: (String) -> Unit, onDismiss: () -> Unit) {
    var token by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        modifier = Modifier.imePadding(),
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
    var notes by rememberSaveable { mutableStateOf("") }
    val context = LocalContext.current
    val keyguard = remember {
        context.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager
    }
    // The signing key is bound to the lock screen, so publishing asks for the device
    // credential first; without it the Keystore refuses to sign anyway.
    val authLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        if (result.resultCode == Activity.RESULT_OK) {
            viewModel.publishDatabase(notes)
        } else {
            viewModel.reportPublishCancelled()
        }
    }
    val startPublish: () -> Unit = {
        @Suppress("DEPRECATION")
        val intent = if (viewModel.publishSigningRequiresAuth) {
            keyguard.createConfirmDeviceCredentialIntent("验证以发布数据库", "发布需要确认设备锁屏")
        } else {
            null
        }
        if (intent != null) authLauncher.launch(intent) else viewModel.publishDatabase(notes)
    }
    val preview = viewModel.publishPreview
    val outcome = viewModel.publishOutcome
    val progress = viewModel.publishProgress
    val pullRequest = viewModel.publishPullRequest
    val uploading = progress.stage == PublishStage.VERIFYING ||
        progress.stage == PublishStage.UPLOADING ||
        progress.stage == PublishStage.OPENING_PULL_REQUEST

    AlertDialog(
        modifier = Modifier.imePadding(),
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
                            PublishLogic.formatMegabytes(value.localSize) +
                            " → 将发布为 v" + value.nextVersion,
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
                        "数据库已按 v" + (preview?.nextVersion ?: 0) + " 写入版本号并追加台账；" +
                            "CI 会校验版本号必须正好是下一个、且只改动了这三个文件。合并后对所有客户端生效。",
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
                    onClick = startPublish,
                    enabled = !uploading && preview != null && viewModel.publishSigningReady,
                ) { Text(if (viewModel.publishSigningReady) "开始上传" else "请先生成签名密钥") }
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
