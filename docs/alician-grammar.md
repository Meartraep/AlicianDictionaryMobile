# 爱丽丝语（Alician）语法总结

> **来源**：本总结由翻译器（`app/src/main/python/webui_backend/`）的翻译规则与内置语料库（`app/src/main/assets/translated.db`）提炼而成。
>
> **证据分级**：
> - **【语料实证】**：在 `sentence_alignments`（对齐语料，1188 条精确对齐句）或词典 `no_class` 表中明确记载
> - **【代码规则】**：翻译器代码中实现的确定性规则（来自上述实证的归纳）
> - **【统计倾向】**：来自歌词语料的统计规律，非强制规则
>
> **检验方式**：可在 App 的"翻译器"中双向输入例句验证（爱丽丝语 ↔ 中文）。

---

## 1. 书写与词类系统

| 词类 | 缩写 | 词典数量 |
|---|---|---|
| 名词 | n. | 610 |
| 动词 | v. | 402（另 vi./vt. 各 2） |
| 形容词 | adj. | 246 |
| 副词 | adv. | 105 |
| 介词 | prep. | 37 |
| 感叹词 | interj. | 25 |
| 连词 | conj. | 25 |
| 代词 | pron. | 20 |
| 数词 | num. | 6 |
| 冠词 | art. | 1 |

书写规则：单词由字母组成，可含连字符与撇号（`A-Za-z'-`），分词符为空格。中文标点与省略号等按书写习惯保留（`？`、`！`、`，`、`。`、`……`）。

---

## 2. 词法（形态变化）

### 2.1 名词复数：后缀 `qls`【语料实证】

> no_class 表记载：*"qls：用在单数名词后，变为复数名词。也常作为后缀"*（count=11）

- 后置形式：`Ene qls` → 人们；`Saray qls` → 朋友们
- 连写后缀形式：`Syeillaqls` → 天使们；`Sarayqls` → 朋友们
- 连写时词干与 `qls` 不可分开拆译

补充：词典还标注了一批 `-s` 复数变体（`Syeillas` 天使们、`Enes` 人们、`Haols` 双手、`Storys` 故事、`Venesenes` 幽灵等），属于已固化词条而非能产规则。【语料实证】

### 2.2 形容词 → 副词：后缀 `lait`【语料实证】

> no_class 表记载：*"lait：后缀，形容词变副词，也可分开写"*

- 连写：`Moutlait` → 美好地（`Mout` 美好 + `lait`）
- 分开写：`Shelim lait` → 寂静地
- 中文侧对应："美好地" → `Moutlait`

### 2.3 动词否定前缀 `Dis-`【语料实证】

- 词典记载 Dis 除名词同形词外，明确标注"动词前表否定"，且可作前缀连写
- `Dis Harie` → 不记得；`Disharie` → 不记得

### 2.4 词形片段识别（no_class 构词关系）

no_class 表可把词标记为"某完整词的一部分"（如 `X 的一部分`）或"同 X"。翻译器据此做**词块重组**：
- 分裂书写的片段按构词关系合并回完整词再查词（`_merge_fragmented_alician_parts`）【代码规则】
- 片段单独出现时借用完整词含义，不把片段视为独立同义词【代码规则】

---

## 3. 语法功能词表【语料实证 + 代码规则】

以下词均有词典/语料明示的语法功能，翻译时按功能解析而非直译元数据：

