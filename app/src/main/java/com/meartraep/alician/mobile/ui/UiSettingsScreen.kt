package com.meartraep.alician.mobile.ui

import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.AutoAwesome
import androidx.compose.material.icons.outlined.RestartAlt
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.data.ColorPalette
import com.meartraep.alician.mobile.data.ContrastLevel
import com.meartraep.alician.mobile.data.ShapeStyle
import com.meartraep.alician.mobile.data.ThemeMode
import com.meartraep.alician.mobile.data.TypographySize
import com.meartraep.alician.mobile.data.UiSettings

@Composable
fun UiSettingsScreen(
    settings: UiSettings,
    padding: PaddingValues,
    onBack: () -> Unit,
    onSettingsChanged: (UiSettings) -> Unit,
    onReset: () -> Unit,
) {
    BackHandler(onBack = onBack)
    val dynamicColorSupported = Build.VERSION.SDK_INT >= Build.VERSION_CODES.S

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(
            start = 16.dp,
            end = 16.dp,
            top = padding.calculateTopPadding() + 8.dp,
            bottom = padding.calculateBottomPadding() + 28.dp,
        ),
        verticalArrangement = Arrangement.spacedBy(14.dp),
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
                Column {
                    Text("UI 设置", style = MaterialTheme.typography.headlineMedium)
                    Text(
                        "Material 3 色彩、字型、形状与无障碍对比度",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }

        item { MaterialPreviewCard() }

        item { SectionHeader("主题模式", "可覆盖系统的浅色/深色外观") }
        item {
            SegmentedSetting(
                value = settings.themeMode,
                options = listOf(
                    ThemeMode.SYSTEM to "跟随系统",
                    ThemeMode.LIGHT to "浅色",
                    ThemeMode.DARK to "深色",
                ),
                onSelected = {
                    onSettingsChanged(settings.copy(themeMode = it))
                },
            )
        }

        item { SectionHeader("Material You", "颜色变化会即时应用到全部页面") }
        item {
            UiSettingCard {
                SettingSwitchRow(
                    title = "系统动态配色",
                    detail = if (dynamicColorSupported) {
                        "从壁纸提取 Material You 色彩；关闭后使用下方内置主题。"
                    } else {
                        "需要 Android 12 或更高版本；当前设备将使用内置主题。"
                    },
                    checked = settings.dynamicColors && dynamicColorSupported,
                    onCheckedChange = {
                        onSettingsChanged(settings.copy(dynamicColors = it))
                    },
                    enabled = dynamicColorSupported,
                )
            }
        }

        item { SectionHeader("内置配色", "动态配色关闭或设备不支持时生效") }
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                ColorPalette.entries.forEach { palette ->
                    FilterChip(
                        selected = settings.colorPalette == palette,
                        onClick = {
                            onSettingsChanged(settings.copy(colorPalette = palette))
                        },
                        leadingIcon = {
                            Box(
                                modifier = Modifier
                                    .size(18.dp)
                                    .clip(CircleShape)
                                    .background(palette.previewColor()),
                            )
                        },
                        label = { Text(palette.label()) },
                    )
                }
            }
        }

        item { SectionHeader("对比度", "增强文本、轮廓和强调色的可辨识度") }
        item {
            SegmentedSetting(
                value = settings.contrastLevel,
                options = listOf(
                    ContrastLevel.STANDARD to "标准",
                    ContrastLevel.MEDIUM to "增强",
                    ContrastLevel.HIGH to "高对比",
                ),
                onSelected = {
                    onSettingsChanged(settings.copy(contrastLevel = it))
                },
            )
        }

        item { SectionHeader("形状体系", "统一控制卡片、按钮、弹窗和输入框圆角") }
        item {
            SegmentedSetting(
                value = settings.shapeStyle,
                options = listOf(
                    ShapeStyle.COMPACT to "紧凑",
                    ShapeStyle.ROUNDED to "圆润",
                    ShapeStyle.EXPRESSIVE to "灵动",
                ),
                onSelected = {
                    onSettingsChanged(settings.copy(shapeStyle = it))
                },
            )
        }

        item { SectionHeader("字体层级", "同步缩放 Material 3 的全部排版角色") }
        item {
            SegmentedSetting(
                value = settings.typographySize,
                options = listOf(
                    TypographySize.COMPACT to "紧凑",
                    TypographySize.STANDARD to "标准",
                    TypographySize.LARGE to "大号",
                ),
                onSelected = {
                    onSettingsChanged(settings.copy(typographySize = it))
                },
            )
        }

        item { SectionHeader("深色表面与专用字体") }
        item {
            UiSettingCard {
                SettingSwitchRow(
                    title = "AMOLED 纯黑表面",
                    detail = "在深色模式下降低发光像素，卡片仍保留 Material 3 色调层级。",
                    checked = settings.amoledBlack,
                    onCheckedChange = {
                        onSettingsChanged(settings.copy(amoledBlack = it))
                    },
                )
                SettingSwitchRow(
                    title = "显示爱丽丝语原字体",
                    detail = "应用于词典词头、写作文本、歌词和翻译内容。",
                    checked = settings.alicianFont,
                    onCheckedChange = {
                        onSettingsChanged(settings.copy(alicianFont = it))
                    },
                )
            }
        }

        item {
            OutlinedButton(
                onClick = onReset,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(Icons.Outlined.RestartAlt, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text("恢复 UI 默认设置")
            }
        }
    }
}

@Composable
private fun MaterialPreviewCard() {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 2.dp),
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    Icons.Outlined.AutoAwesome,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
                Spacer(Modifier.width(10.dp))
                Column {
                    Text("实时主题预览", style = MaterialTheme.typography.titleLarge)
                    Text(
                        "修改设置后，整个应用会立即重组。",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = MaterialTheme.colorScheme.primaryContainer,
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                ),
            ) {
                Column(Modifier.padding(14.dp)) {
                    Text("Material 3 内容卡片", style = MaterialTheme.typography.titleMedium)
                    Text(
                        "色调表面、排版层级和圆角体系会在这里即时呈现。",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
            }
            LinearProgressIndicator(
                progress = { 0.72f },
                modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {}) { Text("主要操作") }
                FilledTonalButton(onClick = {}) { Text("色调按钮") }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun <T> SegmentedSetting(
    value: T,
    options: List<Pair<T, String>>,
    onSelected: (T) -> Unit,
) {
    SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
        options.forEachIndexed { index, option ->
            SegmentedButton(
                selected = value == option.first,
                onClick = { onSelected(option.first) },
                shape = SegmentedButtonDefaults.itemShape(index, options.size),
                modifier = Modifier.weight(1f),
                label = { Text(option.second) },
            )
        }
    }
}

@Composable
private fun UiSettingCard(content: @Composable () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            content()
        }
    }
}

private fun ColorPalette.label(): String = when (this) {
    ColorPalette.ALICIAN -> "爱丽丝紫"
    ColorPalette.OCEAN -> "海洋蓝"
    ColorPalette.FOREST -> "森林绿"
    ColorPalette.ROSE -> "玫瑰红"
}

private fun ColorPalette.previewColor(): Color = when (this) {
    ColorPalette.ALICIAN -> Color(0xFF68548F)
    ColorPalette.OCEAN -> Color(0xFF00639B)
    ColorPalette.FOREST -> Color(0xFF386A20)
    ColorPalette.ROSE -> Color(0xFF9C4146)
}
