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
    fun inputHighlightUsesBlueForUncertainAndRedForUnknownWords() {
        val text = "Known Dubious Missing"
        val red = Color(0xFFD32F2F)
        val blue = Color(0xFF1565C0)
        val result = WritingResult(
            sourceText = text,
            unknownCount = 1,
            unknownRanges = listOf(TextRange(14, 21)),
            uncertainRanges = listOf(TextRange(6, 13)),
            issues = emptyList(),
            status = "checked",
        )

        val highlighted = buildWritingHighlightedText(text, result, red, blue)

        assertEquals(text, highlighted.text)
        assertTrue(
            highlighted.spanStyles.any {
                it.start == 6 && it.end == 13 && it.item.color == blue
            },
        )
        assertTrue(
            highlighted.spanStyles.any {
                it.start == 14 && it.end == 21 && it.item.color == red
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
            uncertainRanges = emptyList(),
            issues = emptyList(),
            status = "checked",
        )

        val highlighted = buildWritingHighlightedText(text, result, Color.Red, Color.Blue)

        assertEquals(text, highlighted.text)
        assertTrue(highlighted.spanStyles.isEmpty())
    }

    @Test
    fun unknownRedRemainsAuthoritativeWhenRangesOverlap() {
        val text = "Mixup"
        val red = Color(0xFFD32F2F)
        val result = WritingResult(
            sourceText = text,
            unknownCount = 1,
            unknownRanges = listOf(TextRange(0, 5)),
            uncertainRanges = listOf(TextRange(0, 5)),
            issues = emptyList(),
            status = "checked",
        )

        val highlighted = buildWritingHighlightedText(text, result, red, Color(0xFF1565C0))

        val lastStyle = highlighted.spanStyles.last()
        assertEquals(0, lastStyle.start)
        assertEquals(5, lastStyle.end)
        assertEquals(red, lastStyle.item.color)
    }
}
