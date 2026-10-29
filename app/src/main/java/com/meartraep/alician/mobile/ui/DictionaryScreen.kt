package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.automirrored.outlined.ArrowForward
import androidx.compose.material.icons.automirrored.outlined.LibraryBooks
import androidx.compose.material.icons.outlined.History
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.Tune
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.meartraep.alician.mobile.MainViewModel
import com.meartraep.alician.mobile.R
import com.meartraep.alician.mobile.data.DataTableGroup
import com.meartraep.alician.mobile.data.DataTableInfo
import com.meartraep.alician.mobile.data.DataTablePage
import com.meartraep.alician.mobile.data.DictionaryEntry
import com.meartraep.alician.mobile.data.DictionarySense
import com.meartraep.alician.mobile.data.ExampleResult
import com.meartraep.alician.mobile.data.LyricExample
import com.meartraep.alician.mobile.data.LyricLineTranslation

private val positionOptions = listOf(
    "any" to "任意位置",
    "start" to "句首",
    "end" to "句尾",
)

@Composable
fun DictionaryScreen(viewModel: MainViewModel, padding: PaddingValues) {
    var query by rememberSaveable { mutableStateOf("") }
    var exact by rememberSaveable { mutableStateOf(false) }
    var position by rememberSaveable { mutableStateOf("any") }

    // 数据工作区：工作区、数据组/表、关键词与分页偏移（P1），以及 P2 的编辑状态。
    var workspace by rememberSaveable { mutableStateOf("search") }
    var dataGroup by rememberSaveable { mutableStateOf("core") }
    var dataTable by rememberSaveable { mutableStateOf("") }
    var dataKeyword by rememberSaveable { mutableStateOf("") }
    var dataExact by rememberSaveable { mutableStateOf(false) }
    var dataOffset by rememberSaveable { mutableIntStateOf(0) }
    val dataPageLimit = 50

    var showCreateWordDialog by rememberSaveable { mutableStateOf(false) }
    var senseAddOpen by rememberSaveable { mutableStateOf(false) }
    var formTable by rememberSaveable { mutableStateOf("") }
    var formKey by rememberSaveable { mutableStateOf(-1L) }
    var formExisting by remember { mutableStateOf<Map<String, String>?>(null) }
    var deleteTable by rememberSaveable { mutableStateOf("") }
    var deleteKey by rememberSaveable { mutableStateOf(-1L) }
    var senseToDelete by remember { mutableStateOf<DictionarySense?>(null) }
    var entrySaveSnapshot by remember { mutableStateOf<DictionaryEntry?>(null) }

    // 每个写入对话框独立实现 DataMutation 协议（成功关闭、失败保留输入并内联报错）。
    val createWordState = remember { DataMutationUiState() }
    val entryState = remember { DataMutationUiState() }
    val senseAddState = remember { DataMutationUiState() }
    val formState = remember { DataMutationUiState() }
    val deleteState = remember { DataMutationUiState() }
    val createWordAction: () -> Unit = {
        createWordState.reset()
        showCreateWordDialog = true
    }

    val focusManager = LocalFocusManager.current
    val alicianFont = if (viewModel.alicianFontEnabled) {
        FontFamily(Font(R.font.alician_regular))
    } else {
        FontFamily.Default
    }
    val landscape = isLandscapeLayout()
    val panePadding = PaddingValues(
        start = 16.dp,
        end = 16.dp,
        top = padding.calculateTopPadding() + if (landscape) 12.dp else 18.dp,
        bottom = padding.calculateBottomPadding() + if (landscape) 16.dp else 24.dp,
    )
    // 竖屏时工作区切换固定在列表上方，列表自身只需要内容间距。
    val portraitListPadding = PaddingValues(
        start = 16.dp,
        end = 16.dp,
        top = 8.dp,
        bottom = padding.calculateBottomPadding() + 24.dp,
    )

    // ---- 数据工作区回调：只在明确的用户动作（进工作区/换组/换表/搜索/翻页）时查库 ----
    val onDataGroupChanged: (DataTableGroup) -> Unit = { group ->
        dataGroup = group.group
        dataOffset = 0
        val table = preferredDataTable(group)
        if (table == null) {
            dataTable = ""
        } else {
            dataTable = table.name
            viewModel.loadDataTablePage(table.name, dataKeyword, dataExact, 0, dataPageLimit)
        }
    }
    val onDataTableChanged: (DataTableInfo) -> Unit = { table ->
        dataTable = table.name
        dataOffset = 0
        viewModel.loadDataTablePage(table.name, dataKeyword, dataExact, 0, dataPageLimit)
    }
    val onDataSearch: () -> Unit = {
        focusManager.clearFocus()
        dataOffset = 0
        if (dataTable.isNotBlank()) {
            viewModel.loadDataTablePage(dataTable, dataKeyword, dataExact, 0, dataPageLimit)
        }
    }
    val onDataPrevious: () -> Unit = {
        val offset = ((viewModel.dataTablePage?.offset ?: dataOffset) - dataPageLimit)
            .coerceAtLeast(0)
        dataOffset = offset
        if (dataTable.isNotBlank()) {
            viewModel.loadDataTablePage(dataTable, dataKeyword, dataExact, offset, dataPageLimit)
        }
    }
    val onDataNext: () -> Unit = {
        val offset = (viewModel.dataTablePage?.offset ?: dataOffset) + dataPageLimit
        dataOffset = offset
        if (dataTable.isNotBlank()) {
            viewModel.loadDataTablePage(dataTable, dataKeyword, dataExact, offset, dataPageLimit)
        }
    }
    val onOpenInDictionary: (String) -> Unit = { value ->
        workspace = "search"
        query = value
        focusManager.clearFocus()
        viewModel.searchDictionary(value, exact = false, position = "any")
    }

    // ---- P2 编辑入口：数据行编辑/删除、表单关闭 ----
    val openWordEditor: (Long) -> Unit = { headwordId ->
        // A fresh editor must not inherit the previous dialog's error text.
        entryState.reset()
        deleteState.reset()
        entrySaveSnapshot = null
        viewModel.openDictionaryEntry(headwordId)
    }
    val openRowEdit: (DataTablePage, Map<String, String>) -> Unit = { page, row ->
        val key = (row["id"] ?: row["rowid"])?.toLongOrNull()
        when {
            page.table == "dictionary_headwords" -> if (key != null) {
                openWordEditor(key)
            }
            key != null -> {
                formState.reset()
                formExisting = row
                formKey = key
                formTable = page.table
                viewModel.loadDataForm(page.table)
            }
        }
    }
    val openRowDelete: (DataTablePage, Map<String, String>) -> Unit = { page, row ->
        val key = (row["id"] ?: row["rowid"])?.toLongOrNull()
        if (key != null) {
            deleteState.reset()
            deleteTable = page.table
            deleteKey = key
            viewModel.requestDataDeletePreview(page.table, key)
        }
    }
    val closeDataForm: () -> Unit = {
        formTable = ""
        formKey = -1L
        formExisting = null
        formState.reset()
        viewModel.clearDataForm()
    }
    val openCreateForm: (String) -> Unit = { table ->
        formState.reset()
        formExisting = null
        formKey = -1L
        formTable = table
        viewModel.loadDataForm(table)
    }

    // DataMutation 协议：成功才关闭对应对话框；失败保留输入并内联显示原因。
    DataMutationEffect(viewModel.dataMutation, createWordState, viewModel::consumeDataMutation) {
        showCreateWordDialog = false
    }
    // 词条保存成功后，VM 还会重新读取该词条（refreshHeadwordId）；若立刻关闭会在
    // 刷新写回后又被重新打开。这里等 dictionaryEditEntry 换成新对象后再关闭。
    LaunchedEffect(entrySaveSnapshot, viewModel.dictionaryEditEntry) {
        val saved = entrySaveSnapshot ?: return@LaunchedEffect
        val current = viewModel.dictionaryEditEntry
        when {
            current == null -> entrySaveSnapshot = null
            current !== saved -> {
                entrySaveSnapshot = null
                viewModel.closeDictionaryEntry()
            }
        }
    }
    DataMutationEffect(
        mutation = viewModel.dataMutation,
        state = entryState,
        onConsume = viewModel::consumeDataMutation,
        onSuccess = {},
        onFailure = { entrySaveSnapshot = null },
    )
    DataMutationEffect(viewModel.dataMutation, senseAddState, viewModel::consumeDataMutation) {
        senseAddOpen = false
    }
    DataMutationEffect(viewModel.dataMutation, formState, viewModel::consumeDataMutation) {
        closeDataForm()
    }
    DataMutationEffect(viewModel.dataMutation, deleteState, viewModel::consumeDataMutation) {
        senseToDelete = null
        deleteTable = ""
        deleteKey = -1L
        viewModel.cancelDataDeletePreview()
    }

    // 进入数据工作区才读取表清单（ViewModel 侧带缓存，重复进入不会重复查库）。
    // ready 作为 key：初始化未完成时 loadDataTables 会直接返回，就绪后需要补一次。
    LaunchedEffect(workspace, viewModel.ready) {
        if (workspace == "data") viewModel.loadDataTables()
    }
    // 表清单就绪后自动选中第一个可编辑表（无则第一个表）并加载第一页；
    // 若清单因换库重建，则按当前条件重载已选表（换库后 page 才会是 null）。
    LaunchedEffect(workspace, viewModel.dataTableGroups) {
        if (workspace != "data") return@LaunchedEffect
        val groups = viewModel.dataTableGroups
        if (groups.isEmpty()) return@LaunchedEffect
        val group = groups.firstOrNull { it.group == dataGroup } ?: groups.firstOrNull()
            ?: return@LaunchedEffect
        val current = group.tables.firstOrNull { it.name == dataTable }
        if (current != null && viewModel.dataTablePage != null) return@LaunchedEffect
        val table = current ?: preferredDataTable(group) ?: return@LaunchedEffect
        dataGroup = group.group
        dataTable = table.name
        if (current == null) dataOffset = 0
        viewModel.loadDataTablePage(
            table = table.name,
            keyword = dataKeyword,
            exact = dataExact,
            offset = if (current == null) 0 else dataOffset,
            limit = dataPageLimit,
        )
    }

    if (landscape) {
        LandscapeTwoPane(
            primary = {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = panePadding,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item {
                        Column(modifier = Modifier.fillMaxWidth()) {
                            DictionaryHeader(
                                onCreateWord = if (workspace == "search") createWordAction else null,
                            )
                            Spacer(Modifier.height(10.dp))
                            WorkspaceSwitcher(
                                workspace = workspace,
                                onWorkspaceChanged = { workspace = it },
                            )
                        }
                    }
                    if (workspace == "search") {
                        dictionarySearchItems(
                            query = query,
                            onQueryChanged = { query = it },
                            exact = exact,
                            onExactChanged = { exact = it },
                            position = position,
                            onPositionChanged = { position = it },
                            viewModel = viewModel,
                            alicianFont = alicianFont,
                            onSearch = {
                                focusManager.clearFocus()
                                viewModel.searchDictionary(it, exact, position)
                            },
                        )
                    } else {
                        dataControlsItems(
                            viewModel = viewModel,
                            dataGroup = dataGroup,
                            dataTable = dataTable,
                            dataKeyword = dataKeyword,
                            dataExact = dataExact,
                            dataPageLimit = dataPageLimit,
                            onGroupChanged = onDataGroupChanged,
                            onTableChanged = onDataTableChanged,
                            onKeywordChanged = { dataKeyword = it },
                            onExactChanged = { dataExact = it },
                            onSearch = onDataSearch,
                            onCreateRow = openCreateForm,
                        )
                    }
                }
            },
            secondary = {
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = panePadding,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    if (workspace == "search") {
                        dictionaryResultItems(
                            viewModel = viewModel,
                            alicianFont = alicianFont,
                            includePageHeader = true,
                            onQueryChanged = { query = it },
                            exact = exact,
                            position = position,
                            onEditEntry = { entry ->
                                openWordEditor(entry.headwordId.toLong())
                            },
                        )
                    } else {
                        dataRowsItems(
                            page = viewModel.dataTablePage,
                            alicianFont = alicianFont,
                            onOpenInDictionary = onOpenInDictionary,
                            onEditRow = openRowEdit,
                            onDeleteRow = openRowDelete,
                            onPrevious = onDataPrevious,
                            onNext = onDataNext,
                        )
                    }
                }
            },
            primaryWeight = 0.44f,
        )
    } else {
        Column(modifier = Modifier.fillMaxSize()) {
            DictionaryHeader(
                modifier = Modifier.padding(
                    start = 16.dp,
                    end = 16.dp,
                    top = padding.calculateTopPadding() + 18.dp,
                ),
                onCreateWord = if (workspace == "search") createWordAction else null,
            )
            WorkspaceSwitcher(
                workspace = workspace,
                onWorkspaceChanged = { workspace = it },
                modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 10.dp),
            )
            Box(modifier = Modifier.weight(1f)) {
                if (workspace == "search") {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = portraitListPadding,
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        dictionarySearchItems(
                            query = query,
                            onQueryChanged = { query = it },
                            exact = exact,
                            onExactChanged = { exact = it },
                            position = position,
                            onPositionChanged = { position = it },
                            viewModel = viewModel,
                            alicianFont = alicianFont,
                            onSearch = {
                                focusManager.clearFocus()
                                viewModel.searchDictionary(it, exact, position)
                            },
                        )
                        dictionaryResultItems(
                            viewModel = viewModel,
                            alicianFont = alicianFont,
                            includePageHeader = false,
                            onQueryChanged = { query = it },
                            exact = exact,
                            position = position,
                            onEditEntry = { entry ->
                                openWordEditor(entry.headwordId.toLong())
                            },
                        )
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = portraitListPadding,
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        dataControlsItems(
                            viewModel = viewModel,
                            dataGroup = dataGroup,
                            dataTable = dataTable,
                            dataKeyword = dataKeyword,
                            dataExact = dataExact,
                            dataPageLimit = dataPageLimit,
                            onGroupChanged = onDataGroupChanged,
                            onTableChanged = onDataTableChanged,
                            onKeywordChanged = { dataKeyword = it },
                            onExactChanged = { dataExact = it },
                            onSearch = onDataSearch,
                            onCreateRow = openCreateForm,
                        )
                        dataRowsItems(
                            page = viewModel.dataTablePage,
                            alicianFont = alicianFont,
                            onOpenInDictionary = onOpenInDictionary,
                            onEditRow = openRowEdit,
                            onDeleteRow = openRowDelete,
                            onPrevious = onDataPrevious,
                            onNext = onDataNext,
                        )
                    }
                }
            }
        }
    }

    viewModel.dictionaryExamples?.let { examples ->
        ExamplesSheet(
            result = examples,
            fullLyric = viewModel.dictionaryExamplesFullLyric,
            alicianFont = alicianFont,
            onDismiss = viewModel::closeExamples,
            onUpdateLyric = viewModel::updateLyric,
        )
    }

    if (showCreateWordDialog) {
        DictionaryCreateWordDialog(
            alicianFont = alicianFont,
            submitting = createWordState.submitting,
            errorMessage = createWordState.errorMessage,
            onSubmit = { word, displayExplanation, displayClass, senses ->
                createWordState.begin()
                viewModel.createDictionaryWord(
                    word = word,
                    displayExplanation = displayExplanation,
                    displayClass = displayClass,
                    senses = senses,
                )
            },
            onDismiss = {
                createWordState.reset()
                showCreateWordDialog = false
            },
        )
    }

    viewModel.dictionaryEditEntry?.let { entry ->
        DictionaryEntryEditDialog(
            entry = entry,
            alicianFont = alicianFont,
            submitting = entryState.submitting,
            errorMessage = entryState.errorMessage ?: deleteState.errorMessage,
            onSave = { word, displayExplanation, senses ->
                entryState.begin()
                deleteState.reset()
                entrySaveSnapshot = entry
                viewModel.saveDictionaryEntry(
                    headwordId = entry.headwordId.toLong(),
                    originalWord = entry.word,
                    word = word,
                    displayExplanation = displayExplanation,
                    senses = senses,
                )
            },
            onAddSense = {
                senseAddState.reset()
                senseAddOpen = true
            },
            onDeleteSense = { sense ->
                if (sense.id > 0) senseToDelete = sense
            },
            onDeleteHeadword = {
                val headwordId = entry.headwordId.toLong()
                if (headwordId > 0L) {
                    deleteState.reset()
                    deleteTable = "dictionary_headwords"
                    deleteKey = headwordId
                    viewModel.requestDataDeletePreview("dictionary_headwords", headwordId)
                }
            },
            onDismiss = { viewModel.closeDictionaryEntry() },
        )
    }

    if (senseAddOpen) {
        val entry = viewModel.dictionaryEditEntry
        SenseAddDialog(
            errorMessage = senseAddState.errorMessage,
            submitting = senseAddState.submitting,
            onSubmit = { explanation, wordClass, english, japanese ->
                val headwordId = entry?.headwordId?.toLong()
                if (headwordId != null && headwordId > 0L) {
                    senseAddState.begin()
                    viewModel.addDictionarySense(
                        headwordId = headwordId,
                        explanation = explanation,
                        wordClass = wordClass,
                        english = english,
                        japanese = japanese,
                    )
                }
            },
            onDismiss = {
                senseAddState.reset()
                senseAddOpen = false
            },
        )
    }

    senseToDelete?.let { sense ->
        val headwordId = viewModel.dictionaryEditEntry?.headwordId?.toLong()
        ConfirmActionDialog(
            title = "删除义项？",
            message = "将永久删除义项「${sense.explanation.ifBlank { "（空释义）" }}」。" +
                "删除前会自动创建恢复点，可在 设置 → 数据库 中回退。",
            confirmText = "删除",
            destructive = true,
            onConfirm = {
                senseToDelete = null
                if (headwordId != null && headwordId > 0L && sense.id > 0) {
                    deleteState.begin()
                    viewModel.deleteDictionarySense(sense.id.toLong(), headwordId)
                }
            },
            onDismiss = { senseToDelete = null },
        )
    }

    if (formTable.isNotBlank()) {
        val form = viewModel.dataForm
        // 旋转后本地行缓存会丢，用 saveable 的 formKey 从当前页数据行恢复编辑目标。
        val editingRow = formExisting ?: if (formKey > 0L) {
            viewModel.dataTablePage?.rows?.firstOrNull { row ->
                (row["id"] ?: row["rowid"])?.toLongOrNull() == formKey
            }
        } else {
            null
        }
        if (form != null && form.table == formTable) {
            DataFormDialog(
                form = form,
                existing = editingRow,
                referenceOptions = viewModel.dataReferenceOptions,
                errorMessage = formState.errorMessage,
                submitting = formState.submitting,
                onRequestReferenceOptions = { column ->
                    viewModel.loadDataReferenceOptions(column)
                },
                onSubmit = { values ->
                    if (editingRow == null) {
                        formState.begin()
                        viewModel.createDataRow(formTable, values)
                    } else {
                        val key = (
                            editingRow[form.keyColumn]
                                ?: editingRow["id"]
                                ?: editingRow["rowid"]
                            )?.toLongOrNull()
                        if (key != null) {
                            formState.begin()
                            viewModel.updateDataRow(formTable, key, values)
                        }
                    }
                },
                onDismiss = { closeDataForm() },
            )
        } else {
            DataFormLoadingDialog(onDismiss = { closeDataForm() })
        }
    }

    if (deleteTable.isNotBlank() && deleteKey > 0L) {
        val table = deleteTable
        val key = deleteKey
        val preview = viewModel.dataDeletePreview
        val tableLabel = preview?.label
            ?: viewModel.dataTableGroups
                .flatMap { it.tables }
                .firstOrNull { it.name == table }
                ?.label
            ?: table
        DataDeleteDialog(
            preview = preview,
            tableLabel = tableLabel,
            submitting = deleteState.submitting,
            errorMessage = deleteState.errorMessage,
            onConfirm = {
                deleteState.begin()
                if (table == "dictionary_headwords") {
                    viewModel.deleteDictionaryHeadword(key, preview?.summary.orEmpty())
                } else {
                    viewModel.deleteDataRow(table, key)
                }
            },
            onDismiss = {
                viewModel.cancelDataDeletePreview()
                deleteTable = ""
                deleteKey = -1L
                deleteState.reset()
            },
        )
    }
}

