package com.meartraep.alician.mobile.data

import android.util.Base64
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL

/**
 * Publishes the local database to a temporary "db-publish" branch and opens a
 * pull request.
 *
 * Deliberately narrow: it writes only the database, the ledger and the manifest to
 * a throw-away branch. The version is stamped by the phone before uploading (see
 * the Python bridge), and the pipeline verifies that it is exactly the next one
 * and that nothing outside the publishing allowlist changed.
 */
class DatabasePublisher(
    private val repository: String = DEFAULT_REPOSITORY,
    private val baseBranch: String = DEFAULT_BASE_BRANCH,
) {
    suspend fun verify(token: String): PublishCredential = withContext(Dispatchers.IO) {
        val json = request(token, "GET", "/repos/" + repository)
        val permissions = json.optJSONObject("permissions")
        val canPush = permissions?.optBoolean("push") ?: false
        PublishCredential(
            configured = true,
            maskedToken = PublishLogic.maskToken(token),
            repository = json.optString("full_name", repository),
            canPush = canPush,
            verifiedAt = System.currentTimeMillis(),
            message = if (canPush) {
                "令牌可用，具备写入权限。"
            } else {
                "令牌可用，但缺少 Contents: Read and write 权限。"
            },
        )
    }

    /** The published ledger: the version the phone has to build on. */
    suspend fun fetchPublishedLedger(): String = withContext(Dispatchers.IO) {
        val connection = URL(ledgerUrl()).openConnection() as HttpURLConnection
        connection.requestMethod = "GET"
        connection.connectTimeout = 8_000
        connection.readTimeout = 15_000
        connection.setRequestProperty("Cache-Control", "no-cache")
        connection.setRequestProperty("User-Agent", USER_AGENT)
        try {
            if (connection.responseCode != HttpURLConnection.HTTP_OK) {
                throw IllegalStateException(
                    "无法获取已发布台账（HTTP " + connection.responseCode + "）。")
            }
            connection.inputStream.bufferedReader().use { it.readText() }
        } catch (error: java.io.IOException) {
            throw IllegalStateException(
                "无法获取已发布台账：" + (error.message ?: "网络不可用"), error)
        } finally {
            connection.disconnect()
        }
    }

    /**
     * Commits [files] on a publishing branch and opens the pull request. The version
     * is already stamped into them, so the pipeline only verifies.
     */
    suspend fun publish(
        token: String,
        files: List<PublishFile>,
        databaseSize: Long,
        notes: String,
        onProgress: (PublishProgress) -> Unit,
    ): PublishOutcome = withContext(Dispatchers.IO) {
        val branch = PublishLogic.branchName(System.currentTimeMillis())
        onProgress(PublishProgress(PublishStage.VERIFYING, "正在校验访问令牌…"))
        val credential = verify(token)
        if (!credential.canPush) {
            throw IllegalStateException(credential.message)
        }

        val baseSha = request(token, "GET", "/repos/" + repository + "/git/ref/heads/" + baseBranch)
            .getJSONObject("object").getString("sha")
        val baseTree = request(token, "GET", "/repos/" + repository + "/git/commits/" + baseSha)
            .getJSONObject("tree").getString("sha")

        onProgress(PublishProgress(PublishStage.UPLOADING, "正在上传（" +
            PublishLogic.formatMegabytes(databaseSize) + "）…"))
        val tree = JSONArray()
        for (file in files) {
            val blobSha = request(
                token,
                "POST",
                "/repos/" + repository + "/git/blobs",
                JSONObject()
                    .put("content", Base64.encodeToString(file.bytes, Base64.NO_WRAP))
                    .put("encoding", "base64"),
            ).getString("sha")
            tree.put(
                JSONObject()
                    .put("path", file.path)
                    .put("mode", "100644")
                    .put("type", "blob")
                    .put("sha", blobSha),
            )
        }
        val treeSha = request(
            token,
            "POST",
            "/repos/" + repository + "/git/trees",
            JSONObject().put("base_tree", baseTree).put("tree", tree),
        ).getString("sha")

        val commitSha = request(
            token,
            "POST",
            "/repos/" + repository + "/git/commits",
            JSONObject()
                .put("message", COMMIT_MESSAGE)
                .put("tree", treeSha)
                .put("parents", JSONArray().put(baseSha)),
        ).getString("sha")

        request(
            token,
            "POST",
            "/repos/" + repository + "/git/refs",
            JSONObject().put("ref", "refs/heads/" + branch).put("sha", commitSha),
        )

        onProgress(PublishProgress(PublishStage.OPENING_PULL_REQUEST, "正在创建合并请求…"))
        val pullRequest = request(
            token,
            "POST",
            "/repos/" + repository + "/pulls",
            JSONObject()
                .put("title", "数据库发布：" + PublishLogic.formatMegabytes(databaseSize))
                .put("head", branch)
                .put("base", baseBranch)
                .put("body", PublishLogic.pullRequestBody(notes)),
        )
        val number = pullRequest.optInt("number", 0)
        val url = pullRequest.optString("html_url")
        onProgress(PublishProgress(PublishStage.DONE, "已创建合并请求 #" + number))
        PublishOutcome(branch, number, url)
    }

    suspend fun pullRequestState(token: String, number: Int): PullRequestState =
        withContext(Dispatchers.IO) {
            val json = request(token, "GET", "/repos/" + repository + "/pulls/" + number)
            PullRequestState(
                number = json.optInt("number", number),
                state = json.optString("state"),
                merged = json.optBoolean("merged"),
                mergeableState = json.optString("mergeable_state"),
                url = json.optString("html_url"),
            )
        }

    suspend fun merge(token: String, number: Int): String = withContext(Dispatchers.IO) {
        val json = request(
            token,
            "PUT",
            "/repos/" + repository + "/pulls/" + number + "/merge",
            JSONObject().put("merge_method", "squash"),
        )
        if (json.optBoolean("merged")) {
            json.optString("message", "合并请求已合并。")
        } else {
            throw IllegalStateException(json.optString("message", "合并失败：检查尚未通过？"))
        }
    }

    private fun request(
        token: String,
        method: String,
        path: String,
        body: JSONObject? = null,
    ): JSONObject {
        val connection = URL(API_ROOT + path).openConnection() as HttpURLConnection
        connection.requestMethod = method
        connection.connectTimeout = 15_000
        connection.readTimeout = 120_000
        connection.setRequestProperty("Authorization", "Bearer " + token)
        connection.setRequestProperty("Accept", "application/vnd.github+json")
        connection.setRequestProperty("X-GitHub-Api-Version", "2022-11-28")
        connection.setRequestProperty("User-Agent", "AlicianDictionaryMobile")
        try {
            if (body != null) {
                val payload = body.toString().toByteArray(Charsets.UTF_8)
                connection.doOutput = true
                connection.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                connection.setFixedLengthStreamingMode(payload.size)
                connection.outputStream.use { it.write(payload) }
            }
            val code = connection.responseCode
            val text = (if (code in 200..299) connection.inputStream else connection.errorStream)
                ?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) {
                throw IllegalStateException(describeFailure(code, text))
            }
            return if (text.isBlank()) JSONObject() else JSONObject(text)
        } catch (error: java.io.IOException) {
            throw IllegalStateException("网络请求失败：" + (error.message ?: "无法连接 GitHub"), error)
        } finally {
            connection.disconnect()
        }
    }

    private fun describeFailure(code: Int, body: String): String {
        val detail = runCatching { JSONObject(body).optString("message") }.getOrDefault("")
        val hint = when (code) {
            401 -> "访问令牌无效或已过期，请重新配置。"
            403 -> "令牌权限不足或触发了 GitHub 限流。"
            404 -> "找不到仓库或分支：令牌可能没有该仓库的权限。"
            422 -> "GitHub 拒绝了请求（分支或合并请求可能已存在）。"
            else -> "GitHub 返回 HTTP " + code + "。"
        }
        return if (detail.isBlank()) hint else hint + "（" + detail + "）"
    }

    /** Where the ledger lives for the configured repository and branch. */
    fun ledgerUrl(): String =
        RAW_ROOT + repository + "/" + baseBranch + "/" + LEDGER_PATH

    /** Paths of the files a publication commit carries. */
    object Paths {
        const val DATABASE = "app/src/main/assets/translated.db"
        const val LEDGER = "database-versions.json"
        const val MANIFEST = "database-manifest.json"
        const val SIGNATURE = "database-publish-signature.json"
    }

    private companion object {
        const val API_ROOT = "https://api.github.com"
        const val RAW_ROOT = "https://raw.githubusercontent.com/"
        const val DEFAULT_REPOSITORY = "Meartraep/AlicianDictionaryMobile"
        const val DEFAULT_BASE_BRANCH = "main"
        const val LEDGER_PATH = "database-versions.json"
        const val COMMIT_MESSAGE = "chore(database): 手机端发布数据库"
        const val USER_AGENT = "AlicianDictionaryMobile"
    }
}
