# Alician Dictionary Mobile — Changelog (English)

> Chinese release notes are shown on the GitHub Releases page. This document is
> the dedicated English version for readers who prefer English.

## v1.6.1 (2026-08-12)

### Fixes

- **Punctuation tokens are no longer highlighted as errors**: the `status` of a
  punctuation token is `punct`, but the UI only handled `exact` and `approximate`
  states, so punctuation fell into the `else` branch and received a red error
  background. Punctuation now uses a neutral color (`surfaceVariant`) and its
  move up/down buttons are disabled.

### Technical details

- `TranslationTokenCard` gained a `"punct"` branch using the `surfaceVariant`
  color
- Move up/down buttons are automatically disabled when `status = punct`
- Version bumped to 1.6.1 (versionCode 9)

### Release assets

- `AlicianDictionary-v1.6.1.apk`: signed release APK (arm64-v8a + x86_64)
- `AlicianDictionary-v1.6.1.apk.intoto.jsonl`: SLSA build provenance
- `SHA256SUMS.txt`: SHA-256 checksums of the assets

**Full changelog**: https://github.com/Meartraep/AlicianDictionaryMobile/compare/v1.6.0...v1.6.1

## v1.6.0 (2026-08-02)

### Highlights

- Expanded bidirectional grammar parsing based on the dictionary, song lyrics
  and precisely aligned corpora, covering pluralization, adverbialization,
  negation, tense/aspect, future tense, passive voice, possessives and relative
  clauses.
- Improved local clause detection for imperatives, questions, conjunctions and
  polysemous function words, reducing cross-clause misparses.
- Fixed dictionary annotations, unknown placeholders and unbound templates
  leaking into translations.
- Fixed the mobile client's concatenation of custom translations for parsed
  grammar tokens, preserving ellipsis and template semantics.
- Sentence-type statistics are now deduplicated per song, and subject/object
  are no longer swapped based on part-of-speech statistics alone.

### Verification

- 64 Python translator tests passed.
- Android `testDebugUnitTest`, release lint and signed APK build passed.
- 1188 precisely aligned sentences fully scanned with 0 grammar metadata and
  slot leaks.
- APK signature verified; SHA-256 checksums and SLSA provenance attached.

**Full changelog**: https://github.com/Meartraep/AlicianDictionaryMobile/compare/v1.5.0...v1.6.0

## v1.5.0 (2026-08-02)

### Highlights

- Modularized the translator and added no-class grammar handling.

### What's Changed

* Modularize translator and handle no-class grammar by @Meartraep in https://github.com/Meartraep/AlicianDictionaryMobile/pull/6
* build(deps): bump actions/setup-python from 6.3.0 to 7.0.0 by @dependabot[bot] in https://github.com/Meartraep/AlicianDictionaryMobile/pull/5
* build(deps): bump actions/upload-artifact from 4.6.2 to 7.0.1 by @dependabot[bot] in https://github.com/Meartraep/AlicianDictionaryMobile/pull/4
* build(deps): bump actions/checkout from 6.1.0 to 7.0.1 by @dependabot[bot] in https://github.com/Meartraep/AlicianDictionaryMobile/pull/3
* build(deps): bump gradle/actions/wrapper-validation from 4c125117fe7c5aed11272ec4213f602f012f89f2 to 0723195856401067f7a2779048b490ace7a47d7c by @dependabot[bot] in https://github.com/Meartraep/AlicianDictionaryMobile/pull/2
* build(deps): bump gradle/actions/setup-gradle from 4c125117fe7c5aed11272ec4213f602f012f89f2 to 0723195856401067f7a2779048b490ace7a47d7c by @dependabot[bot] in https://github.com/Meartraep/AlicianDictionaryMobile/pull/1

**Full changelog**: https://github.com/Meartraep/AlicianDictionaryMobile/compare/v1.4.1...v1.5.0

## v1.4.1 (2026-08-01)

**Full changelog**: https://github.com/Meartraep/AlicianDictionaryMobile/compare/v1.4.0...v1.4.1

## v1.3.0 (2026-08-01)

### Highlights

- New complete Alician recitation center: starts with recognition drills and
  quizzes for case-variant special glyphs, then moves to active recall of
  words/phrases.
- New cards support high-frequency/breadth-first ordering, alphabetical order
  and daily shuffle, with all, word-only or phrase-only decks.
- Scientific spaced repetition: due review first, 1/10-minute learning steps,
  forgotten re-learning, four-level difficulty rating and gradually expanding
  long-term intervals.
- New daily new-card quota, study progress, study streak, mastered count and
  retention-rate statistics; progress is saved independently and included in
  Android backups.
- Updated semantic alias data and translation matching logic, adding a
  reproducible semantic alias generation script and Jieba runtime support.