/** 词典标题（检索/数据工作区共用）；标题只在这里渲染。 */
@Composable
private fun DictionaryHeader(
    modifier: Modifier = Modifier,
    onCreateWord: (() -> Unit)? = null,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            "爱丽丝语词典",
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.headlineMedium,
        )
        if (onCreateWord != null) {
            TextButton(onClick = onCreateWord) { Text("+ 新增词条") }
        }
    }
}

private fun LazyListScope.dictionarySearchItems(
    query: String,
    onQueryChanged: (String) -> Unit,
    exact: Boolean,
    onExactChanged: (Boolean) -> Unit,
    position: String,
    onPositionChanged: (String) -> Unit,
    viewModel: MainViewModel,
    alicianFont: FontFamily,
    onSearch: (String) -> Unit,
) {
        item {
            OutlinedTextField(
                value = query,
                onValueChange = onQueryChanged,
                modifier = Modifier.fillMaxWidth(),
                label = { Text("词条、歌词译文或歌名") },
                placeholder = { Text("例如 Xia、爱、world、Alice Music") },
                leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                trailingIcon = {
                    IconButton(
                        onClick = {
                            onSearch(query)
                        },
                    ) {
                        Icon(Icons.Outlined.Search, contentDescription = "查询")
                    }
                },
                singleLine = true,
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(
                    onSearch = {
                        onSearch(query)
                    },
                ),
            )
        }
        item {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FilterChip(
                    selected = exact,
                    onClick = { onExactChanged(!exact) },
                    label = { Text("精确匹配") },
                    leadingIcon = { Icon(Icons.Outlined.Tune, contentDescription = null) },
                )
                positionOptions.forEach { option ->
                    FilterChip(
                        selected = position == option.first,
                        onClick = { onPositionChanged(option.first) },
                        label = { Text(option.second) },
                    )
                }
            }
        }
        if (viewModel.history.isNotEmpty()) {
            item {
                Row {
                    Icon(Icons.Outlined.History, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text("最近查询", style = MaterialTheme.typography.titleSmall)
                }
            }
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(viewModel.history, key = { it }) { historyItem ->
                        AssistChip(
                            onClick = {
                                onQueryChanged(historyItem)
                                viewModel.searchDictionary(historyItem, exact, position)
                            },
                            label = { Text(historyItem, fontFamily = alicianFont) },
                        )
                    }
                }
            }
        }
}

