# 词典检索与词条编辑数据契约

本文件定义「词典」模块对外的数据契约：`dictionary_search`、`dictionary_song_lyrics`、
`dictionary_update_word`、`dictionary_update_lyric` 的载荷/响应形状与写入规则。
手机端（Kotlin）与 Python 后端各自实现的一半必须同时满足本契约；
`app/src/test/python/test_dictionary_search.py` 是真库回归测试，条款编号与本文一一对应。

改动本契约 = 同时改 Python、Kotlin、测试三处，并在 PR 说明里写明迁移影响。

---

## §0 原则

违反 §0 的改动一律视为阻塞缺陷，优先级高于任何功能。

### §0.1 义项保全

一个 headword 的每个义项（`dictionary` 表的每一行）都是独立数据。
编辑必须按义项 `dictionary.id` 逐条提交，**未提交的义项必须字节不变**
（`explanation` / `english_gloss` / `japanese_gloss` / `class` / `sense_order` / `count` / `variety`）。
禁止 `UPDATE dictionary ... WHERE headword_id = ?` 批量覆盖释义。

### §0.2 词头唯一性

`dictionary_headwords.words` 没有 UNIQUE 约束，因此重命名必须由写路径做校验：
目标拼写与另一个 headword（不同 `id`）不区分大小写相同时拒绝，返回中文原因，且不写入任何行。
改名成功后，该 headword 下所有义项的 `dictionary.words` 必须同步为新拼写，其余列不变。

### §0.3 事务卫生

所有写操作必须自行保证「连接不在事务内」后再 `BEGIN IMMEDIATE`；
失败必须 `rollback`，不得把 `cannot start a transaction within a transaction` 或
`database is locked` 原文抛给用户。失败返回值必须是中文 `message`。

---

## §1 `dictionary_search`

请求：`{query: string, exact: bool, position: string, record_history?: bool}`（`record_history` 缺省 `true`）。

响应顶层字段（不得删减）：`ok`、`query`、`exact_match`、`is_phrase`、`sections`、
`history`、`message`、`suggestions`、`context_examples`、`features`；
每个 section 必须有 `title` / `kind` / `entries`。

### §1.1 词条 section（`kind = alice` / `chinese`）

在既有字段（`word`/`explanation`/`word_class`/`kind`/`count`/`variety`/
`english_gloss`/`japanese_gloss`）之外，必须携带：

- `headword_id`：`dictionary_headwords.id`
- `senses`：数组，按 `sense_order` 升序；每项
  `{id: dictionary.id, explanation, class, english_gloss, japanese_gloss}`；可为空数组

`senses` 是词条编辑器的唯一数据来源；缺了它，编辑就只能退化成「写整词」＝§0.1 违规。

### §1.2 歌词英/日译命中 section（`kind = translation`）

- 触发条件：`len(query) >= 3` 或 `exact == true`
- 上限：**20 条**
- entry 必须携带：`word`（alician 句）、`explanation`（中文译文）、`word_class = 歌词句子`、
  `english_gloss`、`japanese_gloss`、`song_title`、`album`
- 拉丁单 token 查询按**整词**匹配（`love` 不匹配 `loveless`，`GLOB` 边界匹配）
- 歌词句必须能追溯到歌曲（§1.2 的 `song_title`/`album`），否则结果不可用

### §1.3 歌曲标题 section（`kind = song`）

- 触发条件：`len(query) >= 2` 或 `exact == true`
- 上限：**20 条**
- entry：`word = title`、`explanation = album`、`word_class = 歌曲`、`album`

### §1.4 历史

`record_history == false` 时不得写查询历史；其余行为与 `true` 完全一致
（编辑后的重查使用 `false`，重命名不算一次查询）。

---

## §2 `dictionary_song_lyrics`

请求：`{title, album}`。响应与 `dictionary_examples` **同形**（`ExampleResult`）：

- 成功：`ok = true`，`examples` 恰好 1 条，`paragraph` 与 `lyric` 都是全文，
  `start = 0`、`end = len(lyric)`，`poetic_translation`/`english_translation`/
  `japanese_translation`/`korean_translation` 为空串（逐句译文在 `lyric_translations` 里）
- `lyric_translations` 来自 `sentence_alignments`（LEFT JOIN `song_translations`），
  每项 `{line, poetic, english, japanese, korean}`
