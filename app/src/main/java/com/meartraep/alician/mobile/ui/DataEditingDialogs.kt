package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.meartraep.alician.mobile.data.DataDeletePreview
import com.meartraep.alician.mobile.data.DataFieldMeta
import com.meartraep.alician.mobile.data.DataFormMeta
import com.meartraep.alician.mobile.data.DataMutation
import com.meartraep.alician.mobile.data.DataReferenceOption
import com.meartraep.alician.mobile.data.DictionarySense

/**
 * 一次写入对话框的提交状态；宿主配合 [DataMutationEffect] 实现 DataMutation 协议：
 * 成功 → 关闭对话框；失败 → 保留用户输入、内联显示原因，不依赖全局 snackbar。
 */
internal class DataMutationUiState {
    var submitting by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set

    /** Success text of the last write; maintenance dialogs show it inline. */
    var successMessage by mutableStateOf<String?>(null)
        private set

    fun begin() {
        submitting = true
        errorMessage = null
        successMessage = null
    }

    fun reset() {
        submitting = false
        errorMessage = null
        successMessage = null
    }

    /** 应用写入结果；返回 true 表示成功、宿主应关闭对应对话框。 */
    fun apply(mutation: DataMutation): Boolean {
        submitting = false
        if (mutation.ok) {
            errorMessage = null
            successMessage = mutation.message.ifBlank { "已完成。" }
            return true
        }
        successMessage = null
        errorMessage = mutation.message.ifBlank { "保存失败，请重试。" }
        return false
    }
}

/**
 * 只让「正在提交」的那一个对话框消费写入结果，其他（同屏叠加的）对话框忽略。
 */
@Composable
internal fun DataMutationEffect(
    mutation: DataMutation?,
    state: DataMutationUiState,
    onConsume: () -> Unit,
    onFailure: () -> Unit = {},
    onSuccess: () -> Unit,
) {
    LaunchedEffect(mutation, state) {
        val result = mutation ?: return@LaunchedEffect
        if (!state.submitting) return@LaunchedEffect
        onConsume()
        if (state.apply(result)) onSuccess() else onFailure()
    }
}

/** 列表里替换第 index 个义项（新增词条与词条编辑共用）。 */
internal fun List<DictionarySense>.replacingSense(
    index: Int,
    sense: DictionarySense,
): List<DictionarySense> = mapIndexed { itemIndex, item ->
    if (itemIndex == index) sense else item
}

