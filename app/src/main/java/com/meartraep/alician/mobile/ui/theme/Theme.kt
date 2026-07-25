package com.meartraep.alician.mobile.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

private val LightColors = lightColorScheme(
    primary = Color(0xFF68548F),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFEADDFF),
    onPrimaryContainer = Color(0xFF211047),
    secondary = Color(0xFF625B71),
    secondaryContainer = Color(0xFFE8DEF8),
    tertiary = Color(0xFF7D5260),
    tertiaryContainer = Color(0xFFFFD8E4),
    background = Color(0xFFFFF8FF),
    surface = Color(0xFFFFF8FF),
    surfaceVariant = Color(0xFFE7E0EC),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFD1BCFF),
    onPrimary = Color(0xFF38265E),
    primaryContainer = Color(0xFF504176),
    onPrimaryContainer = Color(0xFFEADDFF),
    secondary = Color(0xFFCCC2DC),
    secondaryContainer = Color(0xFF4A4458),
    tertiary = Color(0xFFEFB8C8),
    tertiaryContainer = Color(0xFF633B48),
    background = Color(0xFF141218),
    surface = Color(0xFF141218),
    surfaceVariant = Color(0xFF49454F),
)

@Composable
fun AlicianTheme(
    dynamicColors: Boolean,
    content: @Composable () -> Unit,
) {
    val darkTheme = isSystemInDarkTheme()
    val colors = when {
        dynamicColors && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColors
        else -> LightColors
    }
    MaterialTheme(
        colorScheme = colors,
        typography = AlicianTypography,
        content = content,
    )
}

