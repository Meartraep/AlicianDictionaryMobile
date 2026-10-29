# Alician Dictionary Mobile — Changelog (English)

> Chinese release notes are shown on the GitHub Releases page. This document is
> the dedicated English version for readers who prefer English.

## v1.12.0 (2026-10-30)

### Highlights

- **The database manager is now part of the dictionary.** The dictionary's first
  tab gains a "Data" workspace for day-to-day content work, while the old
  standalone manager becomes a rarely-needed governance screen under Settings.
- **The bundled database is upgraded to v2.** 19 unread legacy tables and one
  orphan translation row were removed and the file was vacuumed. Business tables
  drop from 32 to 13 and the asset shrinks from 2,854,912 to 2,596,864 bytes;
  the 1,339 headwords and 53 songs are unchanged.
- **The writing assistant now highlights uncertain senses instead of rare
  words.** Blue marks dictionary senses annotated with a `(?)` uncertainty
  marker; low frequency or low variety no longer affects the writing assistant.

### Detailed changes

- The dictionary gains a "Data" workspace: paged browsing of the 13 business
  tables, exact search, curated per-table editing (create words and senses,
  delete previews, schema validation), reference candidates and CSV / SQLite
  export.
- One writer for all edits: a single SQLite connection, write guard,
  declarative schema checks, automatic recovery points and a local-edit ledger.
  Destructive actions require preview, a recovery point and a second
  confirmation.
- Maintenance actions now live in the dictionary: recount frequency/variety,
  rebuild `no_class`, allow-listed global replace (case-sensitive,
  preview-gated) and database diagnostics.
- Settings now has a single "Database" card plus a governance screen: version
  and identity, update checks, recovery-point rollback, on-device publishing,
  whole-database import/export, restore-bundled-database and the upstream
  full-dictionary source.
- Fixed SQLite connection leaks that blocked recovery-point rollback and
  whole-database import; lyric maintenance now reads the single `songs.lyric`
  source.
- Writing assistant blue highlights now come from dictionary senses annotated
  with a `(?)` uncertainty marker (any sense, or the headword display
  explanation). Half/full-width parentheses and question marks are accepted; a
  plain question mark is not. Unknown words still take the red highlight, and
  the page, metric card and issue list now say "uncertain meaning".
- Frequency/variety no longer drive or appear in the writing assistant, but
  remain in the study ordering, dictionary details, translation scoring and
  maintenance recount.
- Editing a `(?)` marker in the dictionary editor or data manager refreshes
  the writing assistant immediately. 184 of the 1,339 headwords currently
  carry the marker.

### Technical details

- Version: 1.12.0 (versionCode 16)
- ABIs: arm64-v8a and x86_64, one signed APK each
- Database: db_version 2 (2026-10-29), first shipped with this release

### Release assets

- `AlicianDictionary-v1.12.0-arm64-v8a.apk`: signed APK for Android devices
- `AlicianDictionary-v1.12.0-x86_64.apk`: signed APK for emulators / x86 Chromebooks
- `AlicianDictionary-v1.12.0.intoto.jsonl`: SLSA build provenance covering both APKs
- `SHA256SUMS.txt`: asset checksums

## v1.11.0 (2026-10-21)

### Highlights

- **Much smaller download: one APK per ABI.** Releases now publish
  `AlicianDictionary-<tag>-arm64-v8a.apk` for phones and
  `AlicianDictionary-<tag>-x86_64.apk` for emulators and x86 Chromebooks instead of
  one universal APK. Each download is about 25.8 MB instead of 57.7 MB, and the
  single Sigstore-signed SLSA provenance bundle covers both APKs.
- **The bundled `jieba` is trimmed to what the app uses.** The optional
  `lac_small` (Paddle LAC model), `posseg` (part-of-speech tables) and `analyse`
  (TF-IDF/TextRank data) directories are never imported at runtime, but Chaquopy
  used to pack all of them into the uncompressed requirements archive (~19 MB). The
  build now removes them while keeping `dict.txt`, `finalseg` and the dist-info
  metadata, cutting the archive to about 2.6 MB without changing segmentation.
