package com.meartraep.alician.mobile

import com.meartraep.alician.mobile.data.StudyItem
import com.meartraep.alician.mobile.data.StudyOrder
import com.meartraep.alician.mobile.data.StudyScope
import com.meartraep.alician.mobile.data.mergeStudyItems
import com.meartraep.alician.mobile.data.orderStudyItems
import com.meartraep.alician.mobile.data.stableItemId
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class StudyDeckLogicTest {
    @Test
    fun stableKeysNormalizeUnicodeAndCaseButPreserveScope() {
        assertEquals(
            stableItemId(StudyScope.WORD, "é"),
            stableItemId(StudyScope.WORD, "e\u0301"),
        )
        assertEquals(
            stableItemId(StudyScope.WORD, "La"),
            stableItemId(StudyScope.WORD, "la"),
        )
        assertNotEquals(
            stableItemId(StudyScope.WORD, "Poul ail"),
            stableItemId(StudyScope.PHRASE, "Poul ail"),
        )
    }

    @Test
    fun duplicateHeadwordsMergeMeaningsWithoutLosingStatistics() {
        val id = stableItemId(StudyScope.WORD, "Harmiy")
        val merged = mergeStudyItems(
            listOf(
                item(id, "Harmiy", "认为", "v.", frequency = 2, variety = 1),
                item(id, "Harmiy", "感情", "n.", frequency = 5, variety = 3),
            ),
        ).single()

        assertEquals("认为；感情", merged.explanation)
        assertEquals("v. / n.", merged.wordClass)
        assertEquals(5, merged.frequency)
        assertEquals(3, merged.variety)
    }

    @Test
    fun commonFirstUsesBreadthBeforeRawFrequency() {
        val broad = item("broad", "Broad", "", frequency = 5, variety = 8)
        val repeated = item("repeat", "Repeat", "", frequency = 100, variety = 2)

        assertEquals(
            listOf(broad, repeated),
            orderStudyItems(listOf(repeated, broad), StudyOrder.FREQUENCY, 1L),
        )
    }

    @Test
    fun randomOrderIsStableForTheSameDailySeed() {
        val items = (1..12).map { item("$it", "Word$it", "") }

        assertEquals(
            orderStudyItems(items, StudyOrder.RANDOM, 20260801L),
            orderStudyItems(items, StudyOrder.RANDOM, 20260801L),
        )
        assertNotEquals(
            orderStudyItems(items, StudyOrder.RANDOM, 20260801L),
            orderStudyItems(items, StudyOrder.RANDOM, 20260802L),
        )
    }

    private fun item(
        id: String,
        text: String,
        explanation: String,
        wordClass: String = "",
        frequency: Int = 0,
        variety: Int = 0,
    ) = StudyItem(
        id = id,
        scope = StudyScope.WORD,
        text = text,
        explanation = explanation,
        wordClass = wordClass,
        frequency = frequency,
        variety = variety,
    )
}
