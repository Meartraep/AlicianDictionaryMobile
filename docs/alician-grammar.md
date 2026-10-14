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
| `end` | 关系从句 / 枚举 / 跨行延续 | （结构词；枚举时作"，"） | `Syeilla end Mii Harie` → 我记得的天使；`… Nols end ol Kllea end ol Sjiyupe` → …，忘却的事情，… |
| `Elize` | 原因从句引导｜= 日语 `から` | **因为**（词典正确） | `Elize Shelista Fur a Leimy Zill Baly`（日：世界はいつも僕らを見放す**から**）→ 因为世界总是抛弃我们 |
| `Gout` | 转折 | 但是 / 不过 | `Gout Mii Lootaria end Loog` → 我却永远无法飞离此处 |
| `Poetklar` | 同时/伴随动作｜= 日语 `ながら` | **一边…**（非"正在"） | `Poetklar Myte Herz Yien Torjest Mii`（日：打ちひしがれ**ながら**）→ 我的心一边被杀 |
| `Zel` | 疑问词｜= 日语 `何` + 助词 | 何 / 什么 / 任何 | `Kulu Nai Ranya Zel Note`（日：何も見えない）→ 不能看见任何事物 |
| `ifa` | 伴随/工具｜= 日语 `と` / `で` | 和… / 用… | `… ifa Bis a Xia Haol`（日：この手**で**）→ 用这双手…（前置） |
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
- 位于**跨句/跨行边界**的 `end`、`Gout`（居首或居末、其后无实义词）同样是延续标记，不译（`Gout Mii Drone end` → 我却永远孤身一人）【语料实证】

### 4.15 工具/伴随短语前置【语料实证】

`Ord` 与 `ifa` 引出的名词短语在爱丽丝语中**后置于谓词**，译为中文时一律移到谓词之前：

| 爱丽丝语 | 中文 | 触发词 |
|---|---|---|
| `Poutie Mii Clooshe Eist Ord Ail Entic` | 当我用全部的力气关闭门 | `Ord`（工具） |
| `Olkemia Story ifa Bis a Xia Haol` | 用这双手改写故事 | `ifa`（工具/方式） |
| `Stea ifa Enbrikardi Fas` | 用恐怖的色彩描绘 | `ifa` |
| `Yien Stea ifa Enbrikardi Fas` | 被用恐怖的色彩描绘 | `ifa` + 被动，保持"被-用"序 |

- `ifa` 位于**分句之首**或其名词为**人称代词**时保持伴随义，不前置：`Ifa Anie ou Bip` → 伴随昆虫的气息
- 关系从句内部的工具短语同样先前置，再整体提前作定语

### 4.16 枚举 `end` 与标点策略【语料实证】

- `end` 作为**关系从句标记**时被构式消费（→"的"）；未被消费且后接**非名词性成分**的 `end` 属**枚举连接**，输出"**，**"：
  `Arupe Elled Nols end ol Kllea end ol Sjiyupe` → 古老的电梯，忘却的事情，哭泣受挫的日子
- **分句边界补逗号**：原因与转折连接词（`Elize`、`Gout`）位于句**中**时，其前补"，"；位于句首时不补：
  `Mill end Dikti Elize Olkemia Story ifa Bis a Xia Haol` → 我们不幸，因为用这双手改写故事
- 谓词层级并列（`a`/`es` 连接两个动词）在语料中读作停顿，中文亦可用"，"；名词层级并列仍作"和"

### 4.17 Elize = 因为（以官方日文为准的定论）【语料实证】

**方法论前提（重要）**：`sentence_alignments.chinese_translation` 是**社区维护的中文本地化（非官方）**，为求中文流畅常把"因/果"两个分句**互换**；它不能作为爱丽丝语连接词的判据。唯一的官方对照文本是 `song_translations` 表的 **`japanese`（官方日文歌词）与 `english`（官方英译）**。

**结论**：`Elize` 对应日语 **`から` / `だ+から`（原因）**，即在爱丽丝语中**前置**的"因为"。词典注"因为"**正确**。

