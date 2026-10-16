package com.meartraep.alician.mobile

import com.meartraep.alician.mobile.data.PublishLogic
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PublishLogicTest {
    @Test
    fun branchNameCarriesUtcTimestampAndPrefix() {
        val name = PublishLogic.branchName(1_763_000_000_000L)
        assertTrue(name, name.startsWith(PublishLogic.BRANCH_PREFIX))
        // Formatted in UTC so two phones in different time zones never collide.
        assertEquals("db-publish/20251113-021320", name)
        assertTrue(name, Regex("db-publish/[0-9]{8}-[0-9]{6}").matches(name))
    }

    @Test
    fun tokenIsMaskedWithoutLeakingTheBody() {
        val masked = PublishLogic.maskToken("github_pat_11ABCDEFG0123456789")
        assertFalse(masked, masked.contains("CDEFG0123456789"))
        assertTrue(masked, masked.startsWith("github_"))
        assertEquals("****", PublishLogic.maskToken("short"))
    }

    @Test
    fun notesAreCollapsedAndCapped() {
        assertEquals("第一行 第二行", PublishLogic.normalizeNotes("  第一行\n第二行  "))
        assertEquals("", PublishLogic.normalizeNotes("   "))
        val long = "x".repeat(PublishLogic.NOTES_LIMIT + 50)
        assertEquals(PublishLogic.NOTES_LIMIT, PublishLogic.normalizeNotes(long).length)
    }

    @Test
    fun oversizedDatabaseIsRejected() {
        assertNull(PublishLogic.validateDatabaseSize(3L * 1024 * 1024))
        assertNotNull(PublishLogic.validateDatabaseSize(PublishLogic.MAX_DATABASE_BYTES + 1))
        assertNotNull(PublishLogic.validateDatabaseSize(0L))
        val warning = PublishLogic.validateDatabaseSize(PublishLogic.WARN_DATABASE_BYTES + 1)
        assertNotNull(warning)
        assertTrue(warning.orEmpty(), warning.orEmpty().contains("流量"))
    }

    @Test
    fun unchangedDatabaseIsBlockedBeforeUploading() {
        val preview = PublishLogic.buildPreview(
            localVersion = 1,
            localSize = 2_854_912L,
            localSha1 = "5f5cb1389bae746327ce385b2f5b7d6c010aff82",
            publishedVersion = 1,
            publishedSha1 = "5F5CB1389BAE746327CE385B2F5B7D6C010AFF82",
        )
        assertFalse(preview.hasChanges)
        assertNotNull(preview.blockingReason)
        assertTrue(preview.blockingReason.orEmpty(), preview.blockingReason.orEmpty().contains("完全相同"))
    }

    @Test
    fun changedDatabaseIsPublishable() {
        val preview = PublishLogic.buildPreview(
            localVersion = 1,
            localSize = 2_900_000L,
            localSha1 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            publishedVersion = 1,
            publishedSha1 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        )
        assertTrue(preview.hasChanges)
        assertNull(preview.blockingReason)
        assertTrue(PublishLogic.pullRequestTitle(preview).startsWith("数据库发布："))
    }

    @Test
    fun missingManifestBlocksTheFlow() {
        val preview = PublishLogic.buildPreview(
            localVersion = 0,
            localSize = 2_900_000L,
            localSha1 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            publishedVersion = 0,
            publishedSha1 = "",
        )
        assertFalse(preview.hasChanges)
        assertTrue(preview.blockingReason.orEmpty(), preview.blockingReason.orEmpty().contains("联网"))
    }

    @Test
    fun pullRequestBodyFallsBackToADefaultNote() {
        assertEquals("由手机端上传的数据库更新。", PublishLogic.pullRequestBody("   "))
        assertEquals("修正三条译词", PublishLogic.pullRequestBody(" 修正三条译词 "))
    }

    @Test
    fun signatureMessageMatchesTheServerSideFormat() {
        // The same fixture is pinned in test_publication_signature.py: both
        // implementations must produce identical bytes.
        val message = PublishLogic.buildSignatureMessage(
            previousVersion = 1,
            previousSha1 = "5F5CB1389BAE746327CE385B2F5B7D6C010AFF82",
            version = 2,
            sha1 = "c98419801d2c1e9d6f6c4a4f4d3b0f1e2a3b4c5d",
            size = 2859008L,
            publishedAt = "2026-10-17",
            notes = "手机端发布",
        )
        // Literal from the Python side (hashlib.sha256 of the UTF-8 note), so a
        // difference in encoding or hashing between the two implementations fails here.
        assertEquals("3e1153ffe833bd6785b8bd0d733283d89f0ffa5d2ba7229f45f55863debbe930", PublishLogic.notesSha256("手机端发布"))
        assertEquals(
            "alician-db-publish-v1\n" +
                "prev_version=1\n" +
                "prev_sha1=5f5cb1389bae746327ce385b2f5b7d6c010aff82\n" +
                "version=2\n" +
                "sha1=c98419801d2c1e9d6f6c4a4f4d3b0f1e2a3b4c5d\n" +
                "size=2859008\n" +
                "published_at=2026-10-17\n" +
                "notes_sha256=" + PublishLogic.notesSha256("手机端发布") + "\n",
            message,
        )
    }

    @Test
    fun signatureDocumentIsTheJsonTheServerParses() {
        val document = PublishLogic.signatureDocument("ab12cd34ef56ab78", "MEUCIQ==")
        assertTrue(document, document.startsWith("{"))
        assertTrue(document, document.contains("\"algorithm\": \"ECDSA-P256-SHA256\""))
        assertTrue(document, document.contains("\"key_id\": \"ab12cd34ef56ab78\""))
        assertTrue(document, document.contains("\"signature\": \"MEUCIQ==\""))
    }
}
