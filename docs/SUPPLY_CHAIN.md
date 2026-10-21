# APK supply-chain provenance

Tagged releases are built on a GitHub-hosted runner by
`.github/workflows/release-slsa.yml`. The workflow tests the source, builds one
signed APK per supported ABI, verifies both APKs, and asks GitHub Artifact
Attestations to create a Sigstore-signed SLSA provenance statement whose
subjects are the two APK digests.

This is designed to meet the SLSA v1.2 Build L2 requirements: provenance exists,
is authenticated by the hosted build platform, is distributed with the release,
and the build runs on hosted infrastructure. It does not claim SLSA Build L3 or
SLSA Source Track conformance.

## One-time repository setup

Create these GitHub Actions repository secrets:

- `ANDROID_KEYSTORE_BASE64`: the release keystore encoded as base64
- `ANDROID_KEYSTORE_PASSWORD`: the keystore password
- `ANDROID_KEY_ALIAS`: the release key alias
- `ANDROID_KEY_PASSWORD`: the release key password

For example, PowerShell can encode the keystore without writing another copy:

```powershell
[Convert]::ToBase64String(
    [IO.File]::ReadAllBytes("C:\path\to\release.jks")
) | gh secret set ANDROID_KEYSTORE_BASE64
gh secret set ANDROID_KEYSTORE_PASSWORD
gh secret set ANDROID_KEY_ALIAS
gh secret set ANDROID_KEY_PASSWORD
```

Protect the default branch and `v*` tags with repository rulesets. Require pull
requests and successful checks for workflow changes, restrict tag creation to
release maintainers, and enable immutable releases if the repository plan offers
that setting. These controls are recommended defense in depth; they are not
substitutes for verifying the provenance.

## Release

Ensure the tag matches the app version, then push it. Only the tagged source is
checked out; local APK files are never published by this workflow.

```bash
git tag -s v1.3.0 -m "Alician Dictionary 1.3.0"
git push origin v1.3.0
```

The resulting GitHub release contains:

- `AlicianDictionary-<tag>-arm64-v8a.apk` and
  `AlicianDictionary-<tag>-x86_64.apk`: signed release APKs, one per supported
  ABI. AGP 9 cannot combine `splits.abi` with the `ndk.abiFilters` setting that
  Chaquopy 17 requires, so the workflow builds each ABI in a separate Gradle
  invocation (`-PtargetAbi=<abi>`) and the guard in
  `scripts/verify_release_apk.py` rejects a universal APK or an unexpected size;
- `SHA256SUMS.txt` with one checksum line per APK; and
- `AlicianDictionary-<tag>.intoto.jsonl`: a single Sigstore bundle whose SLSA
  provenance covers both APKs.

Choose `arm64-v8a` for Android devices and `x86_64` for emulators and x86
Chromebooks. Installing the wrong one fails with
`INSTALL_FAILED_NO_MATCHING_ABIS`. The workflow creates the release with generated
notes, so add these ABI/installation instructions to the release body when
publishing.

## Verify before installing

Download the APK matching your device architecture from the GitHub release and
verify its provenance with GitHub CLI. Pinning the repository, workflow, hosted
runner, and tag ref makes the verification policy substantially stricter than
checking only that some attestation exists.

```bash
gh attestation verify AlicianDictionary-v1.11.0-arm64-v8a.apk \
  --repo Meartraep/AlicianDictionaryMobile \
  --signer-workflow Meartraep/AlicianDictionaryMobile/.github/workflows/release-slsa.yml \
  --source-ref refs/tags/v1.11.0 \
  --deny-self-hosted-runners
```

The same command accepts the `x86_64` APK: the release's single provenance
bundle lists both APKs as subjects. The command verifies the APK digest, the
Sigstore signature and certificate, the SLSA provenance predicate type, the
source repository, the exact release workflow, the tag ref, and the use of a
GitHub-hosted runner. An offline verifier can use the release's
`AlicianDictionary-<tag>.intoto.jsonl` file with `--bundle`, but it must also
provision an appropriate trusted root as described by GitHub's offline
verification documentation.