| 爱丽丝语 | 官方日文 | 官方英文 | Elize ≈ |
|---|---|---|---|
| `Elize Shelista Fur a Leimy Zill Baly` | 世界はいつも 僕らを見放す**から** | The world has always abandoned us | から |
| `Oudiq Nai Hexixa Wondidda Elize Vig iy Nai Loosya Enebis Wetijka` | 最早 人ですらないの**だから** 痛みを推し測る必要もないだろう | — | だ+から |
| `Phim Felia Aola Mols Elize Elemie iy Apnesiaflea` | 痛みは付き物**だから** 今は我慢していてね | Pain always comes with it | だ+から |
| `Poet Dooom Anie Elize Mii Vell Kulu Ignai Fal …` | もう二度と 帰って来られないの**だから** | — | だ+から |
| `Xia iy Elize Zyte Herz iy Porsa Friud …` | 僕の心が おかしいだけなん**だから** | It's only because there's something wrong with my mind | だ+から |
| `… Elize Cloud Vell Nai Holt` | きっと 後悔しない**から**… | — | から |
| `Poetklar … Elize Mii Garve …` | このナイフで 数式を刻む**から** | — | から |
| `Foly Elize Vell Mins Lwei Foul` | そのうちきっと慣れてくる**から**大丈夫 | you'll get used to it | から |
| `Elize Zill Nai Nache Sis Poet Nai Eala il Rowt Koll` | 僕ら まだ遊び足りないん**だから** | we're not done playing | だ+から |

**量化**：23 条含 `Elize` 的官方对齐行中，**21 条**的日文以 `から` / `だ+から` / `のだから` 结尾（= "因为"）；仅 **3 条**（`だから` 作**行首接续词**，= "所以"）为例外。

**语序规律**：**紧接 `Elize` 之后的爱丽丝语分句，正是日语 `から` 所依附的那个分句**（原因分句）。见于全部 21 条例证，包括句首用例：

- `Elize` + `Shelista Fur a Leimy Zill Baly`（＝世界抛弃我们）↔ 世界はいつも僕らを見放す**から**
- `Elize` + `Kulu Dist Ail Poutie Eem Wondidda`（＝（痛时）能忘记一切）↔ 全てを忘れられる**から**
- `Elize` + `Tella a Belqua Ilis Fas`（＝倒入彩虹色）↔ 虹色を流し込む**から**

故中文生成取**"因为" + 后续分句**；句中以"，因为…"连接，句首直接起句（**"因为"完全可以起句**——此前"因为不能居句首"的说法有误）。

**反例（保留）**：`だから` 作**行首接续词**时义为"所以"：`Elize Crai Elie Luan …` ↔「**だから** ここから先は 一人で行った方がいいの」；`Mill end Dikti Elize Olkemia Story …` ↔「私たちは不幸だ **だから** 物語を書き換えるんだ」（英译 that's why）。日语 `だから` 本即 `だ + から`，故爱丽丝语用同一个 `Elize` 覆盖 `から` 的两种用法；以 21:3 计，默认取"因为"。

### 4.17.1 邻近词与同类功能的辨析【语料实证】

| 词 | 词典 | 官方日文对照 | 判定 |
|---|---|---|---|
| `Elize` | adv. 因为 | `Elize`+分句 ↔ `…から`（21/23） | **原因连接**（因为）｜= `から` |
| `Poetklar` | adv. 正在 / 与动词构成现在进行时 | 含 `ながら` 的 5 行**全部**含 `Poetklar`（5/5） | **同时动作**（一边…）｜= `ながら`，非进行体 |
| `ifa` | prep. 伴随着 | `ifa Bis a Xia Haol` ↔ この手**で**；`Ifa Anie ou Bip` ↔ 虫の息**で** | **伴随/工具**｜= `と` / `で` |
| `Zel` | n. (没有)任何(事物) | `Zel Note` ↔ 何**も**；`… Zel Veida …` ↔ 何匹目 | **疑问词**（何/什么）｜= `何` |
| `Endjulf` | adv. 因此 | `Endjulf …` ↔ そうして（in this way） | **方式回指**（那样/用这种方式），非因果 |
| `Oltemia` | conj. 因为(?) | `… Oltemia Baly` ↔ …無駄だよ いつだって… | 与"因为"共现，待定 |