| 功能词 | 功能 | 中文对应 | 例句（语料） |
|---|---|---|---|
| `Nai` | 通用否定 | 不 / 没 / 无 / 别（按语境） | `Bis o Nai Hellm` → 这不是幻觉！ |
| `Yien` | 动词前被动标记 | 被 | `Yien Harie Ord Mii` → 被我记得 |
| `Ord` | 被动施事者 / 工具 | 被… / 用… | `Yien Amiy Ord Lusia` → 被光明关爱 |
| `ol` | 过去/现在完成体 | 已 | `Ollenes ob Inay` → 我们已经等待了许久 |
| `ob` | 过去完成体 | 已经 | 同上 |
| `a Laiz` | 将来时（动词后） | 将 | `Mii Dist a Laiz Crai` → 我将忘记你 |
| `Laiz` | 未来标记 | 将 / 即将 | `Vell Laiz` → 将… |
| `ou` | 领属标记 | 的 | `Disverry ou Crai` → 你的魔法 |
| `Phier` | 祈使/礼貌 | 请 / 吧 | `Phier Harie` → 请记得 |
| `Yiela` | 祈使句引导（来） | 来…吧 | `Yiela Brait Tri Ran qls` → 来睁开三只眼睛吧 |
| `Yiep` | 祈使句引导（请） | 请…吧 | `Yiep Qleea Tigilijk Falke` → 请快崩塌吧 |
| `Lqll` | 相似（后置） | 像…一样 | `Syeilla Lqll` → 像天使一样 |
| `Qleea` | 将来/即将 | 将会 / 即将 | `Quim Qleea Miz Elza` → 假如即将变成羽翼 |
| `end` | 关系从句/连接 | （结构词） | `Syeilla end Mii Harie` → 我记得的天使 |
| `ra` | 宾语从句引导 | （结构词） | 19 条标注为从句引导 |
| `iy` | 系词/话题标记 | 是 | `Bis iy ...` → 这是… |
| `a` / `es` | 并列连接 | 和 / 并 | `Mii a Crai` → 我和你 |
| `Poutie` | 时间/条件/伴随 | 当 / 如果 / 随着 | `Poutie Mii Clooshe Eist` → 当我关闭门 |
| `Imeila` | 让步 | 即使 | `Imeila Zia Qleea Verse` → 即使我消失 |
| `imm` | 处所 | 在 | `Aihel imm Bis` → 自由在这 |
| `arch` / `arche` | 环绕：在…上 / 到…上 | 在 / 到 | `Tollm Arch Fenklu` → 流在脸庞上 |
| `lim` / `alfloul` / `pllia` / `uleim` | 环绕：下 / 周围 / 前 / 深处 | 在…下等 | — |
| `forle` / `winde` | 从句后置"之前" | 在…之前 | `forle Sai Elay` → 在清晨到来之前 |
| `folme` | 来源介词 | 从 | — |
| `lid` / `elied` | 处所 / 时间边界 | 在 / 直到 | — |
| `tozlom` / `ijlim` | 时间从句 | 当 | — |
| `mols` / `osa` / `baly` | 焦点副词 | 只 / 也 / 总是 | `Shelista Skelat Mii Baly` → 世界总是嘲笑我 |
| `Og Amiy` | 互惠 | 彼此 | `Qllsiim Og Amiy` → 我们彼此爱 |
| `lend` / `erikes` | 是非问标记 | 是否 | `Lend Cloud Skeem...` → 是否开始新游戏？ |
| `crain` | 句末反问 | 不是吗？ | `Heip Crain` → …不是吗？ |
| `fevla` | 疑问 | 为什么 | `Fevla Crai Qleea Endekta Bai` → 你为什么不承认 |
| `phim` | 道义情态 | 应该 | `Phim Felia` → 应该忍耐 |
| `foul` | 强调 | 一定 | — |
| `vell` | 未来 | 将 | — |
| `quim` | 条件 | 假如 | — |
| `bai` | 句末语气 | （语气词） | — |
| `iqyur` | 敬称标记 | （不译） | — |
| `en`/`ta`/`sii`/`sip`/`wei`/`weiy`/`dou`/`endil` | 轻语义语气词 | （不译） | `Mii endil Crai` → 我你 |
| `iequim` (+Lef) | 相似/仿佛 | 像 / 仿佛 | `Iequim Lef Mono` → 像无色… |

---

## 4. 句法（语序与结构）

### 4.1 基本语序

**默认语序为 SVO（主-谓-宾）**，但语料中大量出现 VOS、SOV 等诗歌化变体；翻译器按**语料句式模式**（`sentence_patterns`，每首歌至多计一次）决定是否重排，并保证不交换主语/宾语语义角色。【代码规则 + 统计倾向】

中文 → 爱丽丝语时按 SVO 模板输出：`主语 + 修饰语 + 动词 + 宾语 + 将来标记 + 方式状语`。【代码规则】

