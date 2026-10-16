package com.meartraep.alician.mobile.data

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Pure rules for publishing the database from the phone.
 *
 * The phone never chooses a version number: it uploads the database to a
 * temporary publishing branch and the CI pipeline stamps the next ledger
 * version. These helpers only decide what may be uploaded and how the request
 * looks.
 */
object PublishLogic {
    const val BRANCH_PREFIX = "db-publish/"
    const val WARN_DATABASE_BYTES = 16L * 1024 * 1024
    const val MAX_DATABASE_BYTES = 64L * 1024 * 1024
    const val NOTES_LIMIT = 500

    /** Branch names carry the upload time so repeated publishes never collide. */
    fun branchName(nowMillis: Long): String {
        val format = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US)
        format.timeZone = TimeZone.getTimeZone("UTC")
        return BRANCH_PREFIX + format.format(Date(nowMillis))
    }

    /** Only ever show a prefix and suffix; the token itself stays in the Keystore. */
    fun maskToken(token: String): String {
        val trimmed = token.trim()
        return when {
            trimmed.length <= 12 -> "****"
            else -> trimmed.take(7) + "…" + trimmed.takeLast(4)
        }
    }

    /** Release notes become public text, so collapse and cap them. */
    fun normalizeNotes(notes: String): String {
        val collapsed = notes.split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")
        return when {
            collapsed.isEmpty() -> ""
            collapsed.length <= NOTES_LIMIT -> collapsed
            else -> collapsed.take(NOTES_LIMIT)
        }
    }

    /** Null when the size is acceptable, otherwise the reason to show the user. */
    fun validateDatabaseSize(size: Long): String? = when {
        size <= 0L -> "数据库文件不存在或为空。"
        size > MAX_DATABASE_BYTES ->
            "数据库过大（" + formatMegabytes(size) + "），上限为 " + formatMegabytes(MAX_DATABASE_BYTES) + "。"
        size > WARN_DATABASE_BYTES ->
            "数据库较大（" + formatMegabytes(size) + "），上传会消耗较多流量。"
        else -> null
    }

    fun formatMegabytes(bytes: Long): String =
        String.format(Locale.US, "%.1f MB", bytes / 1024.0 / 1024.0)

    /**
     * Decides whether the local database can be published. [publishedSha1] comes
     * from the manifest the app already reads, so an unreachable GitHub blocks the
     * flow before anything is uploaded.
     */
    fun buildPreview(
        localVersion: Int,
        localSize: Long,
        localSha1: String,
        publishedVersion: Int,
        publishedSha1: String,
    ): PublishPreview {
        val local = localSha1.trim().lowercase(Locale.US)
        val published = publishedSha1.trim().lowercase(Locale.US)
        val hasChanges = local.isNotEmpty() && published.isNotEmpty() && local != published
        val blocking = when {
            published.isEmpty() -> "尚未获取已发布数据库的指纹，请先联网检查更新。"
            local.isEmpty() -> "无法读取本地数据库指纹。"
            !hasChanges -> "本地数据库与已发布版本完全相同，没有可发布的改动。"
            else -> validateDatabaseSize(localSize)
        }
        return PublishPreview(
            localVersion = localVersion,
            localSize = localSize,
            localSha1 = local,
            publishedVersion = publishedVersion,
            publishedSha1 = published,
            hasChanges = hasChanges,
            blockingReason = blocking,
        )
    }

    /** The version a publication carries: exactly one step after the published one. */
    fun nextVersion(publishedVersion: Int): Int = publishedVersion + 1

    fun pullRequestTitle(preview: PublishPreview): String =
        "数据库发布：" + preview.localSha1.take(10) + "（" + formatMegabytes(preview.localSize) + "）"

    fun pullRequestBody(notes: String): String {
        val normalized = normalizeNotes(notes)
        return normalized.ifEmpty { "由手机端上传的数据库更新。" }
    }
}
