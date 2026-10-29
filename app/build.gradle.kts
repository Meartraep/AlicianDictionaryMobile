import java.io.File
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.util.Collections
import java.util.Properties
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream

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

// The release workflow publishes one APK per ABI and passes -PtargetAbi=<abi> to
// keep each download to a single architecture. Local builds keep both ABIs, so
// an emulator (x86_64) and a phone (arm64-v8a) both work without extra flags.
// AGP 9 forbids combining splits.abi with the abiFilters setting which Chaquopy 17
// requires, so per-ABI builds are separate invocations rather than one split build.
val targetAbi: String? = providers.gradleProperty("targetAbi").orNull
if (targetAbi != null) {
    require(targetAbi in setOf("arm64-v8a", "x86_64")) {
        "targetAbi must be one of: arm64-v8a, x86_64 (got: $targetAbi)"
    }
}

val chaquopyPythonVersion = "3.14"
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
        versionCode = 16
        versionName = "1.12.0"

        ndk {
            abiFilters += targetAbi?.let(::listOf) ?: listOf("arm64-v8a", "x86_64")
        }
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables.useSupportLibrary = true
        buildConfigField("String", "DATABASE_ASSET_VERSION", "\"2026-10-14-lyric-sentence-alignments\"")
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
            // Chaquopy runs pip with `isolated=True`, so it ignores PIP_* environment
            // variables and pip config files. Without this option pip writes its wheel
            // cache under %LOCALAPPDATA%\pip, which confined build environments deny,
            // failing with "WinError 5" while building the jieba wheel.
            options("--no-cache-dir")
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

// ---------------------------------------------------------------------------
// Trim jieba down to what the runtime uses
// ---------------------------------------------------------------------------
// jieba 0.42.1 ships optional components which this app never imports:
//   * jieba/lac_small/  Paddle LAC neural model (~12.4 MiB)
//   * jieba/posseg/     part-of-speech tables (~8.5 MiB; only the developer-only
//                       scripts/semantic_aliases generator uses them, and that
//                       directory is not packaged into the APK)
//   * jieba/analyse/    TF-IDF/TextRank data (~5.9 MiB)
// The runtime only calls Tokenizer().cut(..., HMM=True), so jieba/dict.txt,
// jieba/finalseg and the core modules are sufficient (see
// webui_backend/translation_data.py). Chaquopy packs the whole installed
// distribution into requirements-common.imy, which is stored uncompressed in
// the APK: removing the unused directories takes the archive from ~19 MiB to
// ~2.6 MiB without changing segmentation behaviour.
val unusedJiebaModulePrefixes = listOf(
    "jieba/lac_small/",
    "jieba/posseg/",
    "jieba/analyse/",
)

fun trimUnusedJiebaModules(archive: File) {
    if (!archive.isFile) {
        println("jieba trim: $archive does not exist, skipped")
        return
    }

    val removed = mutableListOf<ZipEntry>()
    val trimmed = File(archive.parentFile, "${archive.name}.trimmed")
    ZipFile(archive).use { source ->
        val entries = Collections.list(source.entries())
        entries.filterTo(removed) { entry ->
            unusedJiebaModulePrefixes.any { prefix -> entry.name.startsWith(prefix) }
        }
        if (removed.isEmpty()) {
            return
        }
        ZipOutputStream(trimmed.outputStream().buffered()).use { sink ->
            entries.forEach { entry ->
                if (unusedJiebaModulePrefixes.any { prefix -> entry.name.startsWith(prefix) }) {
                    return@forEach
                }
                val kept = ZipEntry(entry.name)
                if (entry.time >= 0) {
                    kept.time = entry.time
                }
                sink.putNextEntry(kept)
                source.getInputStream(entry).use { it.copyTo(sink) }
                sink.closeEntry()
            }
        }
    }

    val originalSize = archive.length()
    Files.move(trimmed.toPath(), archive.toPath(), StandardCopyOption.REPLACE_EXISTING)

    ZipFile(archive).use { trimmedZip ->
        val names = Collections.list(trimmedZip.entries()).map { it.name }
        check(unusedJiebaModulePrefixes.none { prefix -> names.any { it.startsWith(prefix) } }) {
            "jieba trim left unused modules in ${archive.name}"
        }
        if ("jieba/dict.txt" in names) {
            check("jieba/finalseg/prob_emit.pyc" in names) {
                "jieba trim removed the finalseg HMM model required by cut(HMM = true)"
            }
            check(names.any { it.startsWith("jieba-") && it.endsWith(".dist-info/METADATA") }) {
                "jieba trim removed dist-info; pkg_resources needs it to find dict.txt in the .imy"
            }
        }
    }

    println(
        "jieba trim: removed ${removed.size} entries from ${archive.name} " +
            "(${originalSize / 1024} KiB -> ${archive.length() / 1024} KiB)"
    )
}

fun hasUnusedJiebaModules(archive: File): Boolean {
    if (!archive.isFile) {
        return false
    }
    return ZipFile(archive).use { zip ->
        Collections.list(zip.entries()).any { entry ->
            unusedJiebaModulePrefixes.any { prefix -> entry.name.startsWith(prefix) }
        }
    }
}

// The merged asset tree (rather than Chaquopy's generated requirement archive)
// is what gets packaged, so prune it in place at the end of the merge task.
// This keeps the change inside the task's own outputs, which Gradle supports:
// the recorded output snapshot is already trimmed, so incremental builds stay
// correct. The generated archive is declared as an extra input because
// Chaquopy's generated asset directory is not tracked by the merge task's
// up-to-date check; without it a jieba upgrade could leave a stale archive in
// the APK. The up-to-date rule additionally forces one merge for build
// directories that still contain an untrimmed archive from before this rule.
android.buildTypes.names.forEach { buildType ->
    val capitalized = buildType.replaceFirstChar { it.uppercaseChar() }
    val generatedArchive = layout.buildDirectory.file(
        "python/assets/requirements/$buildType/chaquopy/requirements-common.imy",
    )
    val mergedArchive = layout.buildDirectory.file(
        "intermediates/assets/$buildType/merge${capitalized}Assets/chaquopy/requirements-common.imy",
    )
    tasks.matching { it.name == "merge${capitalized}Assets" }.configureEach {
        dependsOn("generate${capitalized}PythonRequirementsAssets")
        inputs.files(generatedArchive)
        outputs.upToDateWhen {
            val archive = mergedArchive.get().asFile
            archive.isFile && !hasUnusedJiebaModules(archive)
        }
        doLast {
            trimUnusedJiebaModules(mergedArchive.get().asFile)
        }
    }
}