- 找不到歌曲：`ok = false` + `message = "未找到这首歌。"` + 空 `examples`
  （Kotlin `requireOk()` 会把它转成错误提示，因此不得返回空数组的 `ok: true`）

---

## §3 `dictionary_update_word`

请求：

```json
{
  "headword_id": 388,
  "original_word": "Finz",
  "word": "Finz",
  "display_explanation": "结局，终末 v. 结束 adj. 终末的",
  "senses": [
    {"id": 448, "explanation": "结局", "english": "end/to end", "japanese": "終わり/終わる"}
  ]
}
```

响应：`{ok: true, message: "词条已保存。", headword_id, word}`；
失败：`{ok: false, message: "<中文原因>"}`。

规则（全部强制）：

1. `headword_id` 必须存在，否则 `"未找到要修改的词条。"`
2. `word` trim 后非空、≤ 64 字符、不含换行；`display_explanation` 非空、≤ 500 字符
3. 每个提交义项的 `explanation` 非空、≤ 500 字符；`id` 必须属于该 headword，
   否则 `"义项数据不一致，请刷新后重试。"`
4. 未提交的义项不写（§0.1）；`class`/`sense_order`/`count`/`variety` 永不写
5. `english` / `japanese` 键缺省 = 保持原值（不得静默清空）；显式空串 = 清空。
   同时接受 `english_gloss` / `japanese_gloss` 作为别名键
6. 改名走 §0.2 唯一性校验；成功后 `dictionary.words` 全义项同步
7. 单事务提交（`BEGIN IMMEDIATE`）；失败 `rollback` 并返回中文原因
8. 成功后的 Kotlin 侧副作用：重放上一次搜索（`record_history = false`，沿用
   exact/position）、刷新历史与数据库信息、刷新学习牌组

---

## §4 `dictionary_update_lyric`

请求/响应不变。新增约束：目标歌曲不存在时 `update_song_lyric` 必须 `rollback`，
不得把共享连接留在事务里（这是 §0.3 违规的历史根因）。

---

## §5 更新检查与「本地修改」

- `up_to_date` 以库内 `database_metadata.db_version` 为主判据；两侧 marker 都存在时
  `local >= remote` 即最新（本地编辑只改字节、不改版本号，不得因此永久提示"有更新"）
- marker 缺失时回退到 `sha1` 比较
- 返回 `local_modified`：`local_version == remote_version && local_sha != remote_sha`

## §6 性能与噪声基线（回归门）

- 单次 `search()` 在 2.85 MB 真库上本地目标 < 20 ms；`translation`/`song` section 各 ≤ 20 条
- `search("a")` 不得出现 `translation` section；`search("the")` 的 payload 不得出现
  100 条级卡片墙（历史上是 160 张卡片 / 43 KB，现为 30 张 / 12.5 KB 量级）
- 编辑一次词条不应引发全库多轮重载：翻译器缓存只在成功且命中
  `dictionary`/`phrase`/`songs` 等表时重建一次

---

## §7 验收清单（测试条款编号）

| 编号 | 条款 | 测试 |
|---|---|---|
| §7.1.1 | `search("Alice")` 命中歌曲 section 且 entry 带 `album` | `SearchSectionTests` |
| §7.1.2 | `search("world")` 命中英/日译 section 且带 `song_title`/`album` | 同上 |
| §7.1.3 | 最小长度门控与 20 条上限（`a`/`in`/`the`） | 同上 |
| §7.1.4 | `record_history=False` 不写历史 | `HistoryTests` |
| §7.1.5 | 真歌整首歌词 + 真实逐句译文 | `SongLyricsTests` |
| §7.1.6 | 不存在的歌返回 `ok == False` | 同上 |
| §7.1.7 | 只改提交义项，其余义项字节不变 | `UpdateWordEntryTests` |
| §7.1.8 | 重命名撞词被拒且不新增重复 headword | 同上 |
| §7.1.9 | 非法载荷被拒且数据不变 | 同上 |
| §7.1.10 | 失败歌词写后下一次词条写可正常开事务 | `TransactionRecoveryTests` |

另有 `ShippedSchemaTests` 守住真库结构与体积（`songs.title` UNIQUE、`dictionary` 主键/
NOT NULL/FK、行数量级），防止测试退化成假 schema 自证。

运行：

```powershell
cd app/src/test/python
$env:PYTHONPATH = '<repo>/app/src/main/python'
python -m unittest test_dictionary_search -v
```
