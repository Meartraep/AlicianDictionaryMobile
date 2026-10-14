package com.meartraep.alician.mobile

import com.meartraep.alician.mobile.data.StudyEntry
import com.meartraep.alician.mobile.data.StudyScript
import com.meartraep.alician.mobile.data.StudySettings
import com.meartraep.alician.mobile.data.leadsWithAlicianGlyphs
import com.meartraep.alician.mobile.data.studyEntryFor
import com.meartraep.alician.mobile.ui.buildAlphabetQuiz
import com.meartraep.alician.mobile.ui.formatInterval
import com.meartraep.alician.mobile.ui.millisecondsUntilNextLocalDay
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar

class StudyUiLogicTest {
    @Test
    fun studyTabAsksForTheScriptBeforeAnythingElse() {
        assertEquals(StudyEntry.SCRIPT_CHOICE, studyEntryFor(StudySettings()))
    }

    @Test
    fun originalScriptRequiresTheRecognitionQuiz() {
        assertEquals(
            StudyEntry.ALPHABET_PRIMER,
            studyEntryFor(StudySettings(script = StudyScript.ALICIAN)),
        )
        assertEquals(
            StudyEntry.OVERVIEW,
            studyEntryFor(
                StudySettings(script = StudyScript.ALICIAN, alphabetCompleted = true),
            ),
        )
    }

    @Test
    fun latinTranscriptionSkipsTheGlyphPrimerAndQuiz() {
        val latinOnly = StudySettings(script = StudyScript.LATIN)

        assertEquals(StudyEntry.OVERVIEW, studyEntryFor(latinOnly))
        assertEquals(
            StudyEntry.OVERVIEW,
            studyEntryFor(latinOnly.copy(alphabetCompleted = false)),
        )
        assertFalse(latinOnly.leadsWithAlicianGlyphs)
        assertTrue(StudySettings(script = StudyScript.ALICIAN).leadsWithAlicianGlyphs)
    }

    @Test
    fun alphabetQuizTestsBothCasesWithValidChoices() {
        val quiz = buildAlphabetQuiz(20260801L)

        assertEquals(10, quiz.size)
        assertEquals(10, quiz.map { it.letter }.distinct().size)
        assertTrue(quiz.any { it.glyph.isUpperCase() })
        assertTrue(quiz.any { it.glyph.isLowerCase() })
        quiz.forEach { question ->
            assertEquals(4, question.options.distinct().size)
            assertTrue(question.letter in question.options)
            assertEquals(question.letter, question.glyph.uppercaseChar())
        }
    }

    @Test
    fun intervalLabelsStayCompactAcrossLearningAndReviewRanges() {
        assertEquals("1分钟", formatInterval(60_000L))
        assertEquals("10分钟", formatInterval(10 * 60_000L))
        assertEquals("2小时", formatInterval(2 * 60 * 60_000L))
        assertEquals("4天", formatInterval(4 * 24 * 60 * 60_000L))
    }

    @Test
    fun dailyRefreshTargetsTheNextLocalMidnight() {
        val now = Calendar.getInstance().apply {
            set(2026, Calendar.AUGUST, 1, 23, 59, 30)
            set(Calendar.MILLISECOND, 0)
        }.timeInMillis

        assertEquals(30_000L, millisecondsUntilNextLocalDay(now))
    }
}