- Strengthened concurrency safety for database updates, async translation and
  study queues; improved accessibility, state restoration and auto-refresh.

### Verification

- Signed release APK build with R8/resource shrinking passed.
- Android unit tests and lint passed.
- Full study flow tested on the Android emulator.
- Python semantic translation tests: all 11 passed.

APK version: `1.3.0` (`versionCode 4`), minimum Android 7.0.

## v1.2.0 (2026-07-29)

### Version info

- Semantic version: `v1.2.0`
- Android `versionName`: `1.2.0`
- Android `versionCode`: `3`

### AI-augmented word-sense translation

- Added an optional "AI-augmented word sense" translation mode that uses
  precomputed text2vec synonym senses in the database to improve fuzzy
  matching from Chinese to Alician.
- The translation page can toggle this feature at any time and shows whether
  augmented data is available and its current size.
- Match results are annotated with the augmented sense source while keeping
  candidates, confidence and the original fallback matching logic.
- The bundled database gained augmented senses and metadata; upgrades only
  sync the augmented tables when the core dictionary data matches, preserving
  the user's existing database and edits.
- Compatible with custom databases lacking augmented tables; the feature
  degrades safely.

### Navigation and database management

- Bottom navigation reduced from five items to four: Dictionary, Writing,
  Translation, Settings.
- "Database management" moved to Settings → Dictionary database; the home
  screen no longer shows a separate database entry.
- Database management page gained a top back button and Android system back
  key support.

### Quality and compatibility

- Added tests for the semantic augmentation toggle, matching behavior and
  missing-table compatibility.
- Continues to support `arm64-v8a` and `x86_64`.
- Minimum Android version remains Android 7.0 (API 24).

### Upgrade notes

Directly overwrite-install from `v1.1.0`. Overwrite installation requires the
APK to use the same signing certificate; app data and the user database are
preserved.

### Install notes

Download and install `AlicianDictionaryMobile-v1.2.0.apk` below.

Supported ABIs: `arm64-v8a`, `x86_64`
Minimum Android: Android 7.0 (API 24)
Target Android API: 36

### Integrity

`SHA-256: BA0941CD112020CDBC9B05F8EE8251B1C28C8CF5A08FC7579E97B414C2A71278`

### Verification

- Android release build passed
- Android release lint passed: 0 errors (10 non-blocking warnings)
- 6 Android JVM unit tests passed
- 2 Python semantic augmentation tests passed
- APK version check: `versionName=1.2.0`, `versionCode=3`
- APK Signature Scheme v2 verification passed

**Full changelog**: https://github.com/Meartraep/AlicianDictionaryMobile/compare/v1.1.0...v1.2.0

## v1.1.0 (2026-07-27)

### Material 3 UI

- Upgraded "UI settings" into a standalone settings page with live component
  previews.
- Supports system, light and dark theme modes.
- Supports Material You dynamic color, plus four alternative palettes: Alician,
  Ocean, Forest and Rose.
- Supports three contrast levels, three corner-radius styles, three font sizes
  and AMOLED pure-black mode.
- UI settings apply globally immediately and are saved automatically, with
  one-click reset to defaults.

### Lyrics and dictionary experience

- Highlight and locate the current word in the full lyrics page.
- Jump from a word result to its position in the full lyrics.
- Switch between multiple songs containing the same word.
- Improved lyrics source and navigation display on the dictionary page.
- Moved the example-source distribution to the bottom of the example page,
  prioritizing the example body.

### Database updates

- Show a local-vs-remote version comparison after pulling the remote database.
- View full diffs for added, removed and modified entries.
- Apply remote database updates after user confirmation.

### App updates

- Auto-check GitHub Latest Release on app startup.
- Manual update check on the settings page.
- Prominent color highlighting and a direct link to the Release download page
  when a new version is available.

### Install notes

Download and install `AlicianDictionaryMobile-v1.1.0.apk` below. Overwrite
installation requires the same signing certificate as the old version.

Supported ABIs: `arm64-v8a`, `x86_64`
Minimum Android: Android 7.0 (API 24)

### Integrity

`SHA-256: 3A237E37818AE92FD1E2A52AD41E9FF2C113C8741AE50E79B38A7E9898D0564F`

### Verification

- Android release build passed
- Android release lint: 0 errors
- 6 unit tests passed
- APK Signature Scheme v2 verification passed

**Full changelog**: https://github.com/Meartraep/AlicianDictionaryMobile/compare/v1.0.0...v1.1.0

## v1.0.0 (2026-07-25)

The mobile version of the Alician dictionary lookup tool, built with GPT on the
desktop edition. Feature parity targets the desktop Lite package, currently
slightly behind. Minimum Android 7, Android 12+ recommended.
