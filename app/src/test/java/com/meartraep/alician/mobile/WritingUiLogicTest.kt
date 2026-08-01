package com.meartraep.alician.mobile

import androidx.compose.ui.graphics.Color
import com.meartraep.alician.mobile.data.TextRange
import com.meartraep.alician.mobile.data.WritingResult
import com.meartraep.alician.mobile.ui.buildWritingHighlightedText
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class WritingUiLogicTest {
    @Test
    fun inputHighlightUsesBlueForLowStatAndRedForUnknownWords() {
        val text = "Known Rare Missing"
        val red = Color(0xFFD32F2F)
        val blue = Color(0xFF1565C0)
        val result = WritingResult(
            sourceText = text,
            unknownCount = 1,
            unknownRanges = listOf(TextRange(11, 18)),
            lowStatRanges = listOf(TextRange(6, 10)),
            issues = emptyList(),
            status = "checked",
        )

        val highlighted = buildWritingHighlightedText(text, result, red, blue)

        assertEquals(text, highlighted.text)
        assertTrue(
            highlighted.spanStyles.any {
                it.start == 6 && it.end == 10 && it.item.color == blue
            },
        )
        assertTrue(
            highlighted.spanStyles.any {
                it.start == 11 && it.end == 18 && it.item.color == red
            },
        )
    }

    @Test
    fun invalidBackendRangesAreIgnoredWithoutChangingEditableText() {
        val text = "Alice"
        val result = WritingResult(
            sourceText = text,
            unknownCount = 1,
            unknownRanges = listOf(TextRange(-1, 3), TextRange(2, 99)),
            lowStatRanges = emptyList(),
            issues = emptyList(),
            status = "checked",
        )

        val highlighted = buildWritingHighlightedText(text, result, Color.Red, Color.Blue)

        assertEquals(text, highlighted.text)
        assertTrue(highlighted.spanStyles.isEmpty())
    }
}
