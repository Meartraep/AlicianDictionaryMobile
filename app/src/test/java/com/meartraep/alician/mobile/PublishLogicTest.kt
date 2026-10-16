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
}
