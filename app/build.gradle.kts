import java.io.File
import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
}

val signingPropertiesFile = rootProject.file("keystore.properties")
val signingProperties = Properties().apply {
    if (signingPropertiesFile.exists()) {
        signingPropertiesFile.inputStream().use(::load)
    }
}
val ciSigningStoreFile = System.getenv("ANDROID_KEYSTORE_PATH")?.let(::File)
val ciSigningStorePassword = System.getenv("ANDROID_KEYSTORE_PASSWORD")
val ciSigningKeyAlias = System.getenv("ANDROID_KEY_ALIAS")
val ciSigningKeyPassword = System.getenv("ANDROID_KEY_PASSWORD")
val hasCiSigningConfig = ciSigningStoreFile?.isFile == true &&
    !ciSigningStorePassword.isNullOrBlank() &&
    !ciSigningKeyAlias.isNullOrBlank() &&
    !ciSigningKeyPassword.isNullOrBlank()
val hasLocalSigningConfig = signingPropertiesFile.isFile

val chaquopyPythonVersion = "3.10"
val githubRunnerPython = System.getenv("RUNNER_TOOL_CACHE")
    ?.let(::File)
    ?.resolve("Python")
    ?.listFiles()
    ?.asSequence()
    ?.filter { it.isDirectory && it.name.startsWith("$chaquopyPythonVersion.") }
    ?.flatMap { versionDirectory ->
        sequenceOf("x64", "arm64").map { architecture ->
            versionDirectory.resolve("$architecture/bin/python")
        }
    }
    ?.firstOrNull { it.isFile }

android {
    namespace = "com.meartraep.alician.mobile"
    compileSdk {
        version = release(36) {
            minorApiLevel = 1
        }
    }

    defaultConfig {
        applicationId = "com.meartraep.alician.mobile"
        minSdk = 24
        targetSdk = 36
        versionCode = 6
        versionName = "1.4.1"

        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables.useSupportLibrary = true
        buildConfigField("String", "DATABASE_ASSET_VERSION", "\"2026-07-29-semantic-aliases-v2\"")
    }

    signingConfigs {
        if (hasCiSigningConfig) {
            create("release") {
                storeFile = ciSigningStoreFile
                storePassword = ciSigningStorePassword
                keyAlias = ciSigningKeyAlias
                keyPassword = ciSigningKeyPassword
            }
        } else if (hasLocalSigningConfig) {
            create("release") {
                storeFile = rootProject.file(signingProperties.getProperty("storeFile"))
                storePassword = signingProperties.getProperty("storePassword")
                keyAlias = signingProperties.getProperty("keyAlias")
                keyPassword = signingProperties.getProperty("keyPassword")
            }
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            versionNameSuffix = "-debug"
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
            if (hasCiSigningConfig || hasLocalSigningConfig) {
                signingConfig = signingConfigs.getByName("release")
            }
        }
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    packaging {
        resources.excludes += setOf(
            "/META-INF/{AL2.0,LGPL2.1}",
            "META-INF/DEPENDENCIES",
        )
    }
}

chaquopy {
    defaultConfig {
        version = chaquopyPythonVersion
        // GitHub-hosted runners keep non-default Python versions outside PATH.
        // Locally, let Chaquopy use its platform-specific Python auto-detection.
        githubRunnerPython?.let { buildPython(it.absolutePath) }
        pip {
            install(
                "https://files.pythonhosted.org/packages/c6/cb/" +
                    "18eeb235f833b726522d7ebed54f2278ce28ba9438e3135ab0278d9792a2/" +
                    "jieba-0.42.1.tar.gz#sha256=" +
                    "055ca12f62674fafed09427f176506079bc135638a14e23e25be909131928db2"
            )
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2026.06.00")
    implementation(composeBom)
    androidTestImplementation(composeBom)

    implementation("androidx.core:core-ktx:1.17.0")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.10.0")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.10.0")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.10.0")
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    debugImplementation("androidx.compose.ui:ui-tooling")
    debugImplementation("androidx.compose.ui:ui-test-manifest")

    testImplementation("junit:junit:4.13.2")
    androidTestImplementation("androidx.test.ext:junit:1.3.0")
    androidTestImplementation("androidx.test.espresso:espresso-core:3.7.0")
    androidTestImplementation("androidx.compose.ui:ui-test-junit4")
}

// Chaquopy registers this generated ProGuard file even when the app has no
// static Python proxies. Ensure the empty input exists before R8 snapshots it.
val ensureChaquopyProguardRules by tasks.registering {
    val rulesFile = layout.buildDirectory.file("python/proguard-rules.pro")
    outputs.file(rulesFile)
    doLast {
        val file = rulesFile.get().asFile
        file.parentFile.mkdirs()
        if (!file.exists()) {
            file.writeText("# No static Python proxy rules are required.\n")
        }
    }
}

tasks.matching { it.name.startsWith("minify") && it.name.endsWith("WithR8") }
    .configureEach {
        dependsOn(ensureChaquopyProguardRules)
    }

tasks.matching {
    it.name.contains("Release") && it.name.lowercase().contains("lint")
}
    .configureEach {
        dependsOn(ensureChaquopyProguardRules)
    }
