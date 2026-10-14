package com.meartraep.alician.mobile

import com.meartraep.alician.mobile.data.DatabaseUpdateLogic
import com.meartraep.alician.mobile.data.DatabaseUpdateManifest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DatabaseUpdateLogicTest {
    private val manifest = DatabaseUpdateManifest(
        dbVersion = 3,
        publishedAt = "2026-10-14",
        notes = "逐句对齐",
        size = 2_854_912L,
        sha1 = "5f5cb1389bae746327ce385b2f5b7d6c010aff82",
        url = "https://example.invalid/translated.db",
    )

    @Test
    fun legacyDatabaseWithoutMarkerIsOfferedTheFirstVersionedRelease() {
        assertTrue(
            DatabaseUpdateLogic.shouldPrompt(
                localVersion = DatabaseUpdateLogic.UNKNOWN_DATABASE_VERSION,
                remoteVersion = 1,
                dismissedVersion = DatabaseUpdateLogic.NO_DISMISSED_VERSION,
            ),
        )
    }

    @Test
    fun sameRevisionIsNotOffered() {
        assertFalse(DatabaseUpdateLogic.shouldPrompt(localVersion = 3, remoteVersion = 3, dismissedVersion = -1))
    }

    @Test
    fun olderRemoteRevisionIsNotOffered() {
        assertFalse(DatabaseUpdateLogic.shouldPrompt(localVersion = 4, remoteVersion = 3, dismissedVersion = -1))
    }

    @Test
    fun deferredRevisionStaysQuietUntilANewerOneAppears() {
        assertFalse(DatabaseUpdateLogic.shouldPrompt(localVersion = 1, remoteVersion = 3, dismissedVersion = 3))
        assertTrue(DatabaseUpdateLogic.shouldPrompt(localVersion = 1, remoteVersion = 4, dismissedVersion = 3))
    }

    @Test
    fun installingTheDeferredRevisionAlsoSilencesThePrompt() {
        assertFalse(DatabaseUpdateLogic.shouldPrompt(localVersion = 3, remoteVersion = 3, dismissedVersion = 3))
    }

    @Test
    fun sizeIsRenderedWithReadableUnits() {
        assertEquals("2.7 MB", DatabaseUpdateLogic.formatSize(2_854_912L))
        assertEquals("512 KB", DatabaseUpdateLogic.formatSize(524_288L))
        assertEquals("800 B", DatabaseUpdateLogic.formatSize(800L))
    }

    @Test
    fun summaryNamesBothRevisionsAndTheDownloadSize() {
        val text = DatabaseUpdateLogic.summary(localVersion = 1, manifest = manifest)
        assertTrue(text, text.contains("v1"))
        assertTrue(text, text.contains("v3"))
        assertTrue(text, text.contains("2.7 MB"))
    }

    @Test
    fun summaryOmitsSizeWhenTheManifestDoesNotPublishOne() {
        val text = DatabaseUpdateLogic.summary(localVersion = 0, manifest = manifest.copy(size = 0L))
        assertFalse(text, text.contains("MB"))
    }
}