private fun LazyListScope.dictionaryResultItems(
    viewModel: MainViewModel,
    alicianFont: FontFamily,
    includePageHeader: Boolean,
    onQueryChanged: (String) -> Unit,
    exact: Boolean,
    position: String,
    onEditEntry: (DictionaryEntry) -> Unit,
) {
        if (includePageHeader) {
            item { SectionHeader("查询结果", "筛选区与结果区可独立滚动") }
        }
        val result = viewModel.dictionaryResult
        if (result == null) {
            item {
                EmptyState(
                    icon = Icons.AutoMirrored.Outlined.LibraryBooks,
                    title = if (viewModel.ready) "开始查询" else "正在准备词典",
                    detail = "结果完全在本机数据库中生成，无需联网。",
                )
            }
        } else {
            if (result.message.isNotBlank()) {
                item { InfoBanner(result.message, isError = result.sections.isEmpty()) }
            }
            val suggestions = result.suggestions.filter { it.word.isNotBlank() }
            if (suggestions.isNotEmpty()) {
                item {
                    SectionHeader("你是否想查", "Lite 版基于编辑距离提供拼写纠错")
                }
                item {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        itemsIndexed(
                            suggestions,
                            key = { index, suggestion -> "$index:${suggestion.word}" },
                        ) { _, suggestion ->
                            AssistChip(
                                onClick = {
                                    onQueryChanged(suggestion.word)
                                    viewModel.searchDictionary(suggestion.word, exact, position)
                                },
                                label = { Text(suggestion.word, fontFamily = alicianFont) },
                            )
                        }
                    }
                }
            }
            result.sections.forEach { section ->
                item {
                    SectionHeader(section.title, "${section.entries.size} 条结果")
                }
                items(
                    section.entries,
                    key = { "${section.kind}:${it.word}:${it.explanation}" },
                ) { entry ->
                    DictionaryEntryCard(
                        entry = entry,
                        alicianFont = alicianFont,
                        onClick = {
                            onQueryChanged(entry.word)
                            if (entry.kind == "song") {
                                viewModel.loadSongLyrics(entry.word, entry.album)
                            } else {
                                viewModel.loadExamples(entry.word, position)
                            }
                        },
                        onEdit = onEditEntry,
                    )
                }
            }
            if (result.sections.isEmpty() && suggestions.isEmpty()) {
                item {
                    EmptyState(
                        icon = Icons.Outlined.Search,
                        title = "没有找到结果",
                        detail = "可关闭精确匹配，或检查拼写后再试。",
                    )
                }
            }
        }
}

