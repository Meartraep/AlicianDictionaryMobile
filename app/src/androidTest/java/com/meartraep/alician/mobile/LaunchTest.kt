package com.meartraep.alician.mobile

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test

class LaunchTest {
    @get:Rule
    val composeRule = createAndroidComposeRule<MainActivity>()

    @Test
    fun dictionaryHomeIsVisible() {
        composeRule.onNodeWithText("爱丽丝语词典").assertIsDisplayed()
    }
}

