package com.meartraep.alician.mobile

import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.isEnabled
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToNode
import androidx.compose.ui.test.performSemanticsAction
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class StudyScreenTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun originalScriptAsksForTheScriptThenRunsTheRecognitionQuiz() {
        openStudyTab()

        // Fresh install: the script question gates the study tab.
        if (tagVisible("study_script_choice")) {
            composeRule.onNodeWithTag("study_script_alician")
                .performSemanticsAction(SemanticsActions.OnClick)
            composeRule.waitForIdle()
        }

        // A previous run may have stored the Latin-only mode; switch back to the original glyphs.
        if (tagVisible("study_overview_list")) {
            composeRule.onNodeWithTag("study_overview_list")
                .performScrollToNode(hasTestTag("study_script_option_ALICIAN"))
            composeRule.onNodeWithTag("study_script_option_ALICIAN")
                .performSemanticsAction(SemanticsActions.OnClick)
            composeRule.waitForIdle()
        }

        // The primer only gates the flow until it was passed once.
        if (!textVisible("先认识爱丽丝语字符") && !textVisible("爱丽丝语字符对照")) {
            composeRule.onNodeWithTag("study_overview_list")
                .performScrollToNode(hasTestTag("study_open_alphabet"))
            composeRule.onNodeWithTag("study_open_alphabet")
                .performSemanticsAction(SemanticsActions.OnClick)
            composeRule.waitForIdle()
        }

        assertTrue(
            textVisible("先认识爱丽丝语字符") || textVisible("爱丽丝语字符对照"),
        )
        composeRule.onNodeWithTag("alphabet_lesson_list")
            .performScrollToNode(hasTestTag("alphabet_start_quiz"))
        composeRule.onNodeWithTag("alphabet_start_quiz")
            .performSemanticsAction(SemanticsActions.OnClick)
        composeRule.waitUntil(timeoutMillis = 5_000) {
            composeRule.onAllNodesWithText("字符识读")
                .fetchSemanticsNodes().isNotEmpty()
        }
        repeat(10) { index ->
            val letter = ('A'..'Z').first { candidate ->
                composeRule.onAllNodes(
                    hasTestTag("alphabet_question_$candidate"),
                ).fetchSemanticsNodes().isNotEmpty()
            }
            composeRule.onNodeWithTag("alphabet_option_$letter")
                .performSemanticsAction(SemanticsActions.OnClick)
            composeRule.onNodeWithTag("alphabet_next")
                .performSemanticsAction(SemanticsActions.OnClick)
            if (index < 9) composeRule.waitForIdle()
        }

        composeRule.onNodeWithTag("alphabet_complete")
            .performSemanticsAction(SemanticsActions.OnClick)
        composeRule.onNodeWithText("爱丽丝语背诵").assertIsDisplayed()
        composeRule.waitUntil(timeoutMillis = 10_000) {
            composeRule.onAllNodes(
                hasTestTag("study_start_session") and isEnabled(),
            ).fetchSemanticsNodes().isNotEmpty()
        }
        resetStudyProgress()
        composeRule.waitUntil(timeoutMillis = 10_000) {
            composeRule.onAllNodes(
                hasTestTag("study_start_session") and isEnabled(),
            ).fetchSemanticsNodes().isNotEmpty()
        }
        composeRule.onNodeWithTag("study_start_session")
            .performSemanticsAction(SemanticsActions.OnClick)
        composeRule.waitUntil(timeoutMillis = 10_000) {
            composeRule.onAllNodesWithText("主动回忆")
                .fetchSemanticsNodes().isNotEmpty()
        }
        composeRule.onNodeWithTag("study_reveal_answer")
            .performSemanticsAction(SemanticsActions.OnClick)
        composeRule.onNodeWithTag("study_rating_GOOD")
            .performSemanticsAction(SemanticsActions.OnClick)
        composeRule.waitUntil(timeoutMillis = 10_000) {
            composeRule.onAllNodes(
                hasTestTag("study_reveal_answer") and isEnabled(),
            ).fetchSemanticsNodes().isNotEmpty()
        }
        composeRule.onNodeWithTag("study_reveal_answer").assertIsDisplayed()
    }

    @Test
    fun latinTranscriptionStartsStudyingWithoutTheGlyphQuiz() {
        openStudyTab()

        if (tagVisible("study_script_choice")) {
            composeRule.onNodeWithTag("study_script_latin")
                .performSemanticsAction(SemanticsActions.OnClick)
            composeRule.waitForIdle()
        } else {
            composeRule.onNodeWithTag("study_overview_list")
                .performScrollToNode(hasTestTag("study_script_option_LATIN"))
            composeRule.onNodeWithTag("study_script_option_LATIN")
                .performSemanticsAction(SemanticsActions.OnClick)
            composeRule.waitForIdle()
        }

        // Choosing the Latin transcription skips the primer and its quiz entirely.
        composeRule.onNodeWithText("爱丽丝语背诵").assertIsDisplayed()
        assertTrue(
            composeRule.onAllNodesWithText("先认识爱丽丝语字符")
                .fetchSemanticsNodes().isEmpty(),
        )
        assertTrue(
            composeRule.onAllNodesWithText("识字小测", substring = true)
                .fetchSemanticsNodes().isEmpty(),
        )
        assertTrue(
            composeRule.onAllNodes(hasTestTag("alphabet_start_quiz"))
                .fetchSemanticsNodes().isEmpty(),
        )

        resetStudyProgress()
        composeRule.waitUntil(timeoutMillis = 10_000) {
            composeRule.onAllNodes(
                hasTestTag("study_start_session") and isEnabled(),
            ).fetchSemanticsNodes().isNotEmpty()
        }
        composeRule.onNodeWithTag("study_start_session")
            .performSemanticsAction(SemanticsActions.OnClick)
        composeRule.waitUntil(timeoutMillis = 10_000) {
            composeRule.onAllNodesWithText("主动回忆")
                .fetchSemanticsNodes().isNotEmpty()
        }

        // Cards lead with the Latin transcription and only offer the glyphs on demand.
        composeRule.onNodeWithTag("study_card_text").assertIsDisplayed()
        composeRule.onNodeWithText("查看爱丽丝语字形").assertIsDisplayed()
        assertTrue(
            composeRule.onAllNodesWithText("查看拉丁转写")
                .fetchSemanticsNodes().isEmpty(),
        )
    }

    private fun openStudyTab() {
        composeRule.onNodeWithText("背诵").performClick()
        composeRule.waitForIdle()
    }

    private fun resetStudyProgress() {
        composeRule.onNodeWithTag("study_overview_list")
            .performScrollToNode(hasText("清空学习进度"))
        composeRule.onNodeWithText("清空学习进度")
            .performSemanticsAction(SemanticsActions.OnClick)
        composeRule.onNodeWithText("确认清空")
            .performSemanticsAction(SemanticsActions.OnClick)
        composeRule.waitForIdle()
    }

    private fun tagVisible(tag: String): Boolean =
        composeRule.onAllNodes(hasTestTag(tag)).fetchSemanticsNodes().isNotEmpty()

    private fun textVisible(text: String): Boolean =
        composeRule.onAllNodesWithText(text).fetchSemanticsNodes().isNotEmpty()
}
