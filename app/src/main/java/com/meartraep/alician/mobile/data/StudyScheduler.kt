package com.meartraep.alician.mobile.data

import kotlin.math.roundToLong

data class StudySchedulerConfig(
    val learningStepsMillis: List<Long> = listOf(60_000L, 10 * 60_000L),
    val relearningStepsMillis: List<Long> = listOf(10 * 60_000L),
    val graduatingIntervalDays: Int = 1,
    val easyIntervalDays: Int = 4,
    val hardMultiplier: Double = 1.2,
    val easyBonus: Double = 1.3,
    val lapseMultiplier: Double = 0.2,
    val initialEaseFactor: Double = 2.5,
    val againEasePenalty: Double = 0.2,
    val hardEasePenalty: Double = 0.15,
    val easyEaseBonus: Double = 0.15,
    val minimumEaseFactor: Double = 1.3,
    val maximumEaseFactor: Double = 3.0,
    val maximumIntervalDays: Int = 36_500,
) {
    init {
        requireValidSteps("learningStepsMillis", learningStepsMillis)
        requireValidSteps("relearningStepsMillis", relearningStepsMillis)
        require(graduatingIntervalDays > 0)
        require(easyIntervalDays >= graduatingIntervalDays)
        require(hardMultiplier >= 1.0 && hardMultiplier.isFinite())
        require(easyBonus >= 1.0 && easyBonus.isFinite())
        require(lapseMultiplier in 0.0..1.0 && lapseMultiplier.isFinite())
        require(initialEaseFactor.isFinite())
        require(againEasePenalty >= 0.0 && againEasePenalty.isFinite())
        require(hardEasePenalty >= 0.0 && hardEasePenalty.isFinite())
        require(easyEaseBonus >= 0.0 && easyEaseBonus.isFinite())
        require(minimumEaseFactor > 0.0 && minimumEaseFactor.isFinite())
        require(maximumEaseFactor >= minimumEaseFactor && maximumEaseFactor.isFinite())
        require(initialEaseFactor in minimumEaseFactor..maximumEaseFactor)
        require(maximumIntervalDays >= easyIntervalDays)
    }

    private fun requireValidSteps(name: String, steps: List<Long>) {
        require(steps.isNotEmpty()) { "$name must not be empty" }
        require(steps.all { it > 0L }) { "$name must contain only positive delays" }
        require(steps.zipWithNext().all { (first, second) -> first <= second }) {
            "$name must be ordered from shortest to longest"
        }
    }
}

/**
 * A deterministic, dependency-free spaced-repetition scheduler based on a simplified SM-2.
 *
 * Learning uses short fixed steps. Graduated cards use an ease factor, while a failed review
 * enters a short relearning step and reduces both ease and the previous interval. All due dates
 * are calculated from the supplied review time, so callers can test the scheduler without a
 * clock or Android dependency.
 */
