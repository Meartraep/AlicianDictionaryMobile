package com.meartraep.alician.mobile.data

import java.text.Normalizer
import java.util.Locale
import kotlin.random.Random

internal fun stableItemId(scope: StudyScope, text: String): String =
    "${scope.name}:${Normalizer.normalize(text.trim(), Normalizer.Form.NFC).lowercase(Locale.ROOT)}"

internal fun mergeStudyItems(items: List<StudyItem>): List<StudyItem> =
    items.groupBy(StudyItem::id).values.map { variants ->
        val first = variants.first()
        first.copy(
            explanation = variants.map(StudyItem::explanation)
                .distinct()
                .joinToString("；"),
            wordClass = variants.map(StudyItem::wordClass)
                .filter(String::isNotBlank)
                .distinct()
                .joinToString(" / "),
            frequency = variants.maxOf(StudyItem::frequency),
            variety = variants.maxOf(StudyItem::variety),
        )
    }

internal fun orderStudyItems(
    items: List<StudyItem>,
    order: StudyOrder,
    randomSeed: Long,
): List<StudyItem> = when (order) {
    // Breadth is deliberately the first key: a repeated chorus should not outrank a word
    // which appears across many different lyrics merely because its raw count is large.
    StudyOrder.FREQUENCY -> items.sortedWith(
        compareByDescending<StudyItem>(StudyItem::variety)
            .thenByDescending(StudyItem::frequency)
            .thenBy { it.text.lowercase(Locale.ROOT) }
            .thenBy(StudyItem::id),
    )
    StudyOrder.ALPHABETICAL -> items.sortedWith(
        compareBy<StudyItem> { it.text.lowercase(Locale.ROOT) }
            .thenBy(StudyItem::text)
            .thenBy(StudyItem::id),
    )
    StudyOrder.RANDOM -> items.shuffled(Random(randomSeed))
}
