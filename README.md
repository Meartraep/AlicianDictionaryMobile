# Alician Dictionary Mobile

Android 7.0+ native mobile edition of Alician Dictionary Lite.

## Architecture

- Kotlin and Jetpack Compose Material 3 user interface.
- Chaquopy-hosted Python business layer, reusing the Lite dictionary, writing
  checker and bidirectional translation algorithms.
- Private writable SQLite database initialized from the bundled
  `translated.db`.
- Storage Access Framework import/export: no broad storage permission needed.

## Build

Set `sdk.dir` in `local.properties`, then run:

```powershell
.\gradlew.bat testDebugUnitTest lintDebug assembleDebug
```

For a signed release, create `keystore.properties` using the keys referenced in
`app/build.gradle.kts`, then run `.\gradlew.bat assembleRelease`.

## Attribution and license

Based on `Meartraep/Alician_dictionary`, licensed under CC BY-NC-SA 4.0.
The bundled Alician dictionary data retains its original attribution and
non-commercial restrictions. The Alician typeface and application artwork are
copied from the source project for application compatibility.

