# 官方译词逐句对齐修复（song_translations realignment）

**问题**：翻译器里显示的官方日译/英译与爱丽丝语原句、中文翻译没有逐句对齐。
相邻的 A、B 两句共享同一个“段落块”，于是 A 的翻译里含 B 的内容，B 的翻译里也含 A 的内容
（共 102 个块 / 222 行）。

**根因**：`scripts/import_alicianlabs.py` 以 alicianlabs 的**空行分段（段落）**为单位取
`english_lyrics` / `japanese_lyrics`，而 app 的爱丽丝语歌词是**逐句**的，一段常含 2 句。
被匹配到同一段落的每一句都拿到了整段译文。

## 修复流程（按顺序执行）

```bash
# 1) 基础导入（会重建 song_translations，注意它本身带有上述缺陷）
python scripts/import_alicianlabs.py
python scripts/import_korean.py

# 2) 逐句重排（本目录）
python scripts/realign/assemble.py          # 生成 newpos.json（逐位置） / newmap.json（逐句）
python scripts/realign/write_db.py          # 试运行
python scripts/realign/write_db.py --apply  # 写库（自动备份到 backups/）
```

## 组成

| 文件 | 作用 |
| --- | --- |
| `extract.py` → `extract.json` | 导出 DB 对齐表 + alicianlabs 原文到 JSON |
| `source_fix.py` | 修正上游源文件的已知缺陷（见下） |
| `align_engine.py` | 爱丽丝语逐词模糊（NW）对齐，得到“句子 ↔ 源段落/行”的单调映射 |
| `map_v4.py` | 由 NW 映射 + 内容覆盖率决定每句所属段落；支持重复段落、跨段句 |
| `overrides.py` | 人工核对的少量归属例外 |
| `decisions.json` | **逐段切分决策**（按原子数或显式文本），149 个多句段落全部人工过目 |
| `assemble.py` | 按决策切分段落译文并回填到每一句，含“切分片段必须能拼回原文”的强校验 |
| `write_db.py` | 写回 `song_translations`（每句一行，重复句取首次出现） |
| `changed_rows.txt` | 全部改动行的 old → new 对照（人工校对记录） |
| `review_en_batch_*.json` | 独立子代理对 52 首歌逐段做的官方英/日对齐复核结论 |

## 上游源文件缺陷（已在 `source_fix.py` 修正）

1. **Alice_Music**：`english_lyrics` 在 “Turning the hands of clock…” 处多了一个空行，
   导致第 15 段起英文整体错位一段（S21 的英文行缺失，实测如此）。
2. **killed_by_angel**：英文第 3、4 行与日文/爱丽丝语顺序相反（S02/S03 互换）。
3. **Wanderers**：英文把一句话拆到了 S21/S22/S23 三段，按日文段落边界复原。
4. **Fehlt**：源文件含 `<br>` 残留标记，已清除。

## 校验

* `assemble.py` 会校验每个段落的切分片段能逐字拼回原文（含空白归一化对比），当前 0 报错。
* `final_check.py`：走 app 的真实查询路径（`dictionary_core.find_song_alignments`），
  统计相邻行重复。修复前 222 行共享段落块，修复后仅剩 1 处（Apocalypse 的咒语段，
  官方日文只给出一遍，属客观情况）。
* `python -m unittest test_attested_grammar test_chinese_composition`（64 项）通过。

## 已知取舍

* 52 首源曲中有 12 首**没有官方英译**（`english_lyrics` 为空），这些行英文留空；
  其中 2 首（FEHLT、Maharajah 等）仅日文可对齐。
* 同曲内重复出现的同一句爱丽丝语在 `song_translations` 中只能存一行
  （`UNIQUE(song_title, sentence)`），12 处重复句的不同措辞取首次出现，差异均为
  个别词/拼写（如 `I'll` vs `I' ll`）。
* 官方译文内部语序与爱丽丝语不同时（如 Hypnotized S18 的英文从句后置），
  英文片段按日文/中文语序重排，以保证逐句对应。
* 3 个 app 曲目（FEHLT(DEEMO edition)、Maharajah fenomeno edition、
  フライブルクとエンドロウル(Extended ver.)）在源仓库中没有对应曲目，未生成译词。
