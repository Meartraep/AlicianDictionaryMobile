"""Scratch: verify the post-migration dictionary state across all three tables."""
import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DB = r"c:\Users\meart\Desktop\AlicianDictionaryMobile\app\src\main\assets\translated.db"
con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row

EXPECT = {
    "Qllsiim": ("我们", "pron."),
    "Qllsiimtiel": ("我们自己", "pron."),
    "Xianya": ("他们", "pron."),
    "Salah": ("阴影", "n."),
    "Rinasia": ("诞生", "v."),
    "Loosya": ("连", "adj."),
    "ob": ("持续", "v."),
    "Coll": ("身躯", "n."),
    "tie": ("在", "prep."),
    "Mail": ("披上", "v."),
}
ok = True
for word, (gloss, cls) in EXPECT.items():
    senses = con.execute(
        "SELECT explanation, class FROM dictionary WHERE lower(words)=lower(?) ORDER BY sense_order",
        (word,),
    ).fetchall()
    hw = con.execute(
        "SELECT display_explanation, display_class FROM dictionary_headwords WHERE lower(words)=lower(?)",
        (word,),
    ).fetchone()
    first = senses[0]["explanation"] if senses else None
    first_cls = senses[0]["class"] if senses else None
    doubt = any("(?)" in str(s["explanation"]) for s in senses)
    good = first == gloss and first_cls == cls and not doubt and hw is not None
    ok &= good
    print(f"  {'OK ' if good else 'BAD'} {word:<12} senses={[s['explanation'] for s in senses]}"
          f" class={first_cls} | headword={hw['display_explanation']!r}/{hw['display_class']}")
    # per-class table
    import sqlite3 as _s
    for t in ("pron.", "n.", "v.", "adj.", "prep."):
        try:
            rows = con.execute(f"SELECT translation FROM `{t}` WHERE lower(words)=lower(?)", (word,)).fetchall()
        except sqlite3.OperationalError:
            continue
        if rows:
            print(f"        [{t}] {[r['translation'] for r in rows]}")

print("\nSalah 水面 residual:", con.execute(
    "SELECT words, explanation FROM dictionary WHERE explanation LIKE '%水面%'").fetchall().__len__(),
      [(r["words"], r["explanation"]) for r in con.execute(
          "SELECT words, explanation FROM dictionary WHERE explanation LIKE '%水面%'")])
print("整体:", "全部通过" if ok else "存在不一致")
con.close()
