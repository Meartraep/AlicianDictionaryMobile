package com.meartraep.alician.mobile.ui.theme

import android.app.Activity
import android.content.Context
import android.content.ContextWrapper
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.view.WindowCompat
import com.meartraep.alician.mobile.data.ColorPalette
import com.meartraep.alician.mobile.data.ContrastLevel
import com.meartraep.alician.mobile.data.ShapeStyle
import com.meartraep.alician.mobile.data.ThemeMode
import com.meartraep.alician.mobile.data.UiSettings

private val AlicianLight = lightColorScheme(
    primary = Color(0xFF68548F),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFEADDFF),
    onPrimaryContainer = Color(0xFF211047),
    secondary = Color(0xFF625B71),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE8DEF8),
    onSecondaryContainer = Color(0xFF1D192B),
    tertiary = Color(0xFF7D5260),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFD8E4),
    onTertiaryContainer = Color(0xFF31111D),
    background = Color(0xFFFFF8FF),
    surface = Color(0xFFFFF8FF),
    surfaceVariant = Color(0xFFE7E0EC),
    outline = Color(0xFF79747E),
)

private val AlicianDark = darkColorScheme(
    primary = Color(0xFFD1BCFF),
    onPrimary = Color(0xFF38265E),
    primaryContainer = Color(0xFF504176),
    onPrimaryContainer = Color(0xFFEADDFF),
    secondary = Color(0xFFCCC2DC),
    onSecondary = Color(0xFF332D41),
    secondaryContainer = Color(0xFF4A4458),
    onSecondaryContainer = Color(0xFFE8DEF8),
    tertiary = Color(0xFFEFB8C8),
    onTertiary = Color(0xFF492532),
    tertiaryContainer = Color(0xFF633B48),
    onTertiaryContainer = Color(0xFFFFD8E4),
    background = Color(0xFF141218),
    surface = Color(0xFF141218),
    surfaceVariant = Color(0xFF49454F),
    outline = Color(0xFF938F99),
)

private val OceanLight = lightColorScheme(
    primary = Color(0xFF00639B),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFCDE5FF),
    onPrimaryContainer = Color(0xFF001D32),
    secondary = Color(0xFF51606F),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFD5E4F7),
    onSecondaryContainer = Color(0xFF0D1D2A),
    tertiary = Color(0xFF68587A),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFEEDBFF),
    onTertiaryContainer = Color(0xFF231533),
    background = Color(0xFFF8F9FF),
    surface = Color(0xFFF8F9FF),
    surfaceVariant = Color(0xFFDEE3EB),
    outline = Color(0xFF72777F),
)

private val OceanDark = darkColorScheme(
    primary = Color(0xFF94CCFF),
    onPrimary = Color(0xFF003352),
    primaryContainer = Color(0xFF004A75),
    onPrimaryContainer = Color(0xFFCDE5FF),
    secondary = Color(0xFFB9C8DA),
    onSecondary = Color(0xFF23323F),
    secondaryContainer = Color(0xFF3A4857),
    onSecondaryContainer = Color(0xFFD5E4F7),
    tertiary = Color(0xFFD2BFE6),
    onTertiary = Color(0xFF382A49),
    tertiaryContainer = Color(0xFF4F4161),
    onTertiaryContainer = Color(0xFFEEDBFF),
    background = Color(0xFF101418),
    surface = Color(0xFF101418),
    surfaceVariant = Color(0xFF42474E),
    outline = Color(0xFF8C9199),
)

private val ForestLight = lightColorScheme(
    primary = Color(0xFF386A20),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFB8F398),
    onPrimaryContainer = Color(0xFF082100),
    secondary = Color(0xFF55624C),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFD9E7CB),
    onSecondaryContainer = Color(0xFF131F0D),
    tertiary = Color(0xFF386667),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFBBEBEC),
    onTertiaryContainer = Color(0xFF002021),
    background = Color(0xFFF8FAF0),
    surface = Color(0xFFF8FAF0),
    surfaceVariant = Color(0xFFE0E4D6),
    outline = Color(0xFF74796D),
)

private val ForestDark = darkColorScheme(
    primary = Color(0xFF9DD67F),
    onPrimary = Color(0xFF103800),
    primaryContainer = Color(0xFF205107),
    onPrimaryContainer = Color(0xFFB8F398),
    secondary = Color(0xFFBDCBAF),
    onSecondary = Color(0xFF283420),
    secondaryContainer = Color(0xFF3E4A35),
    onSecondaryContainer = Color(0xFFD9E7CB),
    tertiary = Color(0xFFA0CFD0),
    onTertiary = Color(0xFF003738),
    tertiaryContainer = Color(0xFF1E4E4F),
    onTertiaryContainer = Color(0xFFBBEBEC),
    background = Color(0xFF11140E),
    surface = Color(0xFF11140E),
    surfaceVariant = Color(0xFF44483E),
    outline = Color(0xFF8E9286),
)

private val RoseLight = lightColorScheme(
    primary = Color(0xFF9C4146),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFFFDADB),
    onPrimaryContainer = Color(0xFF40000A),
    secondary = Color(0xFF765658),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFFFDADB),
    onSecondaryContainer = Color(0xFF2C1517),
    tertiary = Color(0xFF755A2F),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFFFDEA6),
    onTertiaryContainer = Color(0xFF281900),
    background = Color(0xFFFFF8F7),
    surface = Color(0xFFFFF8F7),
    surfaceVariant = Color(0xFFF3DDDD),
    outline = Color(0xFF857373),
)

