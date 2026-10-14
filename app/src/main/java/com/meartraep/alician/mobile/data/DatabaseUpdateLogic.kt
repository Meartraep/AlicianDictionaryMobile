package com.meartraep.alician.mobile.data

import java.util.Locale

/**
 * Pure decision logic behind the startup "is there a newer database?" check.
 *
 * Revisions come from two places: the installed database publishes its own
 * revision through `database_metadata` (see [PythonRepository.databaseVersion]),
 * and the published `database-manifest.json` announces the newest one. Databases
 * shipped before the marker existed report [UNKNOWN_DATABASE_VERSION], so the
 * first versioned release is offered to them.
 */
object DatabaseUpdateLogic {
    /** Revision reported by a database that carries no marker at all. */
    const val UNKNOWN_DATABASE_VERSION = 0

    /** Version recorded after the user chooses "later"; nothing is deferred yet. */
    const val NO_DISMISSED_VERSION = -1

    fun isNewer(remoteVersion: Int, localVersion: Int): Boolean = remoteVersion > localVersion

    /**
     * True when the update should interrupt the user: the published revision is
     * newer than the installed one and the user has not already deferred exactly
     * that revision. A later release prompts again.
     */
    fun shouldPrompt(
        localVersion: Int,
        remoteVersion: Int,
        dismissedVersion: Int,
    ): Boolean = isNewer(remoteVersion, localVersion) && remoteVersion > dismissedVersion

    fun formatSize(bytes: Long): String = when {
        bytes >= 1024L * 1024L -> String.format(Locale.US, "%.1f MB", bytes / 1024.0 / 1024.0)
        bytes >= 1024L -> String.format(Locale.US, "%.0f KB", bytes / 1024.0)
        else -> bytes.toString() + " B"
    }

    /** One-line description shown in the update prompt. */
    fun summary(localVersion: Int, manifest: DatabaseUpdateManifest): String {
        val size = if (manifest.size > 0L) "，约 " + formatSize(manifest.size) else ""
        return "本地数据库 v" + localVersion + "，云端已发布 v" + manifest.dbVersion + size
    }
}
