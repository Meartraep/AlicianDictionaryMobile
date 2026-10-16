package com.meartraep.alician.mobile.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder

/** A form POST the device flow performs, kept separate so it can be tested. */
data class GitHubRequest(val url: String, val body: String)

/**
 * The three calls of the device flow.
 *
 * The endpoints differ: the device code is requested from /login/device/code while
 * polling and refreshing go to /login/oauth/access_token. Using the wrong one makes
 * GitHub answer "incorrect_client_credentials", which looks like a bad Client ID.
 */
object DeviceFlowRequests {
    const val DEVICE_CODE_URL = "https://github.com/login/device/code"
    const val TOKEN_URL = "https://github.com/login/oauth/access_token"

    fun deviceCode(clientId: String): GitHubRequest =
        GitHubRequest(DEVICE_CODE_URL, form(mapOf("client_id" to clientId)))

    fun poll(clientId: String, deviceCode: String): GitHubRequest = GitHubRequest(
        TOKEN_URL,
        form(
            mapOf(
                "client_id" to clientId,
                "device_code" to deviceCode,
                "grant_type" to "urn:ietf:params:oauth:grant-type:device_code",
            ),
        ),
    )

    fun refresh(clientId: String, refreshToken: String): GitHubRequest = GitHubRequest(
        TOKEN_URL,
        form(
            mapOf(
                "client_id" to clientId,
                "grant_type" to "refresh_token",
                "refresh_token" to refreshToken,
            ),
        ),
    )

    private fun form(fields: Map<String, String>): String =
        fields.entries.joinToString("&") { (key, value) ->
            URLEncoder.encode(key, "UTF-8") + "=" + URLEncoder.encode(value, "UTF-8")
        }
}

/** What the user has to type into the browser to authorise this device. */
data class DeviceCode(
    val deviceCode: String,
    val userCode: String,
    val verificationUri: String,
    val intervalSeconds: Int,
    val expiresAtMillis: Long,
)

/** Outcome of one poll (or refresh) round. */
sealed interface DeviceToken {
    data class Granted(
        val accessToken: String,
        val accessTokenExpiresAt: Long,
        val refreshToken: String?,
        val refreshExpiresAt: Long,
    ) : DeviceToken

    /** The user has not approved yet; keep polling. */
    data object Pending : DeviceToken

    /** GitHub asked us to slow down. */
    data class SlowDown(val intervalSeconds: Int) : DeviceToken

    data class Denied(val message: String) : DeviceToken
}

/**
 * GitHub App device flow: the phone never stores a long-lived repository token.
 *
 * The user approves the app once in a browser; the phone then holds a rotating
 * refresh token and mints short-lived (8 hour) access tokens. Uninstalling the app
 * revokes access for every device at once, and the credential can only do what the
 * app installation allows.
 */
class GitHubDeviceFlow(private val clientId: String) {

    suspend fun requestCode(): DeviceCode = withContext(Dispatchers.IO) {
        val now = System.currentTimeMillis()
        val json = post(DeviceFlowRequests.deviceCode(clientId))

        // GitHub answers 200 with an "error" object when the app is not allowed to
        // use the device flow, so report that instead of failing on a missing field.
        val error = json.optString("error")
        if (error.isNotEmpty()) {
            throw IllegalStateException(describeError(error, json.optString("error_description")))
        }
        val deviceCode = json.optString("device_code")
        if (deviceCode.isBlank()) {
            throw IllegalStateException(
                "GitHub 返回了意外响应（缺少 device_code）：" + preview(json.toString()))
        }
        DeviceCode(
            deviceCode = deviceCode,
            userCode = json.optString("user_code"),
            verificationUri = json.optString("verification_uri", "https://github.com/login/device"),
            intervalSeconds = json.optInt("interval", 5),
            expiresAtMillis = PublishLogic.tokenExpiry(json.optLong("expires_in", 900L), now),
        )
    }

    /** Human readable reason plus GitHub's own wording, never a bare JSON exception. */
    private fun describeError(error: String, description: String): String {
        val base = PublishLogic.deviceFlowMessage(error)
        val detail = description.takeIf { it.isNotBlank() }?.let { "（" + it + "）" } ?: ""
        val code = if (base.contains(error)) "" else "（error: " + error + "）"
        return base + detail + code
    }

    private fun preview(text: String): String =
        text.replace(Regex("\\s+"), " ").trim().take(300)

    /** One poll round; call again after [PublishLogic.nextPollDelaySeconds] when pending. */
    suspend fun poll(deviceCode: String): DeviceToken = withContext(Dispatchers.IO) {
        interpret(post(DeviceFlowRequests.poll(clientId, deviceCode)))
    }

