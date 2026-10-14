package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.CloudDownload
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.data.DatabaseUpdateLogic
import com.meartraep.alician.mobile.data.DatabaseUpdateManifest

/**
 * Startup prompt for a published database revision.
 *
 * Nothing is downloaded until the user taps 立即更新; 稍后 only defers this exact
 * revision, so the next release asks again.
 */
@Composable
fun DatabaseUpdateDialog(
    manifest: DatabaseUpdateManifest,
    localVersion: Int,
    applying: Boolean,
    onApply: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = { if (!applying) onDismiss() },
        icon = { Icon(Icons.Outlined.CloudDownload, contentDescription = null) },
        title = { Text("发现数据库更新") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    DatabaseUpdateLogic.summary(localVersion, manifest),
                    style = MaterialTheme.typography.bodyMedium,
                )
                if (manifest.publishedAt.isNotBlank()) {
                    Text(
                        "发布时间：" + manifest.publishedAt,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (manifest.notes.isNotBlank()) {
                    Text("更新内容：" + manifest.notes, style = MaterialTheme.typography.bodySmall)
                }
                Text(
                    "更新前会自动备份当前数据库；下载完成后立即生效。",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (applying) {
                    Text("正在下载…", style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            Button(onClick = onApply, enabled = !applying) { Text("立即更新") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !applying) { Text("稍后") }
        },
    )
}
