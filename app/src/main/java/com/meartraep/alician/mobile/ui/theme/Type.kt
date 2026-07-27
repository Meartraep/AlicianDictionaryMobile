package com.meartraep.alician.mobile.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import com.meartraep.alician.mobile.data.TypographySize

fun alicianTypography(size: TypographySize): Typography {
    val scale = when (size) {
        TypographySize.COMPACT -> 0.92f
        TypographySize.STANDARD -> 1f
        TypographySize.LARGE -> 1.14f
    }
    val base = Typography()
    return Typography(
        displayLarge = base.displayLarge.scaled(scale),
        displayMedium = base.displayMedium.scaled(scale),
        displaySmall = base.displaySmall.scaled(scale),
        headlineLarge = base.headlineLarge.scaled(scale),
        headlineMedium = base.headlineMedium.scaled(scale),
        headlineSmall = base.headlineSmall.scaled(scale),
        titleLarge = base.titleLarge.scaled(scale),
        titleMedium = base.titleMedium.scaled(scale),
        titleSmall = base.titleSmall.scaled(scale),
        bodyLarge = base.bodyLarge.scaled(scale),
        bodyMedium = base.bodyMedium.scaled(scale),
        bodySmall = base.bodySmall.scaled(scale),
        labelLarge = base.labelLarge.scaled(scale),
        labelMedium = base.labelMedium.scaled(scale),
        labelSmall = base.labelSmall.scaled(scale),
    )
}

private fun TextStyle.scaled(scale: Float): TextStyle =
    if (scale == 1f) this
    else copy(
        fontSize = fontSize * scale,
        lineHeight = lineHeight * scale,
    )