    /** Exchanges the rotating refresh token for a fresh short-lived access token. */
    suspend fun refresh(refreshToken: String): DeviceToken = withContext(Dispatchers.IO) {
        interpret(post(DeviceFlowRequests.refresh(clientId, refreshToken)))
    }

    /** Polls until the user approves, is denied, or the code expires. */
    suspend fun awaitGrant(
        code: DeviceCode,
        nowMillis: () -> Long = { System.currentTimeMillis() },
        onPending: (String) -> Unit = {},
    ): DeviceToken {
        var interval = code.intervalSeconds
        while (true) {
            if (nowMillis() >= code.expiresAtMillis) {
                return DeviceToken.Denied("设备码已过期，请重新发起登录。")
            }
            onPending("等待浏览器确认（用户码 " + code.userCode + "）…")
            delay(interval * 1000L)
            when (val result = poll(code.deviceCode)) {
                is DeviceToken.Granted, is DeviceToken.Denied -> return result
                is DeviceToken.SlowDown -> interval = result.intervalSeconds
                DeviceToken.Pending -> Unit
            }
        }
    }

    private fun interpret(json: JSONObject): DeviceToken {
        val error = json.optString("error")
        if (error.isNotEmpty()) {
            return when (error) {
                "authorization_pending" -> DeviceToken.Pending
                "slow_down" -> DeviceToken.SlowDown(
                    PublishLogic.nextPollDelaySeconds("slow_down", json.optInt("interval", 5)),
                )
                "access_denied" -> DeviceToken.Denied("你拒绝了授权。")
                "expired_token" -> DeviceToken.Denied("设备码已过期，请重新发起登录。")
                "device_flow_disabled" ->
                    DeviceToken.Denied("该 GitHub App 未启用 Device Flow。")
                "incorrect_client_credentials" ->
                    DeviceToken.Denied("Client ID 不正确。")
                "unsupported_grant_type", "incorrect_device_code" ->
                    DeviceToken.Denied("设备码无效，请重新发起登录。")
                else -> DeviceToken.Denied(
                    PublishLogic.deviceFlowMessage(error) + "（" + error + "）",
                )
            }
        }
        val accessToken = json.optString("access_token")
        if (accessToken.isBlank()) {
            return DeviceToken.Denied("GitHub 没有返回访问令牌。")
        }
        val now = System.currentTimeMillis()
        val expiresIn = json.optLong("expires_in", 0L)
        val refreshExpiresIn = json.optLong("refresh_token_expires_in", 0L)
        return DeviceToken.Granted(
            accessToken = accessToken,
            accessTokenExpiresAt = if (expiresIn > 0L) {
                PublishLogic.tokenExpiry(expiresIn, now)
            } else {
                now + DEFAULT_ACCESS_SECONDS * 1000L
            },
            refreshToken = json.optString("refresh_token").takeIf { it.isNotBlank() },
            refreshExpiresAt = if (refreshExpiresIn > 0L) {
                PublishLogic.tokenExpiry(refreshExpiresIn, now)
            } else {
                0L
            },
        )
    }

    private fun post(request: GitHubRequest): JSONObject {
        val body = request.body
        val connection = URL(request.url).openConnection() as HttpURLConnection
        connection.requestMethod = "POST"
        connection.connectTimeout = 15_000
        connection.readTimeout = 20_000
        connection.doOutput = true
        connection.setRequestProperty("Accept", "application/json")
        connection.setRequestProperty("Content-Type", "application/x-www-form-urlencoded")
        connection.setRequestProperty("User-Agent", USER_AGENT)
        try {
            val payload = body.toByteArray(Charsets.UTF_8)
            connection.setFixedLengthStreamingMode(payload.size)
            OutputStreamWriter(connection.outputStream, Charsets.UTF_8).use { it.write(body) }
            val code = connection.responseCode
            val text = (if (code in 200..299) connection.inputStream else connection.errorStream)
                ?.bufferedReader()?.use { it.readText() }.orEmpty()
            if (code !in 200..299) {
                throw IllegalStateException(
                    "GitHub 设备流请求失败（HTTP " + code + "）：" + preview(text))
            }
            return try {
                if (text.isBlank()) JSONObject() else JSONObject(text)
            } catch (error: org.json.JSONException) {
                // A captive portal or an interception proxy answers with HTML/plain text.
                throw IllegalStateException(
                    "GitHub 返回了非 JSON 响应（HTTP " + code + "）：" + preview(text), error)
            }
        } catch (error: java.io.IOException) {
            throw IllegalStateException(
                "无法连接 GitHub：" + (error.message ?: "网络不可用"), error)
        } finally {
            connection.disconnect()
        }
    }

    private companion object {
        const val USER_AGENT = "AlicianDictionaryMobile"
        const val DEFAULT_ACCESS_SECONDS = 8L * 60 * 60
    }
}