### 4.17.2 系统规律：日语后置成分 → 爱丽丝语前置【语料实证】

上表暴露出一个稳定的类型学差异：日语的**后置语法成分**（接续助词、格助词）在爱丽丝语中一律**前置**于其所依附的成分：

| 日语（后置） | 爱丽丝语（前置） | 例 |
|---|---|---|
| `…から`（接续助词） | `Elize` + 分句 | 見放す**から** → `Elize Shelista …` |
| `…ながら`（接续助词） | `Poetklar` + 动词短语 | 打ちひしがれ**ながら** → `Poetklar … Torjest` |
| `NPすら / NPも`（副助词） | `Loosya` + NP（+ 后置「都」） | 意味**すら**嘲る → `Loosya Selti` → 连意义都 |
| `NPで` / `NPと`（格助词） | `ifa` + NP | この手**で** → `ifa Bis a Haol` |
| `NPに`（受身の動作主） | `Ord` + NP | 光明**に**愛される → `Yien Amiy Ord Lusia` |
| `NPの`（連体助詞） | 中心语 + `ou` + 领属者 | 魔法**の**あなた → `Disverry ou Crai` |

注：`ou` 是唯一**居中**的例子（head-`ou`-possessor），`Lqll`（＝`みたい`）则与日语一致保持后置，故该规律适用于**接续/格助词**一类，并非全部功能词。

### 4.17.3 全量功能词日文复核结果【语料实证】

复核方法：以 `song_translations.japanese` 为准，统计每个爱丽丝语功能词与其共现的日语标记（提升度 = P(标记|词) / P(标记)），并与 `dictionary.japanese_gloss`/`english_gloss` 对照。**词典的日/英注正是由官方歌词构建，优先级高于中文释义列。**

**复核确认正确（无需改动）**

| 爱丽丝语 | 词典 JP / EN | 语料共现（提升度） | 中文生成 |
|---|---|---|---|
| `folme` | から / from | から 20/22 **10.8×** | 从 |
| `gout` | だけど/でも / but | けれど 9/24 **26.7×**、でも 8/24 **15.4×** | 但是 |
| `foul` | きっと / surely | きっと 13/16 **39.6×** | 一定 |
| `mols` | だけ / only | だけ 8/13 **25.9×** | 只 |
| `baly` | いつだって / always | いつも 5/16 **36.2×** | 总是 |
| `quim` | なら / if | なら 4/7 **66.1×** | 假如 |
| `zel` | 何 / what | 何 13/16 **22.8×**、も 13/16 | 何/任何 |
| `ifa` | で / with | で 8/13 **3.3×**、と 6/13 | 伴随/用 |
| `il` | へ / to | へ 10/49 **5.2×** | 到 |
| `poutie` | と/なら / when,if | たら 3/14、ば 4/14（各≈12×） | 当/如果 |
| `yiela` | なさい / imperative | なさい 5/11 **42.1×** | 来…吧 |
| `phier` | お願い / please | ください 3/11 **84.2×** | 请 |
| `lishe` | ましょう | ましょう 7/22 **26.8×** | 让 |
| `hiele` | ほら / look! | ほら・ねえ 为主 | 看哪 |
| `lend` | か / interrogative | 疑问句（まえ…か） | 是否 |
| `erikes` | — | でしょうか / かな（推测疑问） | 是否 |
| `iequim` | みたい | よう 5/10、みたい 3/10 | 像…一样 |
| `rie` | やがて / eventually | や（やがて）10/14 **17.4×** | 不久/早晚 |
| `osa` | も | も 11/13 **4.1×** | 也 |
| `ol` | た / past | 产出"已…"均与日文过去形吻合 | 已 |
| `ob` | ていた / continuous past | 止まっていた、待ってた、眠っていた 全部吻合 | 已经 |
| `vell` | だろう | だろ 6/39 **8.9×**、きっと 4/39 | 将 |
| `laiz` | acts like だろう | だろ 4/18 **12.9×** | 将 |
| `nai` | 否定 | ない 83/112、なかった 11/112 | 不/没 |
| `ou` | の（逆序） | の 145/169 | 的 |

