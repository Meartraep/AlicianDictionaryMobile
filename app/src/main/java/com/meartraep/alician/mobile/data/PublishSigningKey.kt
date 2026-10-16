package com.meartraep.alician.mobile.data

import android.app.KeyguardManager
import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.core.content.edit
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.KeyStore
import java.security.MessageDigest
import java.security.Signature
import java.security.spec.ECGenParameterSpec

/**
 * The device key that authorises a database publication.
 *
 * The private half is generated inside the Android Keystore and can never be
 * exported, so a stolen GitHub token alone cannot publish anything: CI only accepts
 * a publication signed by the key whose public half is registered on main.
 *
 * When the device has a secure lock screen the key additionally requires the user
 * to authenticate before it can sign, which also protects against someone using an
 * unlocked phone.
 */
class PublishSigningKey(context: Context) {
    private val preferences =
        context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
    private val keyguard =
        context.getSystemService(Context.KEYGUARD_SERVICE) as KeyguardManager

    val deviceIsSecure: Boolean get() = keyguard.isDeviceSecure

    val exists: Boolean get() = loadKeyPair() != null

    /** True when signing needs a fresh device authentication. */
    val requiresAuthentication: Boolean
        get() = preferences.getBoolean(KEY_REQUIRES_AUTH, false)

    /** Fingerprint of the public key; CI compares it with the registered key. */
    val keyId: String?
        get() = loadKeyPair()?.let { fingerprint(it) }

    fun publicKeyPem(): String? = loadKeyPair()?.let { pair ->
        val encoded = Base64.encodeToString(pair.public.encoded, Base64.NO_WRAP)
        buildString {
            append("-----BEGIN PUBLIC KEY-----\n")
            encoded.chunked(64).forEach { line -> append(line).append('\n') }
            append("-----END PUBLIC KEY-----\n")
        }
    }

    /** Creates the key pair (or replaces an existing one) and returns its public key. */
    fun create(): String {
        val keyStore = KeyStore.getInstance(PROVIDER).apply { load(null) }
        if (keyStore.containsAlias(ALIAS)) {
            keyStore.deleteEntry(ALIAS)
        }
        val generator = KeyPairGenerator.getInstance(KeyProperties.KEY_ALGORITHM_EC, PROVIDER)
        val builder = KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_SIGN)
            .setAlgorithmParameterSpec(ECGenParameterSpec("secp256r1"))
            .setDigests(KeyProperties.DIGEST_SHA256)
        val boundToUser = deviceIsSecure
        if (boundToUser) {
            @Suppress("DEPRECATION")
            builder.setUserAuthenticationRequired(true)
                .setUserAuthenticationValidityDurationSeconds(AUTH_VALIDITY_SECONDS)
        }
        generator.initialize(builder.build())
        generator.generateKeyPair()
        preferences.edit {
            putBoolean(KEY_REQUIRES_AUTH, boundToUser)
            putLong(KEY_CREATED_AT, System.currentTimeMillis())
        }
        return publicKeyPem().orEmpty()
    }

    /** ECDSA/SHA-256 signature (DER, base64) over the publication message. */
    fun sign(message: String): String {
        val pair = loadKeyPair() ?: throw IllegalStateException("尚未生成发布签名密钥。")
        val signature = Signature.getInstance("SHA256withECDSA")
        signature.initSign(pair.private)
        signature.update(message.toByteArray(Charsets.UTF_8))
        return Base64.encodeToString(signature.sign(), Base64.NO_WRAP)
    }

    fun clear() {
        val keyStore = KeyStore.getInstance(PROVIDER).apply { load(null) }
        runCatching { keyStore.deleteEntry(ALIAS) }
        preferences.edit { clear() }
    }

    private fun loadKeyPair(): KeyPair? {
        val keyStore = KeyStore.getInstance(PROVIDER).apply { load(null) }
        val entry = keyStore.getEntry(ALIAS, null) as? KeyStore.PrivateKeyEntry ?: return null
        return KeyPair(entry.certificate.publicKey, entry.privateKey)
    }

    private fun fingerprint(pair: KeyPair): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(pair.public.encoded)
        return digest.take(8).joinToString("") { byte -> "%02x".format(byte) }
    }

    private companion object {
        const val PROVIDER = "AndroidKeyStore"
        const val ALIAS = "alician_publish_signing"
        const val PREFERENCES = "alician_publish"
        const val KEY_REQUIRES_AUTH = "signing_requires_auth"
        const val KEY_CREATED_AT = "signing_created_at"
        const val AUTH_VALIDITY_SECONDS = 60
    }
}
