package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.GridItemSpan
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.FontDownload
import androidx.compose.material.icons.outlined.Translate
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.data.StudyScript

/**
 * First-run question of the study tab: learn the original Alician glyphs, or only the Latin
 * transcription. The answer decides whether the glyph primer and its quiz are required.
 */
@Composable
internal fun StudyScriptChoice(
    padding: PaddingValues,
    onChoose: (StudyScript) -> Unit,
) {
    val landscape = isLandscapeLayout()
    LazyVerticalGrid(
        columns = GridCells.Fixed(if (landscape) 2 else 1),
        modifier = Modifier
            .fillMaxSize()
            .testTag("study_script_choice"),
        contentPadding = PaddingValues(
            start = 16.dp,
            end = 16.dp,
            top = padding.calculateTopPadding() + 18.dp,
            bottom = padding.calculateBottomPadding() + 24.dp,
        ),
        horizontalArrangement = Arrangement.spacedBy(14.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item(span = { GridItemSpan(maxLineSpan) }) {
            Column(Modifier.fillMaxWidth()) {
                Text("选择学习方式", style = MaterialTheme.typography.headlineMedium)
                Text(
                    "爱丽丝语没有另一套字母表：专用字体只改变 A–Z 的字形，" +
                        "底层仍是普通拉丁字母。",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        item(span = { GridItemSpan(maxLineSpan) }) {
            InfoBanner(
                "先决定要不要认字形。选“只学拉丁转写”会直接进入背词，" +
                    "不会要求你看字符对照或做识字小测；之后随时可以在学习总览里切换。",
            )
        }

        item {
            ScriptOptionCard(
                icon = Icons.Outlined.FontDownload,
                title = "学习爱丽丝语原字体",
                description = "先看 A–Z 字符对照，再通过一次识字小测。" +
                    "之后词卡默认显示爱丽丝语字形，也可以随时查看拉丁转写。",
                hint = "含识字小测",
                buttonText = "学习原字体",
                testTag = "study_script_alician",
                primary = true,
                onClick = { onChoose(StudyScript.ALICIAN) },
            )
        }

        item {
            ScriptOptionCard(
                icon = Icons.Outlined.Translate,
                title = "只学拉丁转写",
                description = "词卡只显示普通拉丁字母，跳过字符对照与识字小测，" +
                    "直接开始背词。遇到别的字形时仍可点开查看。",
                hint = "跳过识字小测",
                buttonText = "只学拉丁转写",
                testTag = "study_script_latin",
                primary = false,
                onClick = { onChoose(StudyScript.LATIN) },
            )
        }

        item(span = { GridItemSpan(maxLineSpan) }) {
            Text(
                "这个选择会记住，可在学习总览的“学习方式”里更改。",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ScriptOptionCard(
    icon: ImageVector,
    title: String,
    description: String,
    hint: String,
    buttonText: String,
    testTag: String,
    primary: Boolean,
    onClick: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = if (primary) {
                MaterialTheme.colorScheme.primaryContainer
            } else {
                MaterialTheme.colorScheme.surfaceContainerLow
            },
        ),
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    icon,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                )
                Spacer(Modifier.width(10.dp))
                Text(title, style = MaterialTheme.typography.titleLarge)
            }
            Text(
                description,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                hint,
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.secondary,
            )
            Button(
                onClick = onClick,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(testTag),
            ) {
                Text(buttonText)
            }
        }
    }
}
