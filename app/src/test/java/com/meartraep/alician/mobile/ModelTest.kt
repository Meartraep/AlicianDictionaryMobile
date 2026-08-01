package com.meartraep.alician.mobile

import com.meartraep.alician.mobile.data.TextRange
import com.meartraep.alician.mobile.data.ThemeMode
import com.meartraep.alician.mobile.data.TranslationToken
import com.meartraep.alician.mobile.data.UiSettings
import com.meartraep.alician.mobile.data.WritingSettings
import com.meartraep.alician.mobile.data.isVersionNewer
import com.meartraep.alician.mobile.ui.formatCustomizedTranslation
import com.meartraep.alician.mobile.ui.wordMatchRanges
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelTest {
    @Test
    fun writingDefaultsMatchLiteConfiguration() {
        val settings = WritingSettings()
        assertTrue(settings.strictCase)
        assertEquals(100, settings.maxUndoSteps)
        assertEquals(listOf(":", "："), settings.dictionaryFormatSeparators)
    }

    @Test
    fun uiDefaultsUseSystemThemeAndMaterialYou() {
        val settings = UiSettings()
        assertEquals(ThemeMode.SYSTEM, settings.themeMode)
        assertTrue(settings.dynamicColors)
        assertEquals(false, settings.amoledBlack)
    }

    @Test
    fun textRangesKeepCharacterOffsets() {
        assertEquals(TextRange(4, 15), TextRange(start = 4, end = 15))
    }

    @Test
    fun lyricHighlightMatchesWholeWordsCaseInsensitively() {
        assertEquals(
            listOf(0..2, 10..12),
            wordMatchRanges("Xia xiala XIA", "xia"),
        )
    }

    @Test
    fun releaseVersionComparisonHandlesPrefixesAndDebugSuffixes() {
        assertTrue(isVersionNewer("v1.1.0", "1.0.9-debug"))
        assertEquals(false, isVersionNewer("v1.0.0", "1.0.0-debug"))
        assertEquals(false, isVersionNewer("not-a-version", "1.0.0"))
    }

    @Test
    fun onlyLatestTranslationRequestCanPublishResults() {
        val requests = LatestTranslationRequestGate()
        val first = requests.next()
        val second = requests.next()

        assertFalse(requests.isCurrent(first))
        assertTrue(requests.isCurrent(second))

        requests.invalidate()
        assertFalse(requests.isCurrent(second))
    }

    @Test
    fun customizedTranslationIgnoresWhitespaceTokensAndFormatsWords() {
        val word = TranslationToken(
            source = "爱",
            target = "Xia",
            status = "exact",
            method = "dictionary_term",
            confidence = 1.0,
            explanation = "爱",
            wordClass = "n.",
            count = 1,
            variety = 1,
            alternatives = emptyList(),
            note = "",
        )
        val space = word.copy(source = " ", target = " ", status = "space", method = "space")
        val punctuation = word.copy(source = "。", target = "。", status = "punct", method = "punct")

        assertEquals(
            "Xia Xia。",
            formatCustomizedTranslation(
                listOf(word, space, word.copy(source = "你"), punctuation),
                "zh_to_alician",
            ),
        )
    }
}