**复核修正或需注意**

| 爱丽丝语 | 词典 JP / EN | 原译法 | 修正后 | 依据 |
|---|---|---|---|---|
| `Elize` | だから / therefore,Because | 所以 | **因为** | 19/23 行日文以 `から`/`だ+から` 结尾，且 Elize 后分句即该 `から` 依附的原因分句 |
| `Poetklar` | ながら / while | 正在 | **一边** | 含 `ながら` 的 5 行 100% 含 Poetklar（185× 提升度） |
| `Qleea` | 〜てしまう / **completely** | 将会（prospective） | 保留"将会/即将/快/已经"语境消解 | 日文为 `てしまう`（完了・不可逆），现有语境机制产出正确（しまいそう→将会、しまえ→快、しまった→已经），仅**角色标签**不精确 |
| `ord` | as in 全〜 / by(something) | 用（仅施事/工具） | 待定 | 词典另注 `全〜`（"完全"）用法，语料尚无清晰例证 |
| `imeila` | ところで / despite | 即使 | 保留"即使" | 语料为 `ても`（即使），词典 JP 列此处疑似录入错误；EN `despite` 与 ても 一致 |
| `dis` | 魔法・二人 / 动词前否定 | 不（仅当前词为动词） | 正确（有守卫） | 词典前两义为名词"魔法/二人"，翻译器仅在后续为动词时才作否定前缀 |

**同向补充**：`因为` 与 `所以` 均映射到 `Elize`（日语 `だから` 的接续助词与接续词两种用法）；`因此` 保持映射到 `Endjulf`（＝そうして）。此前中文"所以"无对应词、会输出未解析标记，已修复。

### 4.18 Zel 的限定词用法【语料实证】

`Zel` = 日语 `何`（疑问/不定词），其后由 `Note`（もの/こと）等名词充当中心语。官方日文对照：

- `Kulu Nai Ranya end Kulu Nai Prifiel Zel Note` ↔ 何**も** 見えない 何**も** 判らない → 不能看见任何事物 / 什么也看不见
- `Melart Mii Nai Guit Zel Note` ↔ 私は何**も**知りません → 我什么也不知道
- `Voi Yien Holo Mane … Zel Note` ↔ 何**か**を想う事 → （想）某些事（肯定语境 → "某事"）

故 `Zel Note` 的中文随语境取**任何事物 / 什么（也）… / 某事**；`Zel` 单独出现（无名词中心语）时保留词典释义"没有任何事物"。

### 4.19 焦点助词 `Loosya`（日语 `すら` / `も`）与「连…都」框架【官方日英歌词实证】

**证据仅取自官方日/英歌词**（`song_translations.japanese` / `.english`）；中文列与词典词表一律不作证据（词典 `japanese_gloss`＝`すら`、`english_gloss`＝`every/even` 仅作旁证）。

`Loosya` 在全部官方歌词中只见于 **3 行**（词典 `count=4` 系 Urxbxrxs 该行在歌词中重复 2 次）：

| offid | 爱丽丝语 | 官方日文 | 官方英文 |
|---|---|---|---|
| 236 | `Oudiq Nai Hexixa Wondidda Elize Vig iy Nai **Loosya** Enebis Wetijka` | 『最早 **人ですらない**のだから 痛みを推し測る必要もないだろう』 | （空） |
| 631 | `**Loosya** Hewvews Liiquip iy …` | ナルシストな**独裁者も** 今は 無様に弄ばれる 惨めなピエロ | The narcissistic dictator is **nothing but** a pathetic clown now… |
| 865 | `… Qtua **Loosya** Selti` | そこは **意味すら**嘲る 合わせ鏡の迷路 | …a labyrinth of mirrors that mocks **even** every meaning |