/** 顶部「检索 | 数据」工作区切换：竖屏固定在列表上方，横屏放在左栏顶部。 */
@Composable
private fun WorkspaceSwitcher(
    workspace: String,
    onWorkspaceChanged: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        FilterChip(
            selected = workspace == "search",
            onClick = { onWorkspaceChanged("search") },
            label = { Text("检索") },
        )
        FilterChip(
            selected = workspace == "data",
            onClick = { onWorkspaceChanged("data") },
            label = { Text("数据") },
        )
    }
}

/** 数据组内默认展示的表：优先可编辑表，没有可编辑表时用第一张表。 */
private fun preferredDataTable(group: DataTableGroup): DataTableInfo? =
    group.tables.firstOrNull { it.editable } ?: group.tables.firstOrNull()

/**
 * 「数据」工作区上栏：数据组/数据表选择、关键词与只读提示。
 * 这里只发出用户动作，真正的查询全部由 DictionaryScreen 传进来的回调触发。
 */
private fun LazyListScope.dataControlsItems(
    viewModel: MainViewModel,
    dataGroup: String,
    dataTable: String,
    dataKeyword: String,
    dataExact: Boolean,
    dataPageLimit: Int,
    onGroupChanged: (DataTableGroup) -> Unit,
    onTableChanged: (DataTableInfo) -> Unit,
    onKeywordChanged: (String) -> Unit,
    onExactChanged: (Boolean) -> Unit,
    onSearch: () -> Unit,
    onCreateRow: (String) -> Unit,
) {
    item { SectionHeader("数据表", "按数据组浏览；系统与遗留表只读") }

    val groups = viewModel.dataTableGroups
    if (groups.isEmpty()) {
        item { InfoBanner("正在读取数据表…") }
        return
    }

    val currentGroup = groups.firstOrNull { it.group == dataGroup } ?: groups.first()
    item {
        SelectField(
            label = "数据组",
            value = currentGroup,
            options = groups,
            display = { it.title },
            onSelected = onGroupChanged,
        )
    }

    val currentTable = currentGroup.tables.firstOrNull { it.name == dataTable }
        ?: preferredDataTable(currentGroup)
    if (currentTable == null) {
        item { InfoBanner("「${currentGroup.title}」暂无可浏览的数据表。") }
    } else {
        item {
            SelectField(
                label = "数据表",
                value = currentTable,
                options = currentGroup.tables,
                display = { "${it.label}（${it.name}）" },
                onSelected = onTableChanged,
            )
        }
    }

    item {
        OutlinedTextField(
            value = dataKeyword,
            onValueChange = onKeywordChanged,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("搜索当前表") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
            keyboardActions = KeyboardActions(onSearch = { onSearch() }),
        )
    }
    item {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            FilterChip(
                selected = dataExact,
                onClick = { onExactChanged(!dataExact) },
                label = { Text("精确") },
            )
            Button(onClick = onSearch) { Text("搜索") }
            val creatableTable = currentTable
            if (creatableTable != null && creatableTable.editable) {
                OutlinedButton(onClick = { onCreateRow(creatableTable.name) }) {
                    Text("+ 新增")
                }
            }
        }
    }

    if (currentTable != null && !currentTable.editable) {
        item {
            InfoBanner("「${currentTable.label}」为只读表：可以浏览，不能在此修改。")
        }
    }

    val page = viewModel.dataTablePage
    val pageLabel = page?.takeIf { it.total > 0 }
        ?.let { "${it.pageIndex + 1}/${it.pageCount}" }
        ?: "0"
    item {
        MetricRow(
            "记录" to (page?.total?.toString() ?: "0"),
            "页码" to pageLabel,
            "每页" to dataPageLimit.toString(),
        )
    }
}

