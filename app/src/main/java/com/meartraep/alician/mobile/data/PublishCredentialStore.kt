package com.meartraep.alician.mobile.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.core.content.edit
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Keeps the GitHub publishing token encrypted with a non-exportable Android
 * Keystore key.
 *
 * The ciphertext lives in its own preferences file ("alician_publish") so it can
 * be excluded from cloud backup and adb backup; the token itself is never written
 * to disk in plain text and never logged.
 */
class PublishCredentialStore(context: Context) {
    private val preferences =
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)

    val hasCredential: Boolean get() = preferences.contains(KEY_CIPHERTEXT)

    /** Display-only prefix/suffix; decryption is not needed to show it. */
    val maskedToken: String get() = preferences.getString(KEY_MASK, "").orEmpty()

    val verifiedAt: Long get() = preferences.getLong(KEY_VERIFIED_AT, 0L)

    fun save(token: String) {
        saveSecret(KEY_CIPHERTEXT, KEY_IV, token)
        preferences.edit {
            putString(KEY_MASK, PublishLogic.maskToken(token))
            putLong(KEY_VERIFIED_AT, System.currentTimeMillis())
        }
    }

    /** Returns null when nothing is stored or the Keystore key no longer decrypts. */
    fun load(): String? = loadSecret(KEY_CIPHERTEXT, KEY_IV)

    // ---- GitHub App (device flow): no long-lived repository credential ------

    val hasAppCredential: Boolean get() = preferences.contains(KEY_APP_REFRESH)

    val appClientId: String get() = preferences.getString(KEY_APP_CLIENT_ID, "").orEmpty()

    val appRefreshExpiresAt: Long get() = preferences.getLong(KEY_APP_REFRESH_EXPIRES, 0L)

    fun saveAppClientId(clientId: String) {
        preferences.edit { putString(KEY_APP_CLIENT_ID, clientId.trim()) }
    }

    /**
     * Stores the rotating refresh token (and the new access token in the same step).
     * The refresh token is the only long-lived secret left, and it is scoped to the
     * app installation: uninstalling the app revokes it for every device at once.
     */
    fun saveAppTokens(
        refreshToken: String?,
        refreshExpiresAt: Long,
        accessToken: String,
        accessTokenExpiresAt: Long,
    ) {
        if (!refreshToken.isNullOrBlank()) {
            saveSecret(KEY_APP_REFRESH, KEY_APP_REFRESH_IV, refreshToken)
            preferences.edit { putLong(KEY_APP_REFRESH_EXPIRES, refreshExpiresAt) }
        }
        saveSecret(KEY_ACCESS, KEY_ACCESS_IV, accessToken)
        preferences.edit { putLong(KEY_ACCESS_EXPIRES, accessTokenExpiresAt) }
    }

    fun loadAppRefreshToken(): String? = loadSecret(KEY_APP_REFRESH, KEY_APP_REFRESH_IV)

    fun loadAccessToken(): String? = loadSecret(KEY_ACCESS, KEY_ACCESS_IV)

    val accessTokenExpiresAt: Long get() = preferences.getLong(KEY_ACCESS_EXPIRES, 0L)

    fun clearApp() {
        preferences.edit {
            remove(KEY_APP_REFRESH)
            remove(KEY_APP_REFRESH_IV)
            remove(KEY_APP_CLIENT_ID)
            remove(KEY_APP_REFRESH_EXPIRES)
            remove(KEY_ACCESS)
            remove(KEY_ACCESS_IV)
            remove(KEY_ACCESS_EXPIRES)
        }
    }

    // ---- encrypted storage --------------------------------------------------

    private fun saveSecret(cipherKey: String, ivKey: String, secret: String) {
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        val ciphertext = cipher.doFinal(secret.toByteArray(Charsets.UTF_8))
        preferences.edit {
            putString(cipherKey, Base64.encodeToString(ciphertext, Base64.NO_WRAP))
            putString(ivKey, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
        }
    }

    private fun loadSecret(cipherKey: String, ivKey: String): String? {
        val ciphertext = preferences.getString(cipherKey, null) ?: return null
        val iv = preferences.getString(ivKey, null) ?: return null
        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                secretKey(),
                GCMParameterSpec(TAG_BITS, Base64.decode(iv, Base64.NO_WRAP)),
            )
            String(cipher.doFinal(Base64.decode(ciphertext, Base64.NO_WRAP)), Charsets.UTF_8)
        } catch (error: Exception) {
            // Key invalidated (for example after a device credential change): every
            // stored secret is unusable, so drop them instead of keeping broken entries.
            clear()
            null
        }
    }

    fun markVerified() {
        preferences.edit { putLong(KEY_VERIFIED_AT, System.currentTimeMillis()) }
    }

    fun clear() {
        preferences.edit { clear() }
    }

    private fun secretKey(): SecretKey {
        val keyStore = KeyStore.getInstance(PROVIDER).apply { load(null) }
        val existing = keyStore.getEntry(KEY_ALIAS, null) as? KeyStore.SecretKeyEntry
        if (existing != null) return existing.secretKey

        val generator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, PROVIDER)
        generator.init(
            KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
            )
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setRandomizedEncryptionRequired(true)
                .build(),
        )
        return generator.generateKey()
    }

    private companion object {
        const val PROVIDER = "AndroidKeyStore"
        const val KEY_ALIAS = "alician_publish_token"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val TAG_BITS = 128
        const val PREFERENCES = "alician_publish"
        const val KEY_CIPHERTEXT = "token_ciphertext"
        const val KEY_IV = "token_iv"
        const val KEY_MASK = "token_mask"
        const val KEY_VERIFIED_AT = "token_verified_at"
        const val KEY_APP_REFRESH = "app_refresh_ciphertext"
        const val KEY_APP_REFRESH_IV = "app_refresh_iv"
        const val KEY_APP_CLIENT_ID = "app_client_id"
        const val KEY_APP_REFRESH_EXPIRES = "app_refresh_expires_at"
        const val KEY_ACCESS = "app_access_ciphertext"
        const val KEY_ACCESS_IV = "app_access_iv"
        const val KEY_ACCESS_EXPIRES = "app_access_expires_at"
    }
}
