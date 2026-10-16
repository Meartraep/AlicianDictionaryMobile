package com.meartraep.alician.mobile.data

/**
 * Resolves the credential used to talk to GitHub.
 *
 * Preferred: a GitHub App access token obtained through the device flow -- short
 * lived (about eight hours), refreshed from a rotating refresh token, and revocable
 * for every device by uninstalling the app. Fallback: the fine-grained personal
 * access token, so an existing setup keeps working.
 */
class PublishAuth(
    private val store: PublishCredentialStore,
    private val flowFactory: (String) -> GitHubDeviceFlow = { clientId -> GitHubDeviceFlow(clientId) },
    private val now: () -> Long = { System.currentTimeMillis() },
) {
    val usesApp: Boolean get() = store.hasAppCredential

    val hasCredential: Boolean get() = store.hasAppCredential || store.hasCredential

    /** A currently valid token, refreshing the app token when it is about to expire. */
    suspend fun accessToken(): String? {
        if (store.hasAppCredential) {
            val cached = store.loadAccessToken()
            if (!cached.isNullOrBlank() &&
                !PublishLogic.tokenNeedsRefresh(store.accessTokenExpiresAt, now())
            ) {
                return cached
            }
            val refreshToken = store.loadAppRefreshToken()
            if (!refreshToken.isNullOrBlank()) {
                when (val refreshed = flowFactory(store.appClientId).refresh(refreshToken)) {
                    is DeviceToken.Granted -> {
                        store.saveAppTokens(
                            refreshToken = refreshed.refreshToken,
                            refreshExpiresAt = refreshed.refreshExpiresAt,
                            accessToken = refreshed.accessToken,
                            accessTokenExpiresAt = refreshed.accessTokenExpiresAt,
                        )
                        return refreshed.accessToken
                    }
                    // Anything else (revoked app, expired refresh token) falls back to
                    // the personal token when one is configured.
                    else -> Unit
                }
            }
        }
        return store.load()
    }
}