- **Release guards.** The release workflow now rejects an APK containing more than
  one ABI, a jieba archive over 3 MiB, or an APK over 28 MB, so size regressions
  fail the release instead of shipping silently.

### Technical details

- Version: 1.11.0 (versionCode 15)
- ABIs: arm64-v8a and x86_64, one signed APK each
- Database: unchanged (db_version 1)

### Release assets

- `AlicianDictionary-v1.11.0-arm64-v8a.apk`: signed APK for Android devices
- `AlicianDictionary-v1.11.0-x86_64.apk`: signed APK for emulators / x86 Chromebooks
- `AlicianDictionary-v1.11.0.intoto.jsonl`: SLSA build provenance covering both APKs
- `SHA256SUMS.txt`: asset checksums

## v1.10.0 (2026-10-17)

### Highlights

- **Publish the database from the phone.** Settings now has a publishing section: the
  app reads the published ledger, takes the next version, stamps it into a copy of the
  local database, appends `database-versions.json`, re-projects
  `database-manifest.json`, commits those three files on a `db-publish/*` branch and
  opens a pull request. The pipeline only verifies: the changed paths must be within
  the publishing allowlist, the new version must be exactly the one after the published
  ledger tip, and sha1, size, the marker inside the database and the manifest must all
  agree.
- **Every publication is signed by a device key.** A non-exportable EC P-256 key is
  generated in the Android Keystore; when the device has a screen lock, signing asks
  for the device credential first. CI verifies the signature against the public key
  registered at `.github/db-publish-pubkey.pem` on the target branch, which a
  publishing pull request may never modify. The signed message binds the previous
  version and hash (so an old signature cannot be replayed), the exact database bytes
  and a digest of the release note, so a stolen GitHub token can no longer publish
  anything on its own.
- **GitHub App sign-in (device flow).** Instead of a long-lived personal access token
  the app can hold only a rotating refresh token and mint access tokens that last about
  eight hours, refreshed shortly before they expire. Uninstalling the app revokes
  access for every device at once; the personal token path still works as a fallback.
- **Database version uniqueness is enforced end to end.** `database-versions.json` is
  an append-only ledger with strictly increasing versions and unique hashes, the
  manifest is a projection of its newest entry, CI verifies the invariants on every
  pull request and before a tagged build, and the release pipeline compares the
  published bytes with the ledger. `Ledger, manifest and database agree` is a required
  status check on `main`.
- **Release metadata is gated.** The signed-APK workflow refuses to build a tag whose
  database, manifest and ledger do not agree, and re-verifies the published bytes
  afterwards.

### Fixes

- The GitHub App device flow requested its device code from the token endpoint, so
  GitHub answered `incorrect_client_credentials` and the app reported it as a wrong
  Client ID. The three calls now use their own endpoints, with regression tests.
- Device-flow failures no longer surface as a bare JSON parse error; they show a
  Chinese explanation plus GitHub's error code and response excerpt.

### Verification

- 51 Android unit tests, 116 Python tests (version guards 12, publication verification
  15, signature 16, publication preparation 9, grammar and composition 64).
- End-to-end drills on the real repository: a stamped publication opens a pull request
  whose required check turns green with no manual approval; an unsigned publication is
  refused; a tampered signature, a different key and a rewritten release note are all
  refused.
- Registered publishing key fingerprint: `6324261ecd9114a0`.

## v1.9.0 (2026-10-14)

### Highlights

- **Database updates are checked automatically at startup**: after a cold start
  the app fetches a small published manifest from GitHub (about 300 bytes, silent
  on failure) and, when a newer revision exists, raises a prompt and waits for the
  user to accept the download. Choosing "Later" remembers that revision, so the
  prompt only returns for a newer one. Downloads are verified by size and SHA-1,
  and the installed database is backed up before it is replaced. Settings gained an
  "auto check at startup" switch plus the local database revision and the time of
  the last check.
- **Official Japanese/English lyrics now align sentence by sentence**: fixed the
  translator showing a whole stanza's translation on two adjacent lines (A
  containing B and B containing A) — 95 blocks / 218 lines, with 266 lines corrected
  and 3 added. Four upstream source defects were fixed as well: the Alice_Music
  English block shifted by one stanza, killed_by_angel S02/S03 swapped, Wanderers
  S21-S23 English split across three stanzas, and a stray `<br>` in Fehlt.
