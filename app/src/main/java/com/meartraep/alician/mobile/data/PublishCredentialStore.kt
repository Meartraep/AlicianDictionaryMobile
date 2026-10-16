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
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.ENCRYPT_MODE, secretKey())
        val ciphertext = cipher.doFinal(token.toByteArray(Charsets.UTF_8))
        preferences.edit {
            putString(KEY_CIPHERTEXT, Base64.encodeToString(ciphertext, Base64.NO_WRAP))
            putString(KEY_IV, Base64.encodeToString(cipher.iv, Base64.NO_WRAP))
            putString(KEY_MASK, PublishLogic.maskToken(token))
            putLong(KEY_VERIFIED_AT, System.currentTimeMillis())
        }
    }

    /** Returns null when nothing is stored or the Keystore key no longer decrypts. */
    fun load(): String? {
        val ciphertext = preferences.getString(KEY_CIPHERTEXT, null) ?: return null
        val iv = preferences.getString(KEY_IV, null) ?: return null
        return try {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(
                Cipher.DECRYPT_MODE,
                secretKey(),
                GCMParameterSpec(TAG_BITS, Base64.decode(iv, Base64.NO_WRAP)),
            )
            String(cipher.doFinal(Base64.decode(ciphertext, Base64.NO_WRAP)), Charsets.UTF_8)
        } catch (error: Exception) {
            // Key invalidated (for example after a device credential change): the
            // stored secret is unusable, so drop it instead of keeping a broken entry.
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
    }
}