### 4.2 领属结构：head-ou-possessor【语料实证】

领属是**中心语在前、`ou`、领属者在后**：

- `Disverry ou Crai` → 你的魔法（字面"魔法 的 你"）
- `Ween ou Myte Hellm` → 我的梦的尽头（嵌套链整体反转：`Ween ou Hellm ou Mii` 结构）
- `Brai ou Pocket` → 那口袋中

中文"的"在爱丽丝语中按修饰语词性三分【代码规则】：
| 中文结构 | 爱丽丝语处理 | 示例 |
|---|---|---|
| 名词/代词领属（X 的 Y） | `Y ou X`（head-ou-possessor） | 我的心 → `Myte Herz`（封闭领属形容词） |
| 形容词定语（A 的 N） | `A N`，直接前置，"的"不译 | 美好的梦 → `Mout Hellm` |
| 动词关系从句（V 的 N） | `N end V...`（head-end-relative） | 我记得的天使 → `Syeilla end Mii Harie` |

代词领属优先使用**封闭所有格形容词**：`Myte`(我的) `Crait`(你的) `Fiete`(他的) `Zillyte`(我们的) `Blemyte`(谁的)。【语料实证】

### 4.3 被动结构：Yien-V-Ord-agent【语料实证】

被动为 **`Yien` + 动词 + `Ord` + 施事者**：

- `Yien Harie Ord Mii` → 被我记得
- `Flea end ol Yien Amiy Ord Lusia` → 被光明关爱的人
- 中文"被 A V" → 爱丽丝语 `Yien V Ord A`

**否定被动**中否定词置于 `Yien` 前（`Nai Yien V` → 不被 V）。【代码规则】

### 4.4 关系从句：head-end-clause【语料实证】

从句后置、以 `end` 引出，译为中文时整段提前到中心语之前并加"的"：

- `Syeilla end Mii Harie` → 我记得的天使
- `Ene end Yien Amiy Ord Lusia` → 被光明爱的人

### 4.5 将来时：动词 + a + Laiz【语料实证】

> no_class 记载：*"动词 + a Laiz 变为将来时"*

- `Mii Dist a Laiz Crai` → 我将忘记你
- 中文"我将V你" → `Mii V a Laiz Crai`；`a` 与 `Laiz` 作为整体生成，不可拆分

### 4.6 完成体：ol / ob【语料实证】

- `ol`：过去/现在完成（已）；`ob`：过去完成（已经）
- `Ollenes ob Inay` → 我们已经等待了许久
- 与将来标记共存时按语境抑制冲突形式（如 `ol Qleea` → 已经，不输出"已将会"）【代码规则】

### 4.7 祈使句：Yiela / Yiep … 吧【语料实证】

- 作用域为**整个后续分句**，句末只生成一个"吧"（不产生"请…吧…吧"）
- `Yiela Brait Tri Ran qls` → 来睁开三只眼睛吧
- `Yiep Qleea Tigilijk Falke` → 请快崩塌吧
- `Phier` 可作简单祈使/礼貌：`Phier Harie` → 请记得
- `Yiela` + 显式主语 → "让…吧"（如"让我们…"）【代码规则】

### 4.8 疑问句【代码规则】

- 是非问：`Lend` / `Erkes` 置句首 → 中文"是否…？"
- 句末反问：`Crain` → "…不是吗？"
- 特殊疑问：`Fevla`（为什么）

### 4.9 否定系统【代码规则】

`Nai` 根据被否定成分的语法家族选择中文形式：

| 语境 | 中文否定 |
|---|---|
| 情态/系词后 | 不能 / 不会 / 不是… |
| 存在/拥有（`Aihel`/`Dilem`） | 没 / 没有 |
| 动词/形容词/副词前 | 不 |
| 名词/代词前 | 无 |
| 名词后（后置否定） | 没有（中文前置） |
| 祈使语境 | 别 |
| 强调语境（`Foul` 等） | 绝不 |

例：`Nai ou Finz Hait` → 无结局的自由；`Crai Nai Anisia Bai` → 我们不会再寂寞了。

### 4.10 相似结构：后置 Lqll【语料实证】