class StudyScheduler(
    private val config: StudySchedulerConfig = StudySchedulerConfig(),
) {
    fun schedule(
        progress: StudyProgress,
        rating: StudyRating,
        reviewedAtEpochMillis: Long,
    ): StudyProgress {
        require(reviewedAtEpochMillis >= 0L) { "reviewedAtEpochMillis must not be negative" }

        val normalized = normalize(progress)
        val scheduled = when (normalized.phase) {
            StudyPhase.LEARNING -> scheduleLearning(normalized, rating, reviewedAtEpochMillis)
            StudyPhase.REVIEW -> scheduleReview(normalized, rating, reviewedAtEpochMillis)
            StudyPhase.RELEARNING -> scheduleRelearning(normalized, rating, reviewedAtEpochMillis)
        }
        return scheduled.copy(
            reviewCount = increment(normalized.reviewCount),
            lastReviewedAtEpochMillis = reviewedAtEpochMillis,
            lastRating = rating,
        )
    }

    fun preview(
        progress: StudyProgress,
        reviewedAtEpochMillis: Long,
    ): List<StudyRatingPreview> = StudyRating.entries.map { rating ->
        val next = schedule(progress, rating, reviewedAtEpochMillis)
        StudyRatingPreview(
            rating = rating,
            nextPhase = next.phase,
            dueAtEpochMillis = next.dueAtEpochMillis,
            intervalMillis = next.dueAtEpochMillis - reviewedAtEpochMillis,
            intervalDays = next.intervalDays,
        )
    }

    private fun scheduleLearning(
        progress: StudyProgress,
        rating: StudyRating,
        now: Long,
    ): StudyProgress = when (rating) {
        StudyRating.AGAIN -> progress.copy(
            phase = StudyPhase.LEARNING,
            dueAtEpochMillis = dueAt(now, config.learningStepsMillis.first()),
            intervalDays = 0,
            stepIndex = 0,
            repetitions = 0,
        )

        StudyRating.HARD -> progress.copy(
            dueAtEpochMillis = dueAt(
                now,
                hardStepDelay(config.learningStepsMillis, progress.stepIndex),
            ),
            intervalDays = 0,
        )

        StudyRating.GOOD -> advanceStepOrGraduate(
            progress = progress,
            steps = config.learningStepsMillis,
            graduatingDays = config.graduatingIntervalDays,
            now = now,
        )

        StudyRating.EASY -> graduate(
            progress = progress,
            intervalDays = config.easyIntervalDays,
            easeFactor = adjustEase(progress.easeFactor, config.easyEaseBonus),
            now = now,
        )
    }

    private fun scheduleReview(
        progress: StudyProgress,
        rating: StudyRating,
        now: Long,
    ): StudyProgress {
        val currentInterval = progress.intervalDays.coerceAtLeast(1)
        return when (rating) {
            StudyRating.AGAIN -> progress.copy(
                phase = StudyPhase.RELEARNING,
                dueAtEpochMillis = dueAt(now, config.relearningStepsMillis.first()),
                intervalDays = scaledInterval(currentInterval, config.lapseMultiplier),
                easeFactor = adjustEase(progress.easeFactor, -config.againEasePenalty),
                stepIndex = 0,
                repetitions = 0,
                lapses = increment(progress.lapses),
            )

            StudyRating.HARD -> continueReview(
                progress = progress,
                intervalDays = growingInterval(currentInterval, config.hardMultiplier),
                easeFactor = adjustEase(progress.easeFactor, -config.hardEasePenalty),
                now = now,
            )

            StudyRating.GOOD -> continueReview(
                progress = progress,
                intervalDays = growingInterval(currentInterval, progress.easeFactor),
                easeFactor = progress.easeFactor,
                now = now,
            )

            StudyRating.EASY -> continueReview(
                progress = progress,
                intervalDays = growingInterval(
                    currentInterval,
                    progress.easeFactor * config.easyBonus,
                ),
                easeFactor = adjustEase(progress.easeFactor, config.easyEaseBonus),
                now = now,
            )
        }
    }

    private fun scheduleRelearning(
        progress: StudyProgress,
        rating: StudyRating,
        now: Long,
    ): StudyProgress = when (rating) {
        StudyRating.AGAIN -> progress.copy(
            dueAtEpochMillis = dueAt(now, config.relearningStepsMillis.first()),
            stepIndex = 0,
            repetitions = 0,
        )

        StudyRating.HARD -> progress.copy(
            dueAtEpochMillis = dueAt(
                now,
                hardStepDelay(config.relearningStepsMillis, progress.stepIndex),
            ),
        )

        StudyRating.GOOD -> advanceStepOrGraduate(
            progress = progress,
            steps = config.relearningStepsMillis,
            graduatingDays = progress.intervalDays.coerceAtLeast(1),
            now = now,
        )

        StudyRating.EASY -> graduate(
            progress = progress,
            intervalDays = growingInterval(progress.intervalDays.coerceAtLeast(1), config.easyBonus),
            easeFactor = adjustEase(progress.easeFactor, config.easyEaseBonus),
            now = now,
        )
    }

    private fun advanceStepOrGraduate(
        progress: StudyProgress,
        steps: List<Long>,
        graduatingDays: Int,
        now: Long,
    ): StudyProgress {
        val nextStep = progress.stepIndex + 1
        return if (nextStep < steps.size) {
            progress.copy(
                dueAtEpochMillis = dueAt(now, steps[nextStep]),
                stepIndex = nextStep,
            )
        } else {
            graduate(progress, graduatingDays, progress.easeFactor, now)
        }
    }

    private fun graduate(
        progress: StudyProgress,
        intervalDays: Int,
        easeFactor: Double,
        now: Long,
    ): StudyProgress {
        val clampedInterval = intervalDays.coerceIn(1, config.maximumIntervalDays)
        return progress.copy(
            phase = StudyPhase.REVIEW,
            dueAtEpochMillis = dueAt(now, daysToMillis(clampedInterval)),
            intervalDays = clampedInterval,
            easeFactor = easeFactor,
            stepIndex = 0,
            repetitions = increment(progress.repetitions),
        )
    }

    private fun continueReview(
        progress: StudyProgress,
        intervalDays: Int,
        easeFactor: Double,
        now: Long,
    ): StudyProgress = progress.copy(
        phase = StudyPhase.REVIEW,
        dueAtEpochMillis = dueAt(now, daysToMillis(intervalDays)),
        intervalDays = intervalDays,
        easeFactor = easeFactor,
        stepIndex = 0,
        repetitions = increment(progress.repetitions),
    )

    private fun normalize(progress: StudyProgress): StudyProgress {
        val steps = when (progress.phase) {
            StudyPhase.LEARNING -> config.learningStepsMillis
            StudyPhase.RELEARNING -> config.relearningStepsMillis
            StudyPhase.REVIEW -> null
        }
        val stepIndex = steps?.let { progress.stepIndex.coerceIn(0, it.lastIndex) } ?: 0
        val ease = if (progress.easeFactor.isFinite()) {
            progress.easeFactor.coerceIn(config.minimumEaseFactor, config.maximumEaseFactor)
        } else {
            config.initialEaseFactor
        }
        return progress.copy(
            intervalDays = progress.intervalDays.coerceIn(0, config.maximumIntervalDays),
            easeFactor = ease,
            stepIndex = stepIndex,
            repetitions = progress.repetitions.coerceAtLeast(0),
            lapses = progress.lapses.coerceAtLeast(0),
            reviewCount = progress.reviewCount.coerceAtLeast(0),
        )
    }

    private fun hardStepDelay(steps: List<Long>, stepIndex: Int): Long {
        val current = steps[stepIndex]
        val next = steps.getOrNull(stepIndex + 1)
        return if (next != null) {
            current + (next - current) / 2L
        } else {
            scaledDelay(current, HARD_STEP_MULTIPLIER)
        }
    }

    private fun growingInterval(currentDays: Int, multiplier: Double): Int {
        val current = currentDays.coerceIn(1, config.maximumIntervalDays)
        val atLeastOneDayLonger = (current + 1).coerceAtMost(config.maximumIntervalDays)
        return maxOf(atLeastOneDayLonger, scaledInterval(current, multiplier))
    }

    private fun scaledInterval(currentDays: Int, multiplier: Double): Int {
        val scaled = currentDays.toDouble() * multiplier
        val rounded = if (scaled.isFinite()) scaled.roundToLong() else Long.MAX_VALUE
        return rounded.coerceIn(1L, config.maximumIntervalDays.toLong()).toInt()
    }

    private fun adjustEase(easeFactor: Double, adjustment: Double): Double =
        (easeFactor + adjustment).coerceIn(
            config.minimumEaseFactor,
            config.maximumEaseFactor,
        )

    private fun daysToMillis(days: Int): Long = days.toLong() * DAY_MILLIS

    private fun dueAt(now: Long, delayMillis: Long): Long =
        if (now > Long.MAX_VALUE - delayMillis) Long.MAX_VALUE else now + delayMillis

    private fun scaledDelay(delayMillis: Long, multiplier: Double): Long {
        val scaled = delayMillis.toDouble() * multiplier
        return if (!scaled.isFinite() || scaled >= Long.MAX_VALUE.toDouble()) {
            Long.MAX_VALUE
        } else {
            scaled.roundToLong().coerceAtLeast(1L)
        }
    }

    private fun increment(value: Int): Int =
        if (value == Int.MAX_VALUE) Int.MAX_VALUE else value + 1

    private companion object {
        const val DAY_MILLIS = 24L * 60L * 60L * 1_000L
        const val HARD_STEP_MULTIPLIER = 1.5
    }
}
