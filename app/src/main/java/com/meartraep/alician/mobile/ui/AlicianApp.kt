package com.meartraep.alician.mobile.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.EditNote
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material.icons.outlined.School
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material.icons.outlined.Translate
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationRail
import androidx.compose.material3.NavigationRailItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.saveable.rememberSaveable
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
    Study("背诵", Icons.Outlined.School),
    Settings("设置", Icons.Outlined.Settings),
}

@Composable
fun AlicianApp(viewModel: MainViewModel) {
    var destination by rememberSaveable { mutableStateOf(AppDestination.Dictionary) }
    val snackbarState = remember { SnackbarHostState() }
    val stateHolder = rememberSaveableStateHolder()
    val landscape = isLandscapeLayout()

    Scaffold(
        bottomBar = {
            if (!landscape) {
                AppNavigationBar(
                    selected = destination,
                    appUpdateAvailable = viewModel.appUpdateInfo?.updateAvailable == true,
                    onSelected = { destination = it },
                )
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
        Row(Modifier.fillMaxSize()) {
            if (landscape) {
                AppNavigationRail(
                    selected = destination,
                    appUpdateAvailable = viewModel.appUpdateInfo?.updateAvailable == true,
                    onSelected = { destination = it },
                )
            }
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxSize(),
            ) {
                stateHolder.SaveableStateProvider(destination.name) {
                    when (destination) {
                        AppDestination.Dictionary -> DictionaryScreen(viewModel, padding)
                        AppDestination.Writing -> WritingScreen(viewModel, padding)
                        AppDestination.Translator -> TranslatorScreen(viewModel, padding)
                        AppDestination.Study -> StudyScreen(viewModel, padding)
                        AppDestination.Settings -> SettingsScreen(viewModel, padding)
                    }
                }
                BusyOverlay(viewModel.busyMessage)
            }
        }
    }
}

@Composable
private fun AppNavigationBar(
    selected: AppDestination,
    appUpdateAvailable: Boolean,
    onSelected: (AppDestination) -> Unit,
) {
    NavigationBar {
        AppDestination.entries.forEach { item ->
            NavigationBarItem(
                selected = selected == item,
                onClick = { onSelected(item) },
                icon = { DestinationIcon(item, appUpdateAvailable) },
                label = { DestinationLabel(item, appUpdateAvailable) },
            )
        }
    }
}

@Composable
private fun AppNavigationRail(
    selected: AppDestination,
    appUpdateAvailable: Boolean,
    onSelected: (AppDestination) -> Unit,
) {
    NavigationRail {
        AppDestination.entries.forEach { item ->
            NavigationRailItem(
                selected = selected == item,
                onClick = { onSelected(item) },
                icon = { DestinationIcon(item, appUpdateAvailable) },
            )
        }
    }
}

@Composable
private fun DestinationIcon(item: AppDestination, appUpdateAvailable: Boolean) {
    val hasAppUpdate = item == AppDestination.Settings && appUpdateAvailable
    if (hasAppUpdate) {
        BadgedBox(badge = { Badge { Text("新") } }) {
            Icon(
                item.icon,
                contentDescription = item.label,
                tint = MaterialTheme.colorScheme.error,
            )
        }
    } else {
        Icon(item.icon, contentDescription = item.label)
    }
}

@Composable
private fun DestinationLabel(item: AppDestination, appUpdateAvailable: Boolean) {
    Text(
        item.label,
        color = if (item == AppDestination.Settings && appUpdateAvailable) {
            MaterialTheme.colorScheme.error
        } else {
            LocalContentColor.current
        },
    )
}
