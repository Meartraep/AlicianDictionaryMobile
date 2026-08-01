package com.meartraep.alician.mobile

import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasTestTag
import androidx.compose.ui.test.isEnabled
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollToIndex
import androidx.compose.ui.test.performScrollTo
import androidx.compose.ui.test.performSemanticsAction
import org.junit.Rule
import org.junit.Test

class StudyScreenTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun studyTabOpensAlphabetPrimerAndQuiz() {
        composeRule.onNodeWithText("背诵").performClick()
        composeRule.waitForIdle()

        if (composeRule.onAllNodesWithText("先认识爱丽丝语字符")
                .fetchSemanticsNodes().isEmpty()
        ) {
            composeRule.onNodeWithText("重新练习爱丽丝语字符")
                .performScrollTo()
                .performClick()
        }

        composeRule.onNodeWithText("先认识爱丽丝语字符").assertIsDisplayed()
        composeRule.onNodeWithTag("alphabet_start_quiz")
            .performScrollTo()
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
        composeRule.onNodeWithTag("study_overview_list").performScrollToIndex(12)
        composeRule.onNodeWithText("清空学习进度")
            .performSemanticsAction(SemanticsActions.OnClick)
        composeRule.onNodeWithText("确认清空")
            .performSemanticsAction(SemanticsActions.OnClick)
        composeRule.onNodeWithTag("study_overview_list").performScrollToIndex(0)
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
}
