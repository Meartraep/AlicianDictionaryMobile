package com.meartraep.alician.mobile.ui

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
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.OpenInNew
import androidx.compose.material.icons.outlined.ChevronRight
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.NewReleases
import androidx.compose.material.icons.outlined.Palette
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Storage
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.BuildConfig
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.data.AppUpdateInfo
import com.meartraep.alician.mobile.data.ColorPalette
import com.meartraep.alician.mobile.data.ThemeMode
import com.meartraep.alician.mobile.data.TypographySize
import com.meartraep.alician.mobile.data.UiSettings

/**
 * 设置页：界面设置 + 档案版本信息。
 * 数据库相关的一切（版本/更新/恢复点/发布/数据来源）已合并进「数据库」治理页。
 */
@Composable
fun SettingsScreen(viewModel: MainViewModel, padding: PaddingValues) {
    var showUiSettings by rememberSaveable { mutableStateOf(false) }
    var showDatabaseGovernance by rememberSaveable { mutableStateOf(false) }
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
    if (showDatabaseGovernance) {
        DatabaseGovernanceScreen(
            viewModel = viewModel,
            onBack = { showDatabaseGovernance = false },
            padding = padding,
        )
        return
    }

    val uriHandler = LocalUriHandler.current
    // 设置页的「数据库」卡需要身份摘要；进入治理页时治理页会再刷新一次。
    LaunchedEffect(Unit) {
        if (viewModel.govIdentity == null) viewModel.refreshGovIdentity()
    }
    val identity = viewModel.govIdentity
    val databaseSummary = when {
        identity == null -> "读取中…"
        identity.localModified -> "v${identity.dbVersion} · 本地已修改 ${identity.localEdits} 处"
        else -> "v${identity.dbVersion} · 无本地修改"
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
            Column(Modifier.fillMaxWidth()) {
                Text("设置", style = MaterialTheme.typography.headlineMedium)
                Text(
                    "显示、数据库治理与版本信息",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
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
        item {
            SectionHeader("数据库", "版本、更新、恢复点、发布与数据来源")
        }
        item {
            Card(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable { showDatabaseGovernance = true },
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.secondaryContainer,
                    contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
                ),
            ) {
                Row(
                    modifier = Modifier.padding(18.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Outlined.Storage, contentDescription = null)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        Text("数据库", style = MaterialTheme.typography.titleMedium)
                        Text(
                            databaseSummary,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                    Icon(Icons.Outlined.ChevronRight, contentDescription = "进入数据库治理")
                }
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
        item(span = { GridItemSpan(maxLineSpan) }) {
            InfoBanner(
                "本应用基于 Meartraep/Alician_dictionary 的 Lite 版开发，遵循 " +
                    "CC BY-NC-SA 4.0，限非商业用途。移动端保留词典、歌词上下文、" +
                    "写作检查、双向翻译、数据库治理与数据更新能力。",
            )
        }
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
internal fun SettingsCard(content: @Composable () -> Unit) {
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
internal fun DatabaseMetricLine(label: String, value: String) {
    Row(Modifier.fillMaxWidth()) {
        Text(
            label,
            modifier = Modifier.weight(1f),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(value, style = MaterialTheme.typography.labelLarge)
    }
}

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
