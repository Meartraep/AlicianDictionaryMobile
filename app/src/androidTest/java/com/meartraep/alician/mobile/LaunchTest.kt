package com.meartraep.alician.mobile

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.hasSetTextAction
import androidx.compose.ui.test.hasText
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTextInput
import org.junit.Rule
import org.junit.Test

class LaunchTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun dictionaryHomeIsVisible() {
        composeRule.onNodeWithText("爱丽丝语词典").assertIsDisplayed()
    }

    @Test
    fun writingTextSurvivesModuleSwitches() {
        composeRule.onNodeWithText("写作").performClick()
        composeRule.onNodeWithText("爱丽丝语文本").performTextInput("Xia persistence")

        composeRule.onNodeWithText("翻译").performClick()
        composeRule.onNodeWithText("双向翻译器").assertIsDisplayed()
        composeRule.onNodeWithText("写作").performClick()

        composeRule.onNode(
            hasSetTextAction() and hasText("Xia persistence"),
        ).assertIsDisplayed()
    }
}