**证明 1：排除法（以 offid=236 为决定性证据）**

日文分句「（お前は）**人** で **すら** ない」共 4 个语素；爱丽丝语分句 `Vig iy Nai Loosya Enebis` 共 5 个词。其余 4 个词均由**其它官方行**独立锚定：

| 爱丽丝语 | 官方锚点（其它行） | 对应日文 |
|---|---|---|
| `Vig` | offid=234「**お前**は頭の壊れた化け物だから」↔`…vig iy pefid…`；offid=1018「“**お前**は神からも見離されるんだ”」↔`vig yien fur…` | お前（你） |
| `iy` | offid=177「あなたの瞳**は**…心臓**は**ここ」↔`…tittri iy…herches iy…`；offid=195「君は独りじゃ**ない**」↔`crai **iy** nai drone` | は / です |
| `Nai` | offid=20「何も 見え**ない**」↔`kulu **nai** ranya`；offid=15「何も思い出せ**ない**」↔`kulu **nai** harie` | ない |
| `Enebis` | offid=411「**人**の皮を被ったハイエナ達」↔`…ou enebis…`；offid=1201「（**人間**のほうが…）」↔`…enebis iy…` | 人 / 人間 |

**4 个日文语素 ↔ 4 个非 Loosya 词一一对上，剩余唯一语素 `すら` 只剩 `Loosya` 可承载。** 即 `Loosya` = `すら`。

**证明 2：官方英文直证（offid=865）**

日文「意味**すら**嘲る」的官方英译写为 `"…that mocks **even** every meaning"`——**官方英文直接给出 `even`**，与 `すら` 对应。

**证明 3：clitic 附着关系（3/3 无例外）**

| offid | 日文副助词 | 其宿主名词 | 爱丽丝语中 `Loosya` 的位置 |
|---|---|---|---|
| 236 | 人で**すら**…ない | **人**（=`Enebis`） | `Loosya` 紧接在 `Enebis` **之前** |
| 631 | 独裁者**も** | **独裁者**（=`Liiquip`，由官方英译 "dictator" 锚定） | `Loosya` 位于 `Hewvews Liiquip` 这一整个名词短语**之前** |
| 865 | 意味**すら** | **意味**（=`Selti`） | `Loosya` 紧接在 `Selti` **之前** |

三例中 `Loosya` 恒在被 `すら/も` 所附着的**同一个名词短语之前**——正是副助词的宿主关系，只是方向与日语相反（同 §4.17.2"日语后置 → 爱丽丝语前置"）。

**证明 4：全域反例检索 = 0**

官方日文中含**副助词 `すら`** 的行共 3 条：236、801、865。

- 236 ✓ 含 `Loosya`；865 ✓ 含 `Loosya`
- 801 的爱丽丝语对应文本为**空**（无对齐，无法检验）→ 不构成反例
- offid=434/435/436 的 `すら` 属 **`ひたすら`**（"一味地"，另一词），**不是**副助词；这三行爱丽丝语侧也确实不含 `Loosya`，与判定一致

→ **"含副助词 すら 且有爱丽丝语对应文本"的行中，`Loosya` 出现率 2/2；零反例。**

**排除"任何 / 每"（`何も`）**

日语 `何も / 誰も / どんな` 都要求句中出现疑问词（何/誰/ど）。而上述 **3 行的日文全部不含任何疑问词**（已检索）；加上证明 1 中「人ですらない」的语素已被 4:4 完全对完，**不存在"任何/每"所需的疑问词槽位**。故"任何/每"在官方证据中**无立足点**。

**中文生成用「连 … 都」框架**