`Lqll` 恒在句末/被比对象后（对齐语料中全部为后置）：

- `Syeilla Lqll` → 像天使一样
- 中文"像 X 一样" → `X Lqll`（`Lqll` 保持后置）

### 4.11 处所环绕结构【代码规则】

处所介词常为**环缀**（首部 + 尾部）：
- `Arch X` → 在 X 上；`Arche X` → 到 X 上
- `Lim X` → 在 X 下；`Alfloul` / `Pllia` / `Uleim` 同理
- 中文生成时补齐后置方位词（上/下/前/深处），如 `Tollm Arch Fenklu` → 流在脸庞上

### 4.12 时间/条件/伴随从句【代码规则】

`Poutie` 依据相邻结构解析为：当（时间）/ 如果（条件）/ 随着（伴随）/ 正如（比较）。`Quim`(假如) `Noa`(之时) `Imeila`(即使) 等为从句标记。

### 4.13 副词位置【统计倾向】

副词位置来自歌词语料统计（`adverb_position_stats`），非强制规则：
- 多数副词倾向**句中**（紧邻谓词）：`Ail` 句中 77%、`Aola` 83%、`Mols` 81%
- `Bai` 倾向句末（64%）；部分副词句首/句中/句末均可

### 4.14 省略与"不译"成分

- 轻语义语气词（`en`、`ta`、`sii`、`wei`、`dou`、`endil`、`iqyur`、`ra` 等）**不输出译文**，仅作句法结构【代码规则】
- 词典中"疑为""(?)""(pl.)"等**编辑性元数据**绝不出现在译文表面【代码规则】

---

## 5. 中文分词与词块匹配（中文 → 爱丽丝语）

- 中文先由 jieba 拆成词块，再逐块查词典（v1.7.0 起：无法匹配的词块会**自动细分为更小词块**重新匹配，如"讲故事"→"讲"+"故事"，仅"讲"标红）【代码规则】
- 词典将中文释义索引为候选词（`term_candidates`），精确命中优先
- 可选 AI 语义别名（`dictionary_semantic_aliases`）用于近似匹配，精确词典释义仍优先【代码规则】

---

## 6. 供检验的对照表（双向翻译样例）

| 中文 | 爱丽丝语 | 语法点 |
|---|---|---|
| 我的心 | `Myte Herz` | 封闭领属形容词 |
| 我的梦的尽头 | `Ween ou Myte Hellm` | 嵌套领属 head-ou |
| 我记得的天使 | `Syeilla end Mii Harie` | 关系从句 head-end |
| 我被你记得 | `Mii Yien Harie Ord Crai` | 被动 Yien-V-Ord |
| 我将忘记你 | `Mii Dist a Laiz Crai` | 将来时 a Laiz |
| 像天使一样 | `Syeilla Lqll` | 后置相似 |
| 来睁开三只眼睛吧 | `Yiela Brait Tri Ran qls` | 祈使 + 复数 |
| 我们彼此相爱 | `Qllsiim Og Amiy` | 互惠结构 |
| 世界总是嘲笑我 | `Shelista Skelat Mii Baly` | 副词语序 |
| 请快崩塌吧 | `Yiep Qleea Tigilijk Falke` | 祈使 + 即将 |
| 美好的梦 | `Mout Hellm` | 形容词定语前置 |
| 不记得 / 你 | `Disharie` / `Craill` | 否定前缀 / 你 |

---

## 7. 主要证据来源

- **翻译规则代码**：`app/src/main/python/webui_backend/`
  - `translation_alician.py`、`translation_alician_syntax.py`（爱丽丝语 → 中文）
  - `translation_chinese_lexicon.py`、`translation_chinese_grammar.py`（中文 → 爱丽丝语）
  - `translation_data.py`（词典 / no_class / 语料加载）、`translation_common.py`（共用规则）
- **语料库**：`app/src/main/assets/translated.db`
  - `no_class`：语法功能与形态规则记载
  - `sentence_alignments`：1188 条精确中爱对齐句
  - `adverb_position_stats`：副词位置统计
  - `songs`：歌词语料（句式模式来源）