private val RoseDark = darkColorScheme(
    primary = Color(0xFFFFB3B5),
    onPrimary = Color(0xFF5F121B),
    primaryContainer = Color(0xFF7E2A30),
    onPrimaryContainer = Color(0xFFFFDADB),
    secondary = Color(0xFFE6BDBF),
    onSecondary = Color(0xFF44292B),
    secondaryContainer = Color(0xFF5D3F41),
    onSecondaryContainer = Color(0xFFFFDADB),
    tertiary = Color(0xFFE5C18D),
    onTertiary = Color(0xFF422C05),
    tertiaryContainer = Color(0xFF5B421A),
    onTertiaryContainer = Color(0xFFFFDEA6),
    background = Color(0xFF191113),
    surface = Color(0xFF191113),
    surfaceVariant = Color(0xFF524344),
    outline = Color(0xFFA08C8D),
)

@Composable
fun AlicianTheme(
    settings: UiSettings,
    content: @Composable () -> Unit,
) {
    val systemDark = isSystemInDarkTheme()
    val darkTheme = when (settings.themeMode) {
        ThemeMode.SYSTEM -> systemDark
        ThemeMode.LIGHT -> false
        ThemeMode.DARK -> true
    }
    val context = LocalContext.current
    val baseColors = when {
        settings.dynamicColors && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        else -> paletteColors(settings.colorPalette, darkTheme)
    }
    val contrasted = applyContrast(baseColors, settings.contrastLevel, darkTheme)
    val colors = if (darkTheme && settings.amoledBlack) {
        contrasted.copy(
            background = Color.Black,
            surface = Color.Black,
            surfaceDim = Color.Black,
            surfaceContainerLowest = Color.Black,
            surfaceContainerLow = Color(0xFF080808),
            surfaceContainer = Color(0xFF0D0D0D),
            surfaceContainerHigh = Color(0xFF151515),
            surfaceContainerHighest = Color(0xFF1D1D1D),
        )
    } else {
        contrasted
    }

    SideEffect {
        context.findActivity()?.window?.let { window ->
            WindowCompat.getInsetsController(window, window.decorView).apply {
                isAppearanceLightStatusBars = !darkTheme
                isAppearanceLightNavigationBars = !darkTheme
            }
        }
    }

    MaterialTheme(
        colorScheme = colors,
        typography = alicianTypography(settings.typographySize),
        shapes = materialShapes(settings.shapeStyle),
        content = content,
    )
}

private fun paletteColors(palette: ColorPalette, dark: Boolean): ColorScheme =
    when (palette) {
        ColorPalette.ALICIAN -> if (dark) AlicianDark else AlicianLight
        ColorPalette.OCEAN -> if (dark) OceanDark else OceanLight
        ColorPalette.FOREST -> if (dark) ForestDark else ForestLight
        ColorPalette.ROSE -> if (dark) RoseDark else RoseLight
    }

private fun applyContrast(
    colors: ColorScheme,
    contrast: ContrastLevel,
    dark: Boolean,
): ColorScheme {
    if (contrast == ContrastLevel.STANDARD) return colors
    val amount = if (contrast == ContrastLevel.HIGH) 0.28f else 0.13f
    val emphasis = if (dark) Color.White else Color.Black
    return colors.copy(
        primary = lerp(colors.primary, emphasis, amount),
        secondary = lerp(colors.secondary, emphasis, amount),
        tertiary = lerp(colors.tertiary, emphasis, amount),
        onBackground = lerp(colors.onBackground, emphasis, amount),
        onSurface = lerp(colors.onSurface, emphasis, amount),
        onSurfaceVariant = lerp(colors.onSurfaceVariant, emphasis, amount),
        outline = lerp(colors.outline, emphasis, amount),
    )
}

private fun materialShapes(style: ShapeStyle): Shapes =
    when (style) {
        ShapeStyle.COMPACT -> Shapes(
            extraSmall = RoundedCornerShape(3.dp),
            small = RoundedCornerShape(6.dp),
            medium = RoundedCornerShape(10.dp),
            large = RoundedCornerShape(14.dp),
            extraLarge = RoundedCornerShape(18.dp),
        )
        ShapeStyle.ROUNDED -> Shapes(
            extraSmall = RoundedCornerShape(6.dp),
            small = RoundedCornerShape(10.dp),
            medium = RoundedCornerShape(16.dp),
            large = RoundedCornerShape(24.dp),
            extraLarge = RoundedCornerShape(30.dp),
        )
        ShapeStyle.EXPRESSIVE -> Shapes(
            extraSmall = RoundedCornerShape(10.dp),
            small = RoundedCornerShape(16.dp),
            medium = RoundedCornerShape(24.dp),
            large = RoundedCornerShape(34.dp),
            extraLarge = RoundedCornerShape(46.dp),
        )
    }

private tailrec fun Context.findActivity(): Activity? =
    when (this) {
        is Activity -> this
        is ContextWrapper -> baseContext.findActivity()
        else -> null
    }