- `Loosya` → 「连」，其受辖名词短语（相邻 形容词/冠词/数词＋名词）**后置追加「都」**；若其前有否定，则否定并入后缀成为「都不是」
- 实测：`Loosya Selti` → 连意义都；`Vig iy Nai Loosya Enebis` → 你连人类都不是；`Loosya Hewvews Liiquip` → 连自恋的独裁者都

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
| 所以至少在你迷失自我的时候 | `Elize imm Krey Phier Holo Miis imm Aim` | Elize = 因为（日：だから，行首接续词） |
| 因为世界总是抛弃我们 | `Elize Shelista Fur a Leimy Zill Baly` | Elize = 因为（日：見放す**から**，21/23） |
| 用这双手改写故事 | `… Olkemia Story ifa Bis a Xia Haol` | ifa 工具短语前置（日：この手**で**） |
| 任何事物 / 没有任何事物 | `Zel Note` / `Zel` | Zel = 何（日：何**も**） |
| 我的心一边被杀 | `Poetklar Myte Herz Yien Torjest Mii` | Poetklar = 一边（日：打ちひしがれ**ながら**） |

---

## 7. 主要证据来源

- **翻译规则代码**：`app/src/main/python/webui_backend/`
  - `translation_alician.py`、`translation_alician_syntax.py`（爱丽丝语 → 中文）
  - `translation_chinese_lexicon.py`、`translation_chinese_grammar.py`（中文 → 爱丽丝语）
  - `translation_data.py`（词典 / no_class / 语料加载）、`translation_common.py`（共用规则）
- **语料库**：`app/src/main/assets/translated.db`
  - **`song_translations`：官方对照文本（`japanese` 原曲 / `english` 官方英译 / `korean`），判断功能词语义的第一依据**
  - `no_class`：语法功能与形态规则记载
  - `sentence_alignments`：1188 条精确中爱对齐句（其 `chinese_translation` 为**本地化**文本，可用于流畅度检验，**不可用于判定连接词语义**）
  - `adverb_position_stats`：副词位置统计
  - `songs` / `raw`：歌词语料（句式模式来源）

> **取证优先级（仅一级为权威）**：
> 1. **`song_translations.japanese`（官方日文歌词）与 `song_translations.english`（官方英译）——唯一的官方证据**
> 2. `dictionary.japanese_gloss`/`english_gloss`（**社区维护**的词表，可作旁证，不可当铁证）
> 3. `dictionary.explanation`（中文释义，社区维护）
> 4. `sentence_alignments.chinese_translation`（**社区中文本地化，非官方**；会把因/果分句互换、省略连接词，仅可用于流畅度参考，**不可用于判定语义**）
>
> 结论必须能由第 1 级证据独立推出；`Elize`、`Poetklar` 均曾因误用中文列而下错判断。

### 7.1 以官方歌词为基准的评估器

`scripts/jp_reference_eval.py` 用 `song_translations` 替代中文列作为评价基准，含两条互相独立的轴：

| 轴 | 含义 | 当前基线 |
|---|---|---|
| 轴1 功能词标记命中率 | 当爱丽丝语功能词 W 与其官方日语标记 M 同时出现时，译文是否含 M 的中文反射 | **555/555 = 1.000** |
| 轴2 词汇释义召回率 | 每个已识别实词是否至少有一个（人工核验过的）词典释义出现在译文中 | **2357/2361 = 0.998** |

- 轴1 逐词给出「用例 / 命中 / 准确 / 偶然 / 提升」，`偶然` 为该反射词在随机译文中的出现率，`提升 = 准确/偶然`；单字高频标记（で/と/も/か/た/の/何）标注 `*弱`，判别力低
- 轴2 会把「无情的 ↔ 无情地」这类句法位置导致的词形差异、以及被构式（`Aihel imm`、`Poul ail` 词组等）吸收的词做归一化处理，仅保留真实漏译
- 用法：`py -3.14 scripts/jp_reference_eval.py [--worst N] [--only 词...] [--json 输出.json]`

**轴2 曾余 4 处残差**，全部是**词典中文释义与官方日文不一致、而翻译器按日文取对**的情况（例：`Qllsiim` 词典注"人们"，其 `japanese_gloss` 为 **我々**、`english_gloss` 为 **we**，译文取"我们"；`Xianya` 词典注"那个"，日文为 **それら/あいつら**，译文取"他们"）。这些词条的中文释义**已按日文列修正**，见 §7.2。

