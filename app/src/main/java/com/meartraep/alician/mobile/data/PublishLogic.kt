package com.meartraep.alician.mobile.data

import java.security.MessageDigest
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone

/**
 * Pure rules for publishing the database from the phone.
 *
 * The phone stamps the next version itself (see the Python bridge) and signs the
 * publication with a non-exportable Keystore key; the pipeline verifies both.
 * These helpers decide what may be uploaded, how the request looks, and produce
 * the exact bytes the device key signs.
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

    const val SIGNATURE_HEADER = "alician-db-publish-v1"
    const val SIGNATURE_ALGORITHM = "ECDSA-P256-SHA256"

    fun notesSha256(notes: String): String =
        MessageDigest.getInstance("SHA-256").digest(notes.toByteArray(Charsets.UTF_8))
            .joinToString("") { byte -> "%02x".format(byte) }

    // ---- GitHub App device flow -----------------------------------------

    /** An access token this close to expiry is refreshed before it is used. */
    const val TOKEN_REFRESH_SKEW_MILLIS = 5L * 60 * 1000

    fun tokenExpiry(expiresInSeconds: Long, nowMillis: Long): Long =
        nowMillis + expiresInSeconds * 1000L

    fun tokenNeedsRefresh(expiresAtMillis: Long, nowMillis: Long): Boolean =
        expiresAtMillis <= 0L || expiresAtMillis - nowMillis <= TOKEN_REFRESH_SKEW_MILLIS

    /** GitHub asks for a longer interval after a "slow_down"; every other round keeps it. */
    fun nextPollDelaySeconds(error: String?, intervalSeconds: Int): Int =
        if (error == "slow_down") intervalSeconds + 5 else intervalSeconds

    fun deviceFlowMessage(error: String): String = when (error) {
        "authorization_pending" -> "等待你在浏览器中确认…"
        "slow_down" -> "GitHub 要求降低轮询频率，继续等待…"
        "expired_token" -> "设备码已过期，请重新发起登录。"
        "access_denied" -> "授权被拒绝。"
        "device_flow_disabled" -> "该 GitHub App 未启用 Device Flow。"
        "incorrect_client_credentials" -> "Client ID 不正确。"
        else -> "登录失败。"
    }

    /**
     * The bytes the device key signs.
     *
     * Must stay byte-identical to verify_publication_signature.build_message: it
     * binds the publication to the ledger tip it was built on (so an old signed
     * payload cannot be replayed), to the exact database bytes, and to the release
     * note users will see.
     */
    fun buildSignatureMessage(
        previousVersion: Int,
        previousSha1: String,
        version: Int,
        sha1: String,
        size: Long,
        publishedAt: String,
        notes: String,
    ): String = buildString {
        append(SIGNATURE_HEADER).append('\n')
        append("prev_version=").append(previousVersion).append('\n')
        append("prev_sha1=").append(previousSha1.lowercase(Locale.US)).append('\n')
        append("version=").append(version).append('\n')
        append("sha1=").append(sha1.lowercase(Locale.US)).append('\n')
        append("size=").append(size).append('\n')
        append("published_at=").append(publishedAt).append('\n')
        append("notes_sha256=").append(notesSha256(notes)).append('\n')
    }

    /** The small JSON file the publication commit carries next to the database. */
    fun signatureDocument(keyId: String, signature: String): String = buildString {
        append("{\n")
        append("  \"algorithm\": \"").append(SIGNATURE_ALGORITHM).append("\",\n")
        append("  \"key_id\": \"").append(keyId).append("\",\n")
        append("  \"signature\": \"").append(signature).append("\"\n")
        append("}\n")
    }

    fun pullRequestTitle(preview: PublishPreview): String =
        "数据库发布：" + preview.localSha1.take(10) + "（" + formatMegabytes(preview.localSize) + "）"

    fun pullRequestBody(notes: String): String {
        val normalized = normalizeNotes(notes)
        return normalized.ifEmpty { "由手机端上传的数据库更新。" }
    }
}
