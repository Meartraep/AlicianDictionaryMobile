# -*- coding: utf-8 -*-
"""Manual assignment overrides verified against the source stanzas."""

# (song, app_index) -> stanza index (or None = no official line exists)
ASSIGN_OVERRIDE = {
    # Snooze: the app lyric repeats "HamilSlay" after the alarm-clock line;
    # those two rows belong to the same stanza as "Staps Termz end Ran Hise".
    ('Sno (_ _) oze & Sn (o_o) ze', 6): 8,
    ('Sno (_ _) oze & Sn (o_o) ze', 7): 8,
    ('Sno (_ _) oze & Sn (o_o) ze', 15): 8,
    ('Sno (_ _) oze & Sn (o_o) ze', 16): 8,
    # Snooze: second "a Story Olis Flute" of the pair belongs to the repeat stanza.
    ('Sno (_ _) oze & Sn (o_o) ze', 10): 6,
    # The White Land: the repeat block of the app lyric was matched to the first
    # occurrence by the fallback; anchor it to the repeat stanzas instead.
    ('The White Land', 30): 9,
    ('The White Land', 31): 10,
    ('The White Land', 32): 10,
    ('The White Land', 33): 11,
    ('The White Land', 39): 14,
    # Forbidden Wonderland: "La La La La La" has no counterpart in the official lyric.
    ('Forbidden Wonderland short ver', 3): None,
}