/** 「数据」工作区下栏：只读行卡片 + 上一页/下一页（服务端分页）。 */
private fun LazyListScope.dataRowsItems(
    page: DataTablePage?,
    alicianFont: FontFamily,
    onOpenInDictionary: (String) -> Unit,
    onEditRow: (DataTablePage, Map<String, String>) -> Unit,
    onDeleteRow: (DataTablePage, Map<String, String>) -> Unit,
    onPrevious: () -> Unit,
    onNext: () -> Unit,
) {
    if (page == null) {
        item {
            EmptyState(
                icon = Icons.AutoMirrored.Outlined.LibraryBooks,
                title = "选择数据表",
                detail = "左侧选择数据组与数据表后即可按页浏览。",
            )
        }
        return
    }
    if (page.total == 0) {
        item {
            EmptyState(
                icon = Icons.Outlined.Search,
                title = "没有记录",
                detail = "可清空关键词后重试。",
            )
        }
        return
    }
    itemsIndexed(
        page.rows,
        key = { index, row -> "${page.table}:${row["id"] ?: row["rowid"] ?: index}" },
    ) { index, row ->
        DataRowCard(
            page = page,
            index = index,
            row = row,
            alicianFont = alicianFont,
            onOpenInDictionary = onOpenInDictionary,
            onEdit = if (page.editable) {
                { onEditRow(page, row) }
            } else {
                null
            },
            onDelete = if (page.editable) {
                { onDeleteRow(page, row) }
            } else {
                null
            },
        )
    }
    item {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedButton(onClick = onPrevious, enabled = page.canGoPrevious) {
                Text("上一页")
            }
            Text(
                "第 ${page.pageIndex + 1} / ${page.pageCount} 页",
                style = MaterialTheme.typography.labelLarge,
            )
            OutlinedButton(onClick = onNext, enabled = page.canGoNext) {
                Text("下一页")
            }
        }
    }
}

