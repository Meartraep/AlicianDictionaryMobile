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

## Semantic alias data

The optional translation enhancement uses reviewed Chinese aliases generated
offline; the Android runtime does not ship or load the text2vec model. With
`text2vec` and `jieba` installed in the development Python environment, rebuild
the bundled dataset from a pinned local model:

```powershell
python scripts\generate_semantic_aliases.py `
  --db app\src\main\assets\translated.db `
  --model-path C:\path\to\text2vec-base-chinese `
  --model-name shibing624/text2vec-base-chinese `
  --model-revision <pinned-revision> `
  --dry-run
```

Remove `--dry-run` only after reviewing the proposed alias-to-sense mappings.
The generator records model, Jieba dictionary, thresholds, and dictionary
fingerprints in `semantic_alias_metadata`.

## Attribution and license

Based on `Meartraep/Alician_dictionary`, licensed under CC BY-NC-SA 4.0.
The bundled Alician dictionary data retains its original attribution and
non-commercial restrictions. The Alician typeface and application artwork are
copied from the source project for application compatibility.