/** 一个义项的编辑卡片：中文释义 / 词性 / 英文 / 日文。 */
@Composable
internal fun SenseEditorCard(
    index: Int,
    sense: DictionarySense,
    removable: Boolean,
    onChange: (DictionarySense) -> Unit,
    onRemove: () -> Unit,
) {
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "#${index + 1}",
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                TextButton(onClick = onRemove, enabled = removable) { Text("删除") }
            }
            OutlinedTextField(
                value = sense.explanation,
                onValueChange = { onChange(sense.copy(explanation = it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("中文释义") },
                minLines = 1,
                isError = sense.explanation.isBlank(),
                supportingText = if (sense.explanation.isBlank()) {
                    { Text("必填") }
                } else {
                    null
                },
            )
            OutlinedTextField(
                value = sense.wordClass,
                onValueChange = { onChange(sense.copy(wordClass = it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("词性") },
                singleLine = true,
            )
            OutlinedTextField(
                value = sense.englishGloss,
                onValueChange = { onChange(sense.copy(englishGloss = it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("英文") },
                singleLine = true,
            )
            OutlinedTextField(
                value = sense.japaneseGloss,
                onValueChange = { onChange(sense.copy(japaneseGloss = it)) },
                modifier = Modifier.fillMaxWidth(),
                label = { Text("日文") },
                singleLine = true,
            )
        }
    }
}

/**
 * 通用表格单行表单（schema 驱动）：字段、必填、长度上限与引用候选都由后端描述。
 */
@Composable
internal fun DataFormDialog(
    form: DataFormMeta,
    existing: Map<String, String>?,
    referenceOptions: Map<String, List<DataReferenceOption>>,
    errorMessage: String?,
    submitting: Boolean,
    onRequestReferenceOptions: (column: String) -> Unit,
    onSubmit: (values: Map<String, String>) -> Unit,
    onDismiss: () -> Unit,
) {
    val editableFields = remember(form) { form.fields.filterNot { it.primaryKey } }
    val primaryKeyField = remember(form) { form.fields.firstOrNull { it.primaryKey } }
    val values = remember(form, existing) {
        mutableStateMapOf<String, String>().apply {
            editableFields.forEach { field ->
                this[field.name] = existing?.get(field.name)
                    ?: if (field.hasDefault) field.defaultValue else ""
            }
        }
    }
    val invalid = editableFields.any { field ->
        val value = values[field.name].orEmpty()
        (field.required && value.isBlank()) ||
            (field.maxLength > 0 && value.length > field.maxLength)
    }
    AlertDialog(
        onDismissRequest = { if (!submitting) onDismiss() },
        modifier = Modifier.imePadding(),
        title = {
            Text(if (existing == null) "新增${form.label}" else "编辑${form.label}")
        },
        text = {
            Column(
                modifier = Modifier
                    .heightIn(max = 420.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (form.note.isNotBlank()) {
                    Text(
                        form.note,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                if (existing != null) {
                    val keyField = primaryKeyField
                    val keyValue = keyField?.let { existing[it.name] }
                    if (keyField != null && keyValue != null) {
                        Text(
                            "编号 $keyValue",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                if (errorMessage != null) {
                    InfoBanner(errorMessage, isError = true)
                }
                editableFields.forEach { field ->
                    val value = values[field.name].orEmpty()
                    val reference = field.reference
                    if (reference != null) {
                        ReferenceFormField(
                            field = field,
                            value = value,
                            options = referenceOptions[field.name].orEmpty(),
                            onChange = { values[field.name] = it },
                            onRequestOptions = { onRequestReferenceOptions(field.name) },
                        )
                    } else {
                        val requiredError = field.required && value.isBlank()
                        val overLimit = field.maxLength > 0 && value.length > field.maxLength
                        val hint = when {
                            requiredError -> "必填"
                            field.maxLength > 0 -> "${value.length}/${field.maxLength}"
                            else -> null
                        }
                        OutlinedTextField(
                            value = value,
                            onValueChange = { values[field.name] = it },
                            modifier = Modifier.fillMaxWidth(),
                            label = { Text(field.label) },
                            singleLine = !field.multiline,
                            minLines = if (field.multiline) 4 else 1,
                            maxLines = if (field.multiline) 8 else 1,
                            isError = requiredError || overLimit,
                            supportingText = if (hint != null) {
                                { Text(hint) }
                            } else {
                                null
                            },
                        )
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSubmit(editableFields.associate { it.name to values[it.name].orEmpty() })
                },
                enabled = !submitting && !invalid,
            ) {
                if (submitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                    )
                    Spacer(Modifier.width(6.dp))
                    Text("保存中…")
                } else {
                    Text("保存")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !submitting) { Text("取消") }
        },
    )
}

/** 引用字段：只读输入框 + 下拉候选（展开时才去读取候选值）。 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ReferenceFormField(
    field: DataFieldMeta,
    value: String,
    options: List<DataReferenceOption>,
    onChange: (String) -> Unit,
    onRequestOptions: () -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val display = options.firstOrNull { it.value == value }?.label ?: value
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
    ) {
        OutlinedTextField(
            value = display,
            onValueChange = {},
            readOnly = true,
            label = { Text(field.label) },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .menuAnchor()
                .fillMaxWidth(),
        )
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            if (options.isEmpty()) {
                DropdownMenuItem(
                    text = { Text("暂无候选值") },
                    onClick = { expanded = false },
                )
            }
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(option.label.ifBlank { option.value }) },
                    onClick = {
                        onChange(option.value)
                        expanded = false
                    },
                )
            }
        }
    }
    LaunchedEffect(expanded) {
        if (expanded) onRequestOptions()
    }
}

/** 删除影响预览：只有预览就绪后才能确认删除。 */
@Composable
internal fun DataDeleteDialog(
    preview: DataDeletePreview?,
    tableLabel: String,
    submitting: Boolean,
    errorMessage: String?,
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = { if (!submitting) onDismiss() },
        modifier = Modifier.imePadding(),
        title = { Text("删除${tableLabel}？") },
        text = {
            Column(
                modifier = Modifier
                    .heightIn(max = 380.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (preview == null) {
                    Text("正在检查删除影响…")
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                } else {
                    Text(
                        preview.summary,
                        style = MaterialTheme.typography.titleSmall,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text("将删除 ${preview.deletedSelf} 条${preview.label}记录")
                    preview.children.forEach { child ->
                        Text("${child.label} ×${child.count}")
                    }
                    Spacer(Modifier.height(2.dp))
                    Text(
                        "合计影响 ${preview.totalRemoved} 条记录",
                        style = MaterialTheme.typography.titleSmall,
                    )
                }
                if (errorMessage != null) {
                    InfoBanner(errorMessage, isError = true)
                }
                InfoBanner("删除前会自动创建恢复点，可在 设置 → 数据库 中回退。")
            }
        },
        confirmButton = {
            Button(
                onClick = onConfirm,
                enabled = !submitting && preview != null,
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error,
                    contentColor = MaterialTheme.colorScheme.onError,
                ),
            ) {
                if (submitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                    )
                    Spacer(Modifier.width(6.dp))
                    Text("删除中…")
                } else {
                    Text("删除")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !submitting) { Text("取消") }
        },
    )
}

/** 新增词条：词头 + 展示信息 + 至少一个义项。 */
@Composable
internal fun DictionaryCreateWordDialog(
    alicianFont: FontFamily,
    submitting: Boolean,
    errorMessage: String?,
    onSubmit: (
        word: String,
        displayExplanation: String,
        displayClass: String,
        senses: List<DictionarySense>,
    ) -> Unit,
    onDismiss: () -> Unit,
) {
    var word by remember { mutableStateOf("") }
    var displayExplanation by remember { mutableStateOf("") }
    var displayClass by remember { mutableStateOf("") }
    var senses by remember {
        mutableStateOf(listOf(DictionarySense(0, "", "", "", "")))
    }
    val valid = word.isNotBlank() &&
        displayExplanation.isNotBlank() &&
        senses.isNotEmpty() &&
        senses.all { it.explanation.isNotBlank() }
    AlertDialog(
        onDismissRequest = { if (!submitting) onDismiss() },
        modifier = Modifier.imePadding(),
        title = { Text("新增词条") },
        text = {
            Column(
                modifier = Modifier
                    .heightIn(max = 460.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (errorMessage != null) {
                    InfoBanner(errorMessage, isError = true)
                }
                OutlinedTextField(
                    value = word,
                    onValueChange = { word = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("原文") },
                    singleLine = true,
                    isError = word.isBlank(),
                    textStyle = MaterialTheme.typography.bodyLarge.copy(fontFamily = alicianFont),
                )
                OutlinedTextField(
                    value = displayExplanation,
                    onValueChange = { displayExplanation = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("展示释义") },
                    minLines = 2,
                    maxLines = 3,
                    isError = displayExplanation.isBlank(),
                )
                OutlinedTextField(
                    value = displayClass,
                    onValueChange = { displayClass = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("词性（可空，例如 n.）") },
                    singleLine = true,
                )
                Text("义项（至少一个）", style = MaterialTheme.typography.titleSmall)
                senses.forEachIndexed { index, sense ->
                    SenseEditorCard(
                        index = index,
                        sense = sense,
                        removable = senses.size > 1 && !submitting,
                        onChange = { senses = senses.replacingSense(index, it) },
                        onRemove = {
                            if (senses.size > 1) {
                                senses = senses.filterIndexed { itemIndex, _ ->
                                    itemIndex != index
                                }
                            }
                        },
                    )
                }
                OutlinedButton(
                    onClick = {
                        senses = senses + DictionarySense(0, "", "", "", "")
                    },
                    enabled = !submitting,
                ) { Text("+ 添加义项") }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSubmit(
                        word.trim(),
                        displayExplanation,
                        displayClass.trim(),
                        senses,
                    )
                },
                enabled = !submitting && valid,
            ) {
                if (submitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                    )
                    Spacer(Modifier.width(6.dp))
                    Text("保存中…")
                } else {
                    Text("保存")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !submitting) { Text("取消") }
        },
    )
}

/** 编辑既有词条时新增单个义项。 */
@Composable
internal fun SenseAddDialog(
    errorMessage: String?,
    submitting: Boolean,
    onSubmit: (
        explanation: String,
        wordClass: String,
        english: String,
        japanese: String,
    ) -> Unit,
    onDismiss: () -> Unit,
) {
    var explanation by remember { mutableStateOf("") }
    var wordClass by remember { mutableStateOf("") }
    var english by remember { mutableStateOf("") }
    var japanese by remember { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = { if (!submitting) onDismiss() },
        modifier = Modifier.imePadding(),
        title = { Text("新增义项") },
        text = {
            Column(
                modifier = Modifier
                    .heightIn(max = 380.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (errorMessage != null) {
                    InfoBanner(errorMessage, isError = true)
                }
                OutlinedTextField(
                    value = explanation,
                    onValueChange = { explanation = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("中文释义") },
                    minLines = 1,
                    isError = explanation.isBlank(),
                    supportingText = if (explanation.isBlank()) {
                        { Text("必填") }
                    } else {
                        null
                    },
                )
                OutlinedTextField(
                    value = wordClass,
                    onValueChange = { wordClass = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("词性") },
                    singleLine = true,
                )
                OutlinedTextField(
                    value = english,
                    onValueChange = { english = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("英文") },
                    singleLine = true,
                )
                OutlinedTextField(
                    value = japanese,
                    onValueChange = { japanese = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("日文") },
                    singleLine = true,
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSubmit(
                        explanation.trim(),
                        wordClass.trim(),
                        english,
                        japanese,
                    )
                },
                enabled = !submitting && explanation.isNotBlank(),
            ) {
                if (submitting) {
                    CircularProgressIndicator(
                        modifier = Modifier.size(16.dp),
                        strokeWidth = 2.dp,
                    )
                    Spacer(Modifier.width(6.dp))
                    Text("保存中…")
                } else {
                    Text("保存")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss, enabled = !submitting) { Text("取消") }
        },
    )
}

/** 表结构读取中的占位对话框（表单打开后结构尚未返回）。 */
@Composable
internal fun DataFormLoadingDialog(onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("正在读取表结构…") },
        text = { LinearProgressIndicator(modifier = Modifier.fillMaxWidth()) },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        },
    )
}