/** 一行数据的卡片；可编辑表带「编辑/删除」，词典类表带「在词典中查看」。 */
@Composable
private fun DataRowCard(
    page: DataTablePage,
    index: Int,
    row: Map<String, String>,
    alicianFont: FontFamily,
    onOpenInDictionary: (String) -> Unit,
    onEdit: (() -> Unit)?,
    onDelete: (() -> Unit)?,
) {
    val titleField = page.display.firstOrNull()
    val title = titleField?.let { row[it] }.orEmpty()
        .ifBlank { "记录 ${page.offset + index + 1}" }
    val lookupValue = dataDictionaryLookupField(page.table)?.let { row[it] }.orEmpty()
    // 只有爱丽丝语字段用自定义字体；歌名、系统表等仍用默认字体。
    val titleFont = if (titleField != null && alicianDataFields.contains(titleField)) {
        alicianFont
    } else {
        FontFamily.Default
    }
    Card(
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.Top,
            ) {
                Text(
                    title,
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.titleMedium,
                    fontFamily = titleFont,
                )
                row["id"]?.let {
                    Text(
                        " #$it",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            page.display.drop(1).forEach { field ->
                val value = row[field].orEmpty()
                if (value.isNotBlank()) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "${dataFieldLabel(field)}：$value",
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 4,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    "${page.offset + index + 1} / ${page.total}",
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (lookupValue.isNotBlank()) {
                    TextButton(onClick = { onOpenInDictionary(lookupValue) }) {
                        Text("在词典中查看")
                    }
                }
            }
            if (onEdit != null || onDelete != null) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                ) {
                    if (onEdit != null) {
                        TextButton(onClick = onEdit) {
                            Text(if (page.table == "dictionary_headwords") "编辑词条" else "编辑")
                        }
                    }
                    if (onDelete != null) {
                        TextButton(onClick = onDelete) {
                            Text("删除", color = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }
        }
    }
}

/** 数据表里能直接回到词典检索的查询字段。 */
private fun dataDictionaryLookupField(table: String): String? = when (table) {
    "dictionary_headwords", "dictionary" -> "words"
    "phrase" -> "PHRASE"
    "songs" -> "title"
    else -> null
}

/** 爱丽丝语字段，展示时使用自定义字体。 */
private val alicianDataFields = setOf("words", "PHRASE", "alician_sentence")

/** 数据表字段的中文显示名；未登记的字段原样显示。 */
private fun dataFieldLabel(field: String): String = when (field) {
    "id" -> "编号"
    "words" -> "词形"
    "display_explanation" -> "展示释义"
    "display_class" -> "词性"
    "explanation" -> "释义"
    "english_gloss" -> "英文"
    "japanese_gloss" -> "日文"
    "count" -> "词频"
    "variety" -> "泛度"
    "PHRASE" -> "词组"
    "title" -> "歌名"
    "Album" -> "专辑"
    "lyric" -> "歌词"
    "song_title" -> "歌曲"
    "alician_sentence" -> "爱丽丝语句"
    "chinese_translation" -> "中文"
    "sentence" -> "原句"
    "english" -> "英文"
    "japanese" -> "日文"
    "korean" -> "韩文"
    "headword_id" -> "词头编号"
    "sense_order" -> "义项序号"
    "class" -> "词性"
    "sense_id" -> "义项编号"
    "db_version" -> "版本"
    "key" -> "键"
    "value" -> "值"
    else -> field
}

@Composable
private fun DictionaryEntryCard(
    entry: DictionaryEntry,
    alicianFont: FontFamily,
    onClick: () -> Unit,
    onEdit: (DictionaryEntry) -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(modifier = Modifier.fillMaxWidth()) {
                Text(
                    entry.word,
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.titleLarge,
                    // 歌曲标题不是爱丽丝语，用默认字体避免字符错位。
                    fontFamily = if (entry.kind == "song") FontFamily.Default else alicianFont,
                    color = MaterialTheme.colorScheme.primary,
                )
                if (entry.wordClass.isNotBlank()) {
                    Text(
                        entry.wordClass,
                        style = MaterialTheme.typography.labelLarge,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }
            Spacer(Modifier.height(7.dp))
            Text(entry.explanation, style = MaterialTheme.typography.bodyLarge)
            if (entry.englishGloss.isNotBlank()) {
                Spacer(Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.Top) {
                    Text(
                        "英",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        entry.englishGloss,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            if (entry.japaneseGloss.isNotBlank()) {
                Spacer(Modifier.height(4.dp))
                Row(verticalAlignment = Alignment.Top) {
                    Text(
                        "日",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.tertiary,
                    )
                    Spacer(Modifier.width(6.dp))
                    Text(
                        entry.japaneseGloss,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Spacer(Modifier.height(10.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    entry.footerText(),
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                if (entry.kind == "alice" || entry.kind == "chinese") {
                    TextButton(onClick = { onEdit(entry) }) { Text("修改") }
                }
            }
        }
    }
}

private fun DictionaryEntry.footerText(): String = when (kind) {
    "translation" -> if (songTitle.isBlank()) {
        "点按查看歌词上下文"
    } else {
        "歌词英/日译命中 · $songTitle · 点按查看歌词上下文"
    }
    "song" -> "歌曲标题命中 · 点按查看完整歌词"
    else -> "词频 $count · 泛度 $variety　点按查看歌词例句"
}

/**
 * 词条与义项编辑器：保存走 viewModel.saveDictionaryEntry（DataMutation 协议），
 * 新增/删除义项与删除词条都在这里入口；entry 被 VM 刷新后 remember(entry) 重置本地输入。
 */
@Composable
private fun DictionaryEntryEditDialog(
    entry: DictionaryEntry,
    alicianFont: FontFamily,
    submitting: Boolean,
    errorMessage: String?,
    onSave: (word: String, displayExplanation: String, senses: List<DictionarySense>) -> Unit,
    onAddSense: () -> Unit,
    onDeleteSense: (DictionarySense) -> Unit,
    onDeleteHeadword: () -> Unit,
    onDismiss: () -> Unit,
) {
    var word by remember(entry) { mutableStateOf(entry.word) }
    var displayExplanation by remember(entry) { mutableStateOf(entry.explanation) }
    var senses by remember(entry) { mutableStateOf(entry.senses) }
    AlertDialog(
        onDismissRequest = { if (!submitting) onDismiss() },
        modifier = Modifier.imePadding(),
        title = { Text("修改词条") },
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
                    textStyle = MaterialTheme.typography.bodyLarge.copy(fontFamily = alicianFont),
                )
                OutlinedTextField(
                    value = displayExplanation,
                    onValueChange = { displayExplanation = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("展示释义") },
                    minLines = 2,
                    maxLines = 3,
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "义项（${senses.size}）",
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.titleSmall,
                    )
                    TextButton(onClick = onAddSense, enabled = !submitting) {
                        Text("+ 新增义项")
                    }
                }
                if (senses.isEmpty()) {
                    Text(
                        "该词条没有义项数据；保存时只更新原文与展示释义。",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                senses.forEachIndexed { index, sense ->
                    SenseEditorCard(
                        index = index,
                        sense = sense,
                        // A headword must keep at least one sense; the backend
                        // rejects deleting the last one as well.
                        removable = !submitting && senses.size > 1,
                        onChange = { senses = senses.replacingSense(index, it) },
                        onRemove = { onDeleteSense(sense) },
                    )
                }
                TextButton(onClick = onDeleteHeadword, enabled = !submitting) {
                    Text("删除词条", color = MaterialTheme.colorScheme.error)
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(word.trim(), displayExplanation, senses) },
                enabled = !submitting && word.isNotBlank() && displayExplanation.isNotBlank(),
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

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ExamplesSheet(
    result: ExampleResult,
    fullLyric: Boolean,
    alicianFont: FontFamily,
    onDismiss: () -> Unit,
    onUpdateLyric: (String, String, String) -> Unit,
) {
    var contextIndex by rememberSaveable(result.word, fullLyric) {
        mutableIntStateOf(if (fullLyric) 0 else -1)
    }
    var editingIndex by rememberSaveable(result.word) { mutableIntStateOf(-1) }

    // 整首歌词模式只显示全文对话框；其余模式保留例句列表，空结果也显示后端提示。
    if (!fullLyric) {
        ModalBottomSheet(onDismissRequest = onDismiss) {
            LazyColumn(
                modifier = Modifier.fillMaxWidth(),
                contentPadding = PaddingValues(start = 16.dp, end = 16.dp, bottom = 36.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item {
                    Text(
                        "${result.word} 的歌词例句",
                        style = MaterialTheme.typography.headlineSmall,
                        fontFamily = alicianFont,
                    )
                    Text(
                        "歌曲 ${result.songStats.size} 首 · 去重前 ${result.totalBefore} · " +
                            "去重后 ${result.totalAfter} · 去重率 " +
                            "${"%.1f".format(result.deduplicationRate)}%",
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                if (result.message.isNotBlank()) {
                    item { InfoBanner(result.message, isError = result.examples.isEmpty()) }
                }
                if (result.examples.isNotEmpty()) {
                    item { SectionHeader("全部例句", "点按可在整首歌词中自动定位") }
                }
                items(
                    count = result.examples.size,
                    key = { index ->
                        result.examples[index].let { "${it.album}:${it.title}:${it.id}:$index" }
                    },
                ) { index ->
                    val example = result.examples[index]
                    Card(
                        colors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surfaceContainer,
                        ),
                    ) {
                        Column(Modifier.padding(16.dp)) {
                            Text(example.title, style = MaterialTheme.typography.titleMedium)
                            Text(
                                example.album,
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(Modifier.height(10.dp))
                            val paragraphLines = example.paragraph.split('\n')
                            val sentence = paragraphLines.firstOrNull { it.isNotBlank() }.orEmpty()
                            val glossLines = paragraphLines.filter { it.isNotBlank() }.drop(1)
                            Text(
                                highlightedText(
                                    text = sentence,
                                    word = result.word,
                                    background = MaterialTheme.colorScheme.errorContainer,
                                    foreground = MaterialTheme.colorScheme.onErrorContainer,
                                ),
                                fontFamily = alicianFont,
                                style = MaterialTheme.typography.bodyLarge,
                            )
                            if (glossLines.isNotEmpty()) {
                                Spacer(Modifier.height(6.dp))
                                Text(
                                    glossLines.joinToString("\n"),
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            if (
                                example.poeticTranslation.isNotBlank() ||
                                example.japaneseTranslation.isNotBlank() ||
                                example.englishTranslation.isNotBlank() ||
                                example.koreanTranslation.isNotBlank()
                            ) {
                                Spacer(Modifier.height(8.dp))
                                LyricTranslationsBlock(
                                    poetic = example.poeticTranslation,
                                    japanese = example.japaneseTranslation,
                                    english = example.englishTranslation,
                                    korean = example.koreanTranslation,
                                )
                            }
                            Spacer(Modifier.height(8.dp))
                            TextButton(onClick = { contextIndex = index }) {
                                Text("查看整首歌词并定位")
                            }
                        }
                    }
                }
                if (result.examples.isEmpty()) {
                    item {
                        EmptyState(
                            icon = Icons.AutoMirrored.Outlined.LibraryBooks,
                            title = "没有符合条件的歌词",
                            detail = "可切换到“任意位置”后重新查询。",
                        )
                    }
                }
                if (result.songStats.isNotEmpty()) {
                    item { SectionHeader("例句来源分布", "查重前 / 查重后") }
                    items(
                        result.songStats,
                        key = { "${it.album}:${it.title}" },
                    ) { stats ->
                        Row(modifier = Modifier.fillMaxWidth()) {
                            Column(Modifier.weight(1f)) {
                                Text(stats.title, style = MaterialTheme.typography.titleSmall)
                                Text(
                                    stats.album,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            Text(
                                "${stats.before} / ${stats.after}",
                                style = MaterialTheme.typography.labelLarge,
                                color = MaterialTheme.colorScheme.primary,
                            )
                        }
                    }
                }
            }
        }
    }

    if (contextIndex in result.examples.indices) {
        val currentIndex = contextIndex
        LyricContextDialog(
            result = result,
            currentIndex = currentIndex,
            fullLyric = fullLyric,
            alicianFont = alicianFont,
            onIndexChanged = { contextIndex = it },
            onEdit = {
                // 整首歌模式不能把 contextIndex 置 -1，否则对话框会在编辑期间失效。
                if (!fullLyric) contextIndex = -1
                editingIndex = currentIndex
            },
            onDismiss = { if (fullLyric) onDismiss() else contextIndex = -1 },
        )
    }

    if (editingIndex in result.examples.indices) {
        val example = result.examples[editingIndex]
        var lyric by remember(example) { mutableStateOf(example.lyric) }
        AlertDialog(
            onDismissRequest = { editingIndex = -1 },
            modifier = Modifier.imePadding(),
            title = { Text(example.title) },
            text = {
                OutlinedTextField(
                    value = lyric,
                    onValueChange = { lyric = it },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(420.dp),
                    textStyle = MaterialTheme.typography.bodyMedium.copy(fontFamily = alicianFont),
                    label = { Text("完整歌词") },
                )
            },
            confirmButton = {
                Button(
                    onClick = {
                        onUpdateLyric(example.title, example.album, lyric)
                        editingIndex = -1
                    },
                ) { Text("保存") }
            },
            dismissButton = {
                OutlinedButton(onClick = { editingIndex = -1 }) { Text("取消") }
            },
        )
    }
}

@Composable
private fun LyricContextDialog(
    result: ExampleResult,
    currentIndex: Int,
    fullLyric: Boolean,
    alicianFont: FontFamily,
    onIndexChanged: (Int) -> Unit,
    onEdit: () -> Unit,
    onDismiss: () -> Unit,
) {
    val example = result.examples[currentIndex]
    val lyricSentenceCount = remember(example.lyric) {
        buildLyricBlocks(example.lyric).size
    }
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
                Text(
                    "完整歌词 · ${result.word}",
                    style = MaterialTheme.typography.headlineSmall,
                    fontFamily = alicianFont,
                )
                Text(
                    "${example.album} - ${example.title}",
                    style = MaterialTheme.typography.titleMedium,
                )
                if (fullLyric) {
                    Text(
                        "歌词共 $lyricSentenceCount 句",
                        modifier = Modifier.padding(vertical = 8.dp),
                        style = MaterialTheme.typography.labelLarge,
                    )
                } else {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        OutlinedButton(
                            onClick = { onIndexChanged(currentIndex - 1) },
                            enabled = currentIndex > 0,
                        ) {
                            Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = null)
                            Spacer(Modifier.width(5.dp))
                            Text("上一句")
                        }
                        Text(
                            "${currentIndex + 1} / ${result.examples.size}",
                            modifier = Modifier.padding(vertical = 12.dp),
                            style = MaterialTheme.typography.labelLarge,
                        )
                        OutlinedButton(
                            onClick = { onIndexChanged(currentIndex + 1) },
                            enabled = currentIndex < result.examples.lastIndex,
                        ) {
                            Text("下一句")
                            Spacer(Modifier.width(5.dp))
                            Icon(Icons.AutoMirrored.Outlined.ArrowForward, contentDescription = null)
                        }
                    }
                }
                Text(
                    if (fullLyric) {
                        "红色为查询词；整首歌词按歌曲顺序排列，可点按「编辑歌词」修改全文。"
                    } else {
                        "红色为查询词，整块底色为当前例句；切换上一句/下一句可跨歌曲跳转。"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                FocusedLyric(
                    example = example,
                    word = result.word,
                    alicianFont = alicianFont,
                    modifier = Modifier.weight(1f),
                )
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.weight(1f),
                    ) { Text("关闭") }
                    Button(
                        onClick = onEdit,
                        modifier = Modifier.weight(1f),
                    ) { Text("编辑歌词") }
                }
            }
        }
    }
}

@Composable
private fun FocusedLyric(
    example: LyricExample,
    word: String,
    alicianFont: FontFamily,
    modifier: Modifier = Modifier,
) {
    val focusStart = example.start.coerceIn(0, example.lyric.length)
    val focusEnd = example.end.coerceIn(focusStart, example.lyric.length)
    val requester = remember(example.id, example.title, focusStart, focusEnd) {
        BringIntoViewRequester()
    }
    val hitBackground = MaterialTheme.colorScheme.errorContainer
    val hitForeground = MaterialTheme.colorScheme.onErrorContainer
    val translations = remember(example) {
        example.lyricTranslations.associateBy { it.line.trim() }
    }
    val blocks = remember(example) { buildLyricBlocks(example.lyric) }
    val focusedIndex = remember(blocks, focusStart) {
        blocks.indexOfLast { it.start <= focusStart }.coerceAtLeast(0)
    }

    LaunchedEffect(requester) {
        requester.bringIntoView()
    }

    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow,
        ),
    ) {
        SelectionContainer {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                blocks.forEachIndexed { index, block ->
                    val focused = index == focusedIndex
                    val content: @Composable () -> Unit = {
                        LyricBlockContent(
                            block = block,
                            translations = translations,
                            word = word,
                            alicianFont = alicianFont,
                            hitBackground = hitBackground,
                            hitForeground = hitForeground,
                            translationColor = if (focused) {
                                MaterialTheme.colorScheme.onSecondaryContainer
                            } else {
                                MaterialTheme.colorScheme.onSurfaceVariant
                            },
                        )
                    }
                    if (focused) {
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .bringIntoViewRequester(requester)
                                .background(
                                    MaterialTheme.colorScheme.secondaryContainer,
                                    MaterialTheme.shapes.small,
                                )
                                .border(
                                    1.dp,
                                    MaterialTheme.colorScheme.secondary,
                                    MaterialTheme.shapes.small,
                                )
                                .padding(horizontal = 8.dp, vertical = 6.dp),
                        ) {
                            content()
                        }
                    } else {
                        content()
                    }
                }
            }
        }
    }
}

private data class LyricBlock(val start: Int, val lines: List<String>) {
    val sentence: String get() = lines.firstOrNull { it.isNotBlank() } ?: ""
}

private fun isLyricGloss(line: String): Boolean =
    line.contains('：') || line.contains(':')

/**
 * Group the raw lyric into paragraphs: one Alician sentence plus all of its
 * following word-by-word gloss lines.  In the stored lyrics the sentence and
 * its gloss are separated by a blank line, so blank lines must not split a
 * paragraph — only the next sentence line does.
 */
private fun buildLyricBlocks(lyric: String): List<LyricBlock> {
    val blocks = mutableListOf<LyricBlock>()
    var current = mutableListOf<String>()
    var currentStart = 0
    var offset = 0
    for (line in lyric.split('\n')) {
        val trimmed = line.trim()
        if (trimmed.isEmpty()) {
            // separator inside a paragraph; a following sentence line flushes
        } else if (isLyricGloss(trimmed)) {
            if (current.isNotEmpty()) current.add(line)
        } else {
            if (current.isNotEmpty()) {
                blocks += LyricBlock(currentStart, current.toList())
            }
            current = mutableListOf(line)
            currentStart = offset
        }
        offset += line.length + 1
    }
    if (current.isNotEmpty()) blocks += LyricBlock(currentStart, current.toList())
    return blocks
}

@Composable
private fun LyricBlockContent(
    block: LyricBlock,
    translations: Map<String, LyricLineTranslation>,
    word: String,
    alicianFont: FontFamily,
    hitBackground: Color,
    hitForeground: Color,
    translationColor: Color,
) {
    Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
        block.lines.forEachIndexed { lineIndex, line ->
            if (line.isBlank()) return@forEachIndexed
            Text(
                highlightedText(line, word, hitBackground, hitForeground),
                fontFamily = alicianFont,
                style = if (lineIndex == 0) {
                    MaterialTheme.typography.bodyLarge
                } else {
                    MaterialTheme.typography.bodySmall
                },
            )
        }
        translations[block.sentence.trim()]?.let { translation ->
            if (
                translation.poetic.isNotBlank() ||
                translation.japanese.isNotBlank() ||
                translation.english.isNotBlank() ||
                translation.korean.isNotBlank()
            ) {
                Spacer(Modifier.height(2.dp))
                LyricTranslationsBlock(
                    poetic = translation.poetic,
                    japanese = translation.japanese,
                    english = translation.english,
                    korean = translation.korean,
                    textColor = translationColor,
                )
            }
        }
    }
}

@Composable
private fun LyricTranslationsBlock(
    poetic: String,
    japanese: String,
    english: String,
    korean: String,
    modifier: Modifier = Modifier,
    textColor: Color = MaterialTheme.colorScheme.onSurfaceVariant,
) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        if (poetic.isNotBlank()) {
            TranslationRow("中文翻译", poetic, MaterialTheme.colorScheme.primary, textColor)
        }
        if (japanese.isNotBlank()) {
            TranslationRow("官方日译", japanese, null, textColor)
        }
        if (english.isNotBlank()) {
            TranslationRow("官方英译", english, null, textColor)
        }
        if (korean.isNotBlank()) {
            TranslationRow("官方韩译", korean, null, textColor)
        }
    }
}

@Composable
private fun TranslationRow(
    label: String,
    text: String,
    labelColor: Color?,
    textColor: Color,
) {
    Row(verticalAlignment = Alignment.Top) {
        Text(
            label,
            style = MaterialTheme.typography.labelSmall,
            color = labelColor ?: MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.width(6.dp))
        Text(
            text,
            style = MaterialTheme.typography.bodyMedium,
            color = textColor,
        )
    }
}

@Composable
private fun highlightedText(
    text: String,
    word: String,
    background: Color,
    foreground: Color,
): AnnotatedString = buildAnnotatedString {
    append(text)
    wordMatchRanges(text, word).forEach { range ->
        addStyle(
            SpanStyle(background = background, color = foreground),
            range.first,
            range.last + 1,
        )
    }
}

internal fun wordMatchRanges(text: String, word: String): List<IntRange> {
    val target = word.trim()
    if (target.isEmpty()) return emptyList()
    return Regex(
        pattern = "\\b${Regex.escape(target)}\\b",
        option = RegexOption.IGNORE_CASE,
    ).findAll(text).map { it.range }.toList()
}