- **Study mode asks which script to learn**: first entry into the study tab offers
  "Alician glyphs" (glyph primer plus its recognition quiz) or "Latin transcription
  only", which skips the glyph quiz and starts the deck right away.
- **Translation engine recalibrated against the official Japanese lyrics**: Elize,
  Zel, end and Loosya were re-checked against the corpus, Chinese chunking and
  composition improved, and semantic expansions now default to on. The grammar
  document gained corpus-attested sections 4.15-4.19 and 7.1-7.2.

### Fixes

- The database update action no longer points at the upstream full database, which
  carries no official translations and would have wiped them; it is now a manual
  "check and import upstream full database" entry with an explanatory label.

### Build and toolchain

- Chaquopy's pip runs with `--no-cache-dir`, fixing wheel-cache failures in
  confined build environments.
- `DATABASE_ASSET_VERSION` tracks the new database asset; the asset itself now
  carries a `database_metadata` revision marker.

### Verification

- 37 Android unit tests pass, including 8 new `DatabaseUpdateLogicTest` cases.
- 64 Python tests pass (`test_attested_grammar` + `test_chinese_composition`).
- Alignment is enforced mechanically: every split fragment of the 149
  multi-sentence stanzas rejoins the official source text verbatim, and a full
  1279-line duplicate scan dropped adjacent duplicated blocks from 95 to 6 (the
  remainder are lines whose Alician original is identical).
- The published manifest and database were verified byte-for-byte (size/SHA-1) and
  the startup decision was simulated: existing installs (v0) receive the prompt,
  fresh installs (v1) stay silent, and "Later" silences that revision.

### Technical details

- Version: 1.9.0 (versionCode 13)
- ABIs: arm64-v8a + x86_64

### Release assets

- `AlicianDictionary-v1.9.0.apk`: signed release APK (arm64-v8a + x86_64)
- `AlicianDictionary-v1.9.0.apk.intoto.jsonl`: SLSA build provenance
- `SHA256SUMS.txt`: SHA-256 checksums of the assets

**Full changelog**: https://github.com/Meartraep/AlicianDictionaryMobile/compare/v1.8.1...v1.9.0

## v1.8.1 (2026-09-19)

### Fixes

- **Exact dictionary search no longer crashes**: with "Exact match" enabled,
  looking up a word that is not in the dictionary made the backend return
  spelling suggestions under `words` (an array) while the client read `word`
  (a string). Every suggestion therefore parsed into an empty string, and the
  Compose list keyed on that field hit duplicate keys and threw, killing the
  app. The backend now also emits `word`, the client accepts either field, and
  the suggestion list uses unique keys and drops blank entries.
- **Page titles no longer overlap their subtitles**: the Settings and Study
  pages drew their top headline and its small caption on top of each other.
  Both screens host their content in a `LazyVerticalGrid`, and
  `LazyGridMeasuredItem` places every direct child of one item at the same
  coordinate (the item height is the maximum of its children) — unlike
  `LazyColumn`, which sums the heights and lays children out in sequence. The
  title and caption are now wrapped in an explicit `Column`, fixing landscape
  and portrait alike.
- **UI settings preview card refreshes correctly**: the Material preview card
  did not update after changing theme, palette or typography; it now carries a
  key so that it reacts to settings changes.

### Build and toolchain

- Android Gradle Plugin upgraded to 9.3.2, Chaquopy migrated to Python 3.14
- CI dependencies bumped: `gradle/actions/setup-gradle`,
  `gradle/actions/wrapper-validation`, `actions/setup-java`, `actions/attest`

### Technical details

- Version: 1.8.1 (versionCode 12)
- ABIs: arm64-v8a + x86_64

### Release assets

- `AlicianDictionary-v1.8.1.apk`: signed release APK (arm64-v8a + x86_64)
- `AlicianDictionary-v1.8.1.apk.intoto.jsonl`: SLSA build provenance
- `SHA256SUMS.txt`: SHA-256 checksums of the assets

**Full changelog**: https://github.com/Meartraep/AlicianDictionaryMobile/compare/v1.8.0...v1.8.1

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
