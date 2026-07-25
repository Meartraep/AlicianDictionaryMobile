package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.EditNote
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Storage
import androidx.compose.material.icons.outlined.Translate
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import com.meartraep.alician.mobile.MainViewModel

private enum class AppDestination(
    val label: String,
    val icon: ImageVector,
) {
    Dictionary("词典", Icons.Outlined.Search),
    Writing("写作", Icons.Outlined.EditNote),
    Translator("翻译", Icons.Outlined.Translate),
    Database("数据库", Icons.Outlined.Storage),
    Settings("设置", Icons.Outlined.Settings),
}

@Composable
fun AlicianApp(viewModel: MainViewModel) {
    var destination by remember { mutableStateOf(AppDestination.Dictionary) }
    val snackbarState = remember { SnackbarHostState() }
    val stateHolder = rememberSaveableStateHolder()

    Scaffold(
        bottomBar = {
            NavigationBar {
                AppDestination.entries.forEach { item ->
                    NavigationBarItem(
                        selected = destination == item,
                        onClick = { destination = item },
                        icon = { Icon(item.icon, contentDescription = item.label) },
                        label = { Text(item.label) },
                    )
                }
            }
        },
        snackbarHost = {
            AppSnackbar(
                error = viewModel.errorMessage,
                notice = viewModel.noticeMessage,
                onConsumed = viewModel::clearMessages,
                hostState = snackbarState,
            )
        },
    ) { padding ->
        Box(Modifier.fillMaxSize()) {
            stateHolder.SaveableStateProvider(destination.name) {
                when (destination) {
                    AppDestination.Dictionary -> DictionaryScreen(viewModel, padding)
                    AppDestination.Writing -> WritingScreen(viewModel, padding)
                    AppDestination.Translator -> TranslatorScreen(viewModel, padding)
                    AppDestination.Database -> DatabaseScreen(viewModel, padding)
                    AppDestination.Settings -> SettingsScreen(viewModel, padding)
                }
            }
            BusyOverlay(viewModel.busyMessage)
        }
    }
}
