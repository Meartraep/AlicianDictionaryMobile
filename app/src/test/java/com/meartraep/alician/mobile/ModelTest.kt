package com.meartraep.alician.mobile

import com.meartraep.alician.mobile.data.TextRange
import com.meartraep.alician.mobile.data.TranslationToken
import com.meartraep.alician.mobile.data.WritingSettings
import com.meartraep.alician.mobile.ui.formatCustomizedTranslation
import org.junit.Assert.assertEquals
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
    fun textRangesKeepCharacterOffsets() {
        assertEquals(TextRange(4, 15), TextRange(start = 4, end = 15))
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
