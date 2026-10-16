package com.meartraep.alician.mobile.data

/** Result of validating the stored GitHub publishing token. */
data class PublishCredential(
    val configured: Boolean,
    val maskedToken: String = "",
    val repository: String = "",
    val canPush: Boolean = false,
    val verifiedAt: Long = 0L,
    val message: String = "",
)

/** What the phone is about to publish, checked before anything is uploaded. */
data class PublishPreview(
    val localVersion: Int,
    val localSize: Long,
    val localSha1: String,
    val publishedVersion: Int,
    val publishedSha1: String,
    val hasChanges: Boolean,
    val blockingReason: String? = null,
)

enum class PublishStage { IDLE, VERIFYING, UPLOADING, OPENING_PULL_REQUEST, DONE, FAILED }

data class PublishProgress(
    val stage: PublishStage = PublishStage.IDLE,
    val detail: String = "",
)

data class PublishOutcome(
    val branch: String,
    val pullRequestNumber: Int,
    val pullRequestUrl: String,
)

/** State of the pull request the publishing pipeline created. */
data class PullRequestState(
    val number: Int,
    val state: String,
    val merged: Boolean,
    val mergeableState: String,
    val url: String,
)
