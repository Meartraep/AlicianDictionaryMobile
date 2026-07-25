package com.meartraep.alician.mobile

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.viewModels
import com.meartraep.alician.mobile.ui.AlicianApp
import com.meartraep.alician.mobile.ui.theme.AlicianTheme

class MainActivity : ComponentActivity() {
    private val viewModel: MainViewModel by viewModels()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            AlicianTheme(dynamicColors = viewModel.dynamicColorsEnabled) {
                AlicianApp(viewModel)
            }
        }
    }
}

