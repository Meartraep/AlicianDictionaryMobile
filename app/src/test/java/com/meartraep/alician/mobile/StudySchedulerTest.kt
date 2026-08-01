package com.meartraep.alician.mobile

import com.meartraep.alician.mobile.data.StudyContent
import com.meartraep.alician.mobile.data.StudyOrder
import com.meartraep.alician.mobile.data.StudyPhase
import com.meartraep.alician.mobile.data.StudyProgress
import com.meartraep.alician.mobile.data.StudyRating
import com.meartraep.alician.mobile.data.StudyScheduler
import com.meartraep.alician.mobile.data.StudySchedulerConfig
import com.meartraep.alician.mobile.data.StudySettings
import org.junit.Assert.assertEquals
import org.junit.Assert.assertThrows
import org.junit.Test

class StudySchedulerTest {
    private val scheduler = StudyScheduler()

    @Test
    fun studySettingsDefaultToFrequencyAndAllContent() {
        val settings = StudySettings()

        assertEquals(StudyOrder.FREQUENCY, settings.order)
        assertEquals(StudyContent.ALL, settings.content)
        assertEquals(10, settings.dailyNewLimit)
        assertEquals(false, settings.alphabetCompleted)
    }

    @Test
    fun previewShowsEveryRatingWithoutMutatingTheCard() {
        val now = 1_000_000L
        val progress = StudyProgress(itemId = "WORD:end")

        val previews = scheduler.preview(progress, now).associateBy { it.rating }

        assertEquals(StudyRating.entries.toSet(), previews.keys)
        assertEquals(60_000L, previews.getValue(StudyRating.AGAIN).intervalMillis)
        assertEquals(330_000L, previews.getValue(StudyRating.HARD).intervalMillis)
        assertEquals(600_000L, previews.getValue(StudyRating.GOOD).intervalMillis)
        assertEquals(4 * DAY_MILLIS, previews.getValue(StudyRating.EASY).intervalMillis)
        assertEquals(StudyPhase.LEARNING, progress.phase)
        assertEquals(0, progress.reviewCount)
        assertEquals(null, progress.lastRating)
    }

    @Test
    fun goodAdvancesLearningStepsThenGraduates() {
        val now = 10_000L
        val first = scheduler.schedule(
            StudyProgress(itemId = "WORD:end"),
            StudyRating.GOOD,
            now,
        )

        assertEquals(StudyPhase.LEARNING, first.phase)
        assertEquals(1, first.stepIndex)
        assertEquals(now + 10 * MINUTE_MILLIS, first.dueAtEpochMillis)
        assertEquals(1, first.reviewCount)

        val graduated = scheduler.schedule(first, StudyRating.GOOD, now + 10 * MINUTE_MILLIS)

        assertEquals(StudyPhase.REVIEW, graduated.phase)
        assertEquals(1, graduated.intervalDays)
        assertEquals(now + 10 * MINUTE_MILLIS + DAY_MILLIS, graduated.dueAtEpochMillis)
        assertEquals(1, graduated.repetitions)
        assertEquals(2, graduated.reviewCount)
    }

    @Test
    fun easyGraduatesNewCardWithLongerIntervalAndHigherEase() {
        val next = scheduler.schedule(
            StudyProgress(itemId = "PHRASE:Poul ail"),
            StudyRating.EASY,
            reviewedAtEpochMillis = 0L,
        )

        assertEquals(StudyPhase.REVIEW, next.phase)
        assertEquals(4, next.intervalDays)
        assertEquals(4 * DAY_MILLIS, next.dueAtEpochMillis)
        assertEquals(2.65, next.easeFactor, 0.000_001)
    }

    @Test
    fun reviewRatingsApplySimplifiedSm2Intervals() {
        val progress = StudyProgress(
            itemId = "WORD:end",
            phase = StudyPhase.REVIEW,
            intervalDays = 10,
            easeFactor = 2.5,
            repetitions = 3,
        )

        val again = scheduler.schedule(progress, StudyRating.AGAIN, 0L)
        assertEquals(StudyPhase.RELEARNING, again.phase)
        assertEquals(2, again.intervalDays)
        assertEquals(10 * MINUTE_MILLIS, again.dueAtEpochMillis)
        assertEquals(2.3, again.easeFactor, 0.000_001)
        assertEquals(1, again.lapses)
        assertEquals(0, again.repetitions)

        val hard = scheduler.schedule(progress, StudyRating.HARD, 0L)
        assertEquals(12, hard.intervalDays)
        assertEquals(2.35, hard.easeFactor, 0.000_001)

        val good = scheduler.schedule(progress, StudyRating.GOOD, 0L)
        assertEquals(25, good.intervalDays)
        assertEquals(2.5, good.easeFactor, 0.000_001)

        val easy = scheduler.schedule(progress, StudyRating.EASY, 0L)
        assertEquals(33, easy.intervalDays)
        assertEquals(2.65, easy.easeFactor, 0.000_001)
    }

    @Test
    fun relearningGoodReturnsCardToItsReducedReviewInterval() {
        val lapsed = StudyProgress(
            itemId = "WORD:end",
            phase = StudyPhase.RELEARNING,
            intervalDays = 6,
            easeFactor = 2.1,
            stepIndex = 0,
            lapses = 2,
        )

        val next = scheduler.schedule(lapsed, StudyRating.GOOD, 5_000L)

        assertEquals(StudyPhase.REVIEW, next.phase)
        assertEquals(6, next.intervalDays)
        assertEquals(5_000L + 6 * DAY_MILLIS, next.dueAtEpochMillis)
        assertEquals(2, next.lapses)
        assertEquals(1, next.repetitions)
    }

    @Test
    fun schedulerClampsCorruptStateAndConfiguredLimits() {
        val configured = StudyScheduler(
            StudySchedulerConfig(maximumIntervalDays = 30, easyIntervalDays = 4),
        )
        val progress = StudyProgress(
            itemId = "WORD:end",
            phase = StudyPhase.REVIEW,
            intervalDays = Int.MAX_VALUE,
            easeFactor = Double.NaN,
            stepIndex = Int.MAX_VALUE,
            repetitions = -4,
            lapses = -2,
            reviewCount = -1,
        )

        val next = configured.schedule(progress, StudyRating.GOOD, 0L)

        assertEquals(30, next.intervalDays)
        assertEquals(30 * DAY_MILLIS, next.dueAtEpochMillis)
        assertEquals(2.5, next.easeFactor, 0.000_001)
        assertEquals(0, next.stepIndex)
        assertEquals(1, next.repetitions)
        assertEquals(0, next.lapses)
        assertEquals(1, next.reviewCount)
    }

    @Test
    fun invalidConfigAndNegativeReviewTimeAreRejected() {
        assertThrows(IllegalArgumentException::class.java) {
            StudySchedulerConfig(learningStepsMillis = emptyList())
        }
        assertThrows(IllegalArgumentException::class.java) {
            scheduler.schedule(
                StudyProgress(itemId = "WORD:end"),
                StudyRating.GOOD,
                -1L,
            )
        }
    }

    private companion object {
        const val MINUTE_MILLIS = 60_000L
        const val DAY_MILLIS = 24L * 60L * MINUTE_MILLIS
    }
}