### 7.2 词条释义按官方日文列修正记录【语料实证】

上节残差已修复：`scripts/migrate_gloss_fixes.py` 把 10 个词条的释义与其**自身**的日/英注对齐，并同步 `dictionary`、`dictionary_headwords`、`<词类>` 三张表。**注意证据层级**：下表每条的判定依据都是**官方日/英歌词行**（`song_translations`），词典自身的日/英注只作旁证；中文列为社区维护，不作证据。执行前已备份数据库（`backups/translated.db.<时间戳>.bak`），脚本同时输出回滚 JSON（`backups/gloss_fix_<时间戳>_rollback.json`），可一键还原：

```bash
py -3.14 scripts/migrate_gloss_fixes.py --dry-run          # 预览
py -3.14 scripts/migrate_gloss_fixes.py                    # 应用 + 生成回滚文件
py -3.14 scripts/migrate_gloss_fixes.py --rollback backups/gloss_fix_xxx_rollback.json
```

| 词 | 原中文释义 | 修正为 | 官方日文证据 | 官方英文 |
|---|---|---|---|---|
| `Qllsiim` | 人们 | **我们** | offid=232 `… Qllsiim …` ↔「そうして **我々**は 共に愛し合い…」 | we |
| `Qllsiimtiel` | 它自己(?) | **我们自己** | offid=230 ↔「まず**我々自身**を愛してあげましょう」 | ourselves |
| `Xianya` | 那个 / 它(作主语) | **他们 / 那些**（词类改 pron.） | offid=228「**それら**は ぼくを何度も突き刺した」、offid=520/716 英译皆 they | Those people |
| `Salah` | 阴影 / **水面(?)** | **阴影**（删除"水面"义项） | offid=154 瞳の**影**、430 朝**影**に映る、665 **影**に取り憑かれた、856 人**影** | shadow |
| `Rinasia` | 诞生 / 产生。也可以写作Rin或Rin Asia(?) | **诞生 / 出生**（说明文字移出释义） | offid=241 `生まれ`、497/498 `生まれ変わる`、854 `生まれる`、1008 `生まれてこなければ` | born |
| `Loosya` | 任何(?) | **连** | 官方日文 3 例皆副助词：offid=236「人です**ら**ない」（排除法证明：该分句 4 语素已由 Vig/iy/Nai/Enebis 对完，余下 `すら` 必归 Loosya）、865「意味**すら**嘲る」（官方英译 `mocks **even** every meaning`）、631「独裁者**も**」；含副助词 `すら` 的官方行 2/2 皆含 Loosya、零反例（详见 §4.19） | even |
| `ob` | 助动词 / 用于过去完成时(?) | **持续** | offid=185「止まっ**ていた**時間」、319「みんな待っ**てた**」 | had been |
| `Coll` | 身躯(?) | **身躯**（去存疑标记） | offid=305 `汚い体`、321 `体をすり抜け`、543 `大きな体`、683 `ぼくらの体` | body |
| `tie` | 在(?) | **在**（去存疑标记） | offid=62/63 `故郷で会える`（不可写作"在…中"，该字段兼作译文表面） | Inside |
| `Mail` | 披上 / 衣服(?) | **披上 / 衣服**（去存疑标记） | offid=588 `天命を纏い`、747 `服を着替えて` | clad |

**"水面"归属更正**：offid=154「瞳の影 瞳の奥の**水面**」中，`水面` 由 `Akarche`（n. 水面）承担，与 `Salah` 无关——该义项已从 `Salah` 删除。

**同时移除代码补丁**：`translation_alician.py` 的 `_attested_lexical_override_token` 原含 `xianya`/`qllsiim`/`qllsiimtiel` 三条手写覆盖（注释即"对齐语料与官方译文均作 …"）——这是当初发现数据冲突却以代码绕过的产物。数据修正后已删除，使数据库成为唯一真相源。

**修正后基准**：轴1 = 555/555 = 1.000，轴2 = 2361/2361 = **1.000**（残差归零）。
