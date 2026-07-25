package com.meartraep.alician.mobile

import com.meartraep.alician.mobile.data.TextRange
import com.meartraep.alician.mobile.data.WritingSettings
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
}

