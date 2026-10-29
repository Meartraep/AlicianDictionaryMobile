# 词典 / 数据库管理器合并方案

> 状态：**方案待评审**（本文只做设计与规划，不含实现）
> 基线：`main` @ `88d9c1f` + 一笔未提交的词典改造（歌曲检索 / 整首歌词 / 义项级编辑）
> 依据：三份只读清点（数据库管理器 / 词典 / 发布与版本），全部结论带 `文件:行`
> 目标一句话：**日常数据操作全部收进「词典」，数据库管理器退化成「数据库治理」（版本 / 发布 / 回退 / 来源）**

---

## 0. 问题陈述

今天的「数据库管理器」其实是三块东西拼起来的：

| 今天的形态 | 入口 | 干的事 |
|---|---|---|
| `DatabaseScreen`（标题"数据库管理"） | 设置 → 卡片 → 全屏子屏 | 任意表分页浏览、通用增删改、全局搜索替换、重算词频/词性、导出 |
| 设置页「词典数据库 / 数据库更新 / 上游完整数据库」三节 | 设置 | 信息卡、版本检查与更新、导入/导出/恢复内置库、上游全量库对比 |
| 设置页「手机端发布」+ 启动更新弹窗 | 设置 / 应用根 | 发布盖章、设备签名、凭据、PR 状态 |

矛盾点（用户的判断是对的）：

1. **词典已经把"看词条"做到最好，但"改词条"只能改一小部分**——新加的义项级编辑只能改既有 headword 的既有 sense，**不能新增/删除**（`dictionary_core.py` 无 INSERT/DELETE 入口）。
2. **数据库管理器能改一切，但它是给开发者用的原始编辑器**：任意 32 张表、任意列、无业务校验、外键未开（`dbmanager_service.py:16`）、能直接改 `database_metadata` 的版本 marker、每次删除后 `VACUUM`（`dbmanager_service.py:125`）。它出现在这个 App 里，纯粹是历史原因。
3. **发布/版本/回退这一块反而住在设置页，跟"管理器"没有关系**，而且**回退功能根本不存在**——只有"恢复 APK 内置 v1"，备份文件写了却没有任何列出/恢复入口（`mobile_bridge.py:526-531,682-689`）。

所以合并不是"把两个屏叠一起"，而是**按数据生命周期重新切**：

```
            ┌──────────────── 内容层（高频） ────────────────┐
            │  词典：查 → 看 → 改 → 增/删 → 维护/导出        │
            └───────────────────────────────────────────────┘
            ┌──────────────── 治理层（低频、危险、需凭据） ──┐
            │  数据库治理：版本 · 更新 · 回退 · 发布 · 来源   │
            └───────────────────────────────────────────────┘
```

合并后**不存在**"数据库管理器"这个用户的日常目的地；它变成设置里的一个治理页。

---

## 1. 现状盘点摘要（决定方案的硬事实）

### 1.1 数据与结构

- 32 张业务表；最大表 `sentence_alignments` 1286 行 / **1.25 MB 文本**，`songs` 300 KB，`song_translations` 133 KB，`dictionary` 1515 行 / 60 KB（只读实测）。
- 现有表分页是**桥层绕过服务层直接摸私有连接**（`mobile_bridge.py:206-215`）；`get_all_data` 是全量加载（`dbmanager_service.py:30-42`）→ 大表必须改服务端分页。
- 外键在 schema 里声明了 3 条，但**所有 Python 连接都没开 `PRAGMA foreign_keys`**（只有 `writing_database.py:47` 开了）→ 通用删除会留孤儿。
- `songs.lyric` 与 `raw.lyric_raw` 是**两份歌词正文**：词典写 `songs`，重算词频读 `raw`（`update_word_count.py:156-159`）→ 改完歌词词频不更新，且永远无法同时一致。
- 12 张词性表（`n.`/`v.`/`adj.`…）在 App 内**零读者**；只有 `no_class` 被翻译器读。

### 1.2 写路径两极分化

| 写路径 | 校验 | 事务 | 回滚 | 缓存失效 | 备份 |
|---|---|---|---|---|---|
| 词典 `dictionary_update_word` / `_lyric` | 长度/空值/重名/义项归属 | `BEGIN IMMEDIATE` | 有 | 有（`_reload_translator_if_needed`） | 无 |
| 管理器 `db_add` / `db_update` / `db_delete` | **无**（值一律 `str()`） | 单语句 commit | 无 | 部分（表名白名单） | 无 |
| 管理器 `db_global_replace` | 仅字段名 | 显式事务（唯一规范） | 有 | 部分 | 无 |
| 维护脚本 `update_word_count` / `classify_words` | 几乎无 | 单事务但 `synchronous=OFF` + `journal_mode=MEMORY` | 被吞异常 | **无** | 无 |

→ **通用编辑器不能原样搬进访问频率更高的词典页**，这是方案的第一约束。

### 1.3 连接与崩溃面

同一个库文件同时被 **8 类连接**打开（词典共享连接、管理器自有连接、翻译器、写作库、桥层短连接、Kotlin 学习只读连接、启动期读写连接…）。后果：

- 词典连接 `synchronous=OFF`，其它连接默认 FULL；共享文件的持久性由最弱连接决定。
- 管理器连接**没有 `busy_timeout`**：共享连接若泄漏事务，管理器写会立刻 `SQLITE_BUSY`。
- `VACUUM` 需要整库独占，而进程内还有别的连接和 Kotlin 只读连接 → 失败时还会「commit 之后误报失败」。
- 每次单行编辑后 `refreshDatabaseInfo()` 会**整库 SHA-256**（`mobile_bridge.py:136`）。

### 1.4 版本/发布/回退

- 身份是两层：`database_metadata.db_version`（发布基线，只增不重用）+ `sha1/size`（确切字节）。
- 更新提示只看版本号 `remote > local`（`DatabaseUpdateLogic.kt:21,28-32`）→ 本地编辑不会造成"永远提示更新"。
- 发布 = **把当前安装库（含本地编辑）盖上 N+1 号上传**；客户端不记录"本地改过什么"，发布前也没有 diff 审阅。
- **回退不存在**：备份只有文件名，没有元数据、没有 list/restore API、没有 UI；已发布旧版本的字节不可再取（台账只有 sha1/size，raw URL 恒指 `main` HEAD）。
- CI 契约很硬：必需检查 `Ledger, manifest and database agree` 在**每个 PR** 上强制"台账/清单/资产库三方一致 + 改内容必须 bump"；发布 PR 另有 4 路径白名单 + last+1 + 字节绑定 + marker + 签名。

### 1.5 覆盖缺口（词典今天做不到）

| 缺口 | 谁承接 |
|---|---|
| 新增 / 删除词条、义项、短语 | 词典（新建策展入口） |
| 改歌名 / 专辑 | 词典歌词上下文 |
| 浏览原始行 / 翻页看全表 | 词典「数据」工作区（服务端分页） |
| 编辑对齐表 / 官方译文表（`sentence_alignments` / `song_translations`） | 词典「数据」工作区（策展表单，非通用编辑器） |
| 重算词频/泛度、重建 `no_class` | 词典维护动作（先统一正文源） |
| 批量替换 | 词典维护动作（白名单 + 预览 + 前置备份） |
| 回退 / 恢复点 | **数据库治理页（新建）** |

---

## 2. 目标架构

### 2.1 职责重划

| 层 | 宿主 | 负责 | 频率 |
|---|---|---|---|
| **内容层** | 词典（底部导航第 1 项） | 查询、词条/义项/短语增删改、歌词、对齐与译文、维护动作、导出、诊断 | 每天 |
| **治理层** | 设置 → 「数据库」二级页 | 版本与身份、更新检查、恢复点与回退、发布、数据来源、整库导入/导出 | 每周/每次发版 |

### 2.2 五条设计原则

1. **单一写者（single writer）**：所有 SQLite 写经由同一个数据层、同一把锁、同一套事务与校验；`DatabaseManagerService` 被吸收，不再有第二条写连接。
2. **策展编辑，不做万能表格**：只在白名单表上暴露编辑，字段按 schema 校验；系统表只读；危险操作必须「预览 → 备份 → 二次确认」。
3. **一切可回退**：任何写操作之前都能拿到恢复点（自动或手动），恢复点有元数据（版本/时间/原因/sha1）与恢复入口。
4. **契约不变**：`db_version` / `sha1` / 台账 / 清单 / 签名 / CI 的语义一字不改；新增的只是"本地修改"的记账。
5. **缓存失效走统一事件**：写成功后统一触发 `translator / study deck / databaseInfo` 失效，不允许各写路径各记一套表名白名单。

### 2.3 反目标（明确不做）

- ❌ 不新增底部导航项；不把发布/版本搬进词典。
- ❌ 不做「任意表/任意列」的通用行编辑器暴露给日常用户（`database_metadata`、`raw`、派生表必须只读）。
- ❌ 不改 `db_version` 语义、不改台账追加式规则、不放宽 CI 白名单。
- ❌ 不做自动合并（本地修改 vs 官方更新）的冲突解算；首版只做"检测 + 备份 + 提示"。
- ❌ 不保留 12 张词性表的写入口（零读者）。

---

## 3. 布局

### 3.1 导航总览（不变）

```
底部导航（竖屏）/ 侧边 rail（横屏）：词典 · 写作 · 翻译 · 背诵 · 设置
词典 tab = 两个工作区：  [ 检索 ] [ 数据 ]
设置 tab = 一个治理入口： 「数据库」卡片 → 数据库治理页（版本/更新/回退/发布/来源）
```

### 3.2 词典 · 检索工作区（竖屏）

```
┌──────────────────────────────────────────────────┐
│ 爱丽丝语词典                          [+ 新增] [⋮]│   ← 标题行：新增词条 / 维护菜单
│ ┌──────────────┬──────────────┐                  │
│ │   检 索      │   数 据      │  ← SegmentedButton（并排，选中态清晰）
│ └──────────────┴──────────────┘                  │
├──────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────┐ │
│ │ 🔍 爱丽丝语、中文、英文或日文                  │ │
│ │ [精确]   位置 [任意 ▾]                        │ │
│ └──────────────────────────────────────────────┘ │
│ 最近：Xia · 爱 · world · Alice Music              │
│ ──────────────────────────────────────────────── │
│ 爱丽丝语 → 中文                            3 条   │
│ ┌──────────────────────────────────────────────┐ │
│ │ Finz    n.                          [ 修改 ] │ │
│ │ 结局，终末 v. 结束 adj. 终末的                │ │
│ │ 义项 4 条：结局 / 终末 / 结束 / 终末的        │ │  ← 义项摘要（点开展开全部）
│ │ 词频 48 · 泛度 22 · 点按查看歌词例句          │ │
│ └──────────────────────────────────────────────┘ │
│ 歌词英/日译命中                            2 条   │
│ ┌──────────────────────────────────────────────┐ │
│ │ A Little Servant · 追憶の図書館               │ │  ← 歌曲归属（上一轮已补）
│ │ ……                                          │ │
│ └──────────────────────────────────────────────┘ │
│ 歌曲标题                                   1 条   │
│ ┌──────────────────────────────────────────────┐ │
│ │ Alice Music · アリスシャッハと氷の世界樹      │ │
│ │ 歌曲标题命中 · 点按查看完整歌词               │ │
│ └──────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

新增/改动点（相对今天）：

- 顶部增加 **工作区切换**（检索 / 数据）与标题行 **「新增」** 按钮。
- 词条卡片增加 **义项摘要**（`senses` 上一轮已经随搜索返回，不需要新接口）。
- 「修改」按钮 → 义项级编辑对话框（已有），对话框内新增 **删除义项 / 删除词条 / 新增义项** 三个动作。
- 「新增词条」→ 新建策展对话框：词头 + 词性 + N 个义项（中文/英/日），保存走同一个写守卫。

### 3.3 词典 · 数据工作区（竖屏）

```
┌──────────────────────────────────────────────────┐
│ 爱丽丝语词典                          [+ 记录] [⋮]│   ← ⋮ = 维护菜单（见 3.5）
│ ┌──────────────┬──────────────┐                  │
│ │   检 索      │   数 据      │                  │
│ └──────────────┴──────────────┘                  │
├──────────────────────────────────────────────────┤
│ 表  [核心 ▾]  [dictionary_headwords ▾]           │   ← 分组 + 表选择
│ ┌──────────────────────────────────────────────┐ │
│ │ 🔍 搜索当前表                      [精确]     │ │
│ └──────────────────────────────────────────────┘ │
│ 1,339 行 · 第 1 / 27 页 · 每页 50                │
│ ┌──────────────────────────────────────────────┐ │
│ │ #388  Finz                                   │ │
│ │ words        Finz                            │ │
│ │ 释义          结局，终末 v. 结束 adj. 终末的   │ │
│ │ 词频/泛度     48 / 22                         │ │
│ │                       [ 在词典中查看 ] [编辑] │ │
│ └──────────────────────────────────────────────┘ │
│ ┌──────────────────────────────────────────────┐ │
│ │ #389  Finza                                  │ │
│ │ ……                                           │ │
│ └──────────────────────────────────────────────┘ │
│        [ ← 上一页 ]   1 / 27   [ 下一页 → ]      │
└──────────────────────────────────────────────────┘
```

表分组（这是替代"32 张表随便点"的关键）：

| 分组 | 表 | 能力 |
|---|---|---|
| 核心词典 | `dictionary_headwords`、`dictionary`、`phrase` | 可编辑（策展表单） |
| 歌词与译文 | `songs`、`sentence_alignments`、`song_translations` | 可编辑（策展表单） |
| 语义 | `dictionary_semantic_aliases`、`semantic_alias_metadata`、`adverb_position_stats` | 只读 |
| 系统 | `database_metadata`、`Signature` | 只读（显示版本等关键信息） |
| 遗留（默认折叠） | `raw`、`Album1-3`、`Single`、`All_words`、`Unknown`、`test`、12 张词性表 | 只读；后续版本可整体隐藏/删除 |

行卡片的「在词典中查看」是**双向跳转**：从原始行跳到检索工作区的对应词条/歌曲，这是"两个模块真正连起来"的体验点。

### 3.4 数据工作区 · 行编辑器（对话框 / 底部弹层）

- **策展表单**，不是"每个列一个输入框"：
  - `dictionary_headwords`：`words`（必填，唯一性实时校验）→ `display_explanation`（必填）→ 下面列出该词头全部义项（复用已有义项编辑器）
  - `songs`：`title`（唯一）→ `Album` → `lyric`（全屏编辑器）
  - `sentence_alignments`：`alician_sentence` / `chinese_translation` / 对齐状态（只读展示得分/方法）
  - `song_translations`：句子 + 英/日/韩 三栏
- 保存前：字段校验 → 影响预览（"将修改 1 个词头的 4 个义项"）→ 需要时自动创建恢复点。
- 删除前：级联说明（"删除词头将同时删除 4 个义项、3 条语义别名"）→ 二次确认 → 恢复点。

### 3.5 维护菜单（数据工作区 ⋮ / 检索工作区长按）

| 动作 | 现状 | 方案 |
|---|---|---|
| 重算词频 / 泛度 | 管理器菜单，读 `raw` | 迁入；先统一正文源（见 4.5） |
| 重建 `no_class` | 管理器菜单，顺带建 13 表 | 只重建 `no_class`；12 张词性表退役 |
| 全局替换 | 管理器菜单，作用全 32 表 | 白名单表 + 预览 + 前置恢复点 |
| 导出 CSV（ZIP） | 管理器菜单 | 迁入（唯一入口） |
| 导出 SQLite | 管理器菜单 + 设置页（重复） | 只保留设置/治理页一处 |
| 创建恢复点 | 不存在 | 新建 |
| 数据库诊断 | 不存在 | 新建：`integrity_check` / 孤儿行 / 表行数 / 外键状态 |

### 3.6 数据库治理页（设置 → 「数据库」）

```
设置
┌──────────────────────────────────────────────────┐
│ 数据库                              v1 · 已修改 3 处 ⚠ │  ← 卡片（替代原"数据库管理"）
│ 词头 1,339 · 歌曲 53 · 2.7 MB                      │
│ 版本、更新与回退                            >     │
└──────────────────────────────────────────────────┘
                ↓ 点击进入
┌──────────────────────────────────────────────────┐
│ ← 数据库治理                                      │
│ ┌ 版本与身份 ───────────────────────────────────┐ │
│ │ 当前 v1 · 2026-10-14 · local 2026-10-29        │ │
│ │ 本地已修改：3 个词条、1 首歌（上次编辑 00:41）  │ │
│ │ sha256 8a3f…c21d                              │ │
│ └───────────────────────────────────────────────┘ │
│ ┌ 更新 ─────────────────────────────────────────┐ │
│ │ [✓] 启动时自动检查                             │ │
│ │ 立即检查更新       最近检查 今天 00:30          │ │
│ └───────────────────────────────────────────────┘ │
│ ┌ 恢复点与回退 ─────────────────────────────────┐ │
│ │ 00:41 · 编辑词条前 · v1 · 2.7 MB     [恢复]   │ │
│ │ 昨天 23:12 · 更新前 · v1 · 2.7 MB    [恢复]   │ │
│ │ [立即创建恢复点]                               │ │
│ │ 恢复 APK 内置数据库 v1                         │ │
│ └───────────────────────────────────────────────┘ │
│ ┌ 发布 ─────────────────────────────────────────┐ │
│ │ 签名密钥 ✓ · GitHub ✓    [发布新版本]          │ │
│ │ 发布预览（版本 N+1、字节指纹、包含本地修改）    │ │
│ └───────────────────────────────────────────────┘ │
│ ┌ 数据来源 ─────────────────────────────────────┐ │
│ │ [检查上游完整数据库] [导入数据库文件]           │ │
│ │ [导出当前数据库]                               │ │
│ └───────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────┘
```

要点：

- **"本地已修改 N 处"是新增能力**（当前完全没有），它把"内容层"和"治理层"缝起来：词典里改，治理页看；治理页决定覆盖与否。
- 「恢复」= 列出 `translated.backup_*.db` + 新恢复点，带元数据（版本/原因/sha1/大小），恢复走 `size+sha1+marker` 同一套校验链。
- 发布预览增加"本次发布包含 N 处本地修改"的提示（不做自动合并，只让人知道）。

### 3.7 横屏布局

```
┌──────┬───────────────────────────┬────────────────────────────┐
│ rail │ 左 pane（检索/数据 共用）   │ 右 pane（结果/行列表）       │
│ 词典 │                           │                            │
│ 写作 │ [检索][数据]               │ 爱丽丝语 → 中文      3 条   │
│ 翻译 │ 🔍 搜索框                  │ ┌────────────────────────┐ │
│ 背诵 │ [精确][位置]               │ │ Finz       [修改]      │ │
│ 设置 │                           │ └────────────────────────┘ │
│      │ 数据模式时：                │ 数据模式时：                │
│      │ 表分组 + 表选择 + 搜索      │ 行卡片列表 + 分页           │
└──────┴───────────────────────────┴────────────────────────────┘
```

复用现有 `LandscapeTwoPane(primaryWeight = 0.44f)`；**不**改共享组件签名。

### 3.8 状态与返回行为

- 工作区选中态（检索/数据）用 `rememberSaveable` 存在词典屏内；表选择/搜索词/页码同样 saveable，切 tab 回来不丢。
- 编辑对话框草稿（新增词条、歌词、行编辑）改为 saveable 的 key（当前 `editingEntry` 是 `remember`，旋转会丢）。
- 词典屏新增 `BackHandler`：数据模式 → 回检索模式；编辑对话框 → 关对话框（优先级：对话框 > 数据模式）。

---

## 4. 技术方案

### 4.1 统一数据访问层（P0 核心）

新增 `webui_backend/data_core.py`（或把 `DatabaseHandler` 提升为 `DataCore`）：

```
DataCore
├─ 唯一写连接：WAL + busy_timeout=5000 + foreign_keys=ON + synchronous=NORMAL
├─ ReadHandle：分页查询（服务端 LIMIT/OFFSET）
├─ WriteGuard：表白名单 → schema 元数据 → 校验 → 事务 → 事件 → 审计
└─ EventBus：translator / study / databaseInfo 失效（统一在写成功后触发一次）
```

- **WAL**：读写不互斥，解决管理器 `SQLITE_BUSY` 的根源；`journal_mode` 是持久属性，落盘后所有连接共享。
- **`busy_timeout`**：给所有连接设置（含 `writing_database.py`），不再立即失败。
- **`foreign_keys=ON`**：开启前先跑孤儿审计并修数据（当前仅 1 条 `song_translations` 孤儿标题，见附录 A）。
- **去掉 `VACUUM`**：删除后不再 `VACUUM`；空间回收交给显式"数据库诊断 → 压缩"动作（带确认与备份）。
- **`synchronous`**：统一为 `NORMAL`（WAL 下的安全/性能平衡点），删除词典连接的 `OFF`。

### 4.2 写守卫（WriteGuard）—— 让"策展编辑"可机器执行

表级元数据（新文件 `webui_backend/data_schema.py`）：

```python
TABLES = {
  "dictionary_headwords": TableSpec(
      group="core", editable=True, label="词头",
      unique=[["words"]], required=["words"],
      display=("words", "display_explanation"),
      cascade=[("dictionary", "headword_id"), ("dictionary_semantic_aliases", "sense_id")],
      invariants=["sync_child_words"],   # dictionary.words 跟 words 同步
  ),
  ...
  "database_metadata": TableSpec(group="system", editable=False),
}
```

写操作统一入口：`write(table, op, row, draft)` → 校验 → 事务 → 事件 → 审计。
所有 `db_add/update/delete/global_replace` 的语义在这里重建，**不保留旧实现**。

### 4.3 本地修改台账（把"改过什么"变成一等数据）

新增表（资产库与安装库都带 schema，发布时随库走）：

```sql
CREATE TABLE local_edits (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  table_name TEXT NOT NULL,
  row_key TEXT NOT NULL,      -- 业务主键（headword_id / song title / sense_id …）
  op TEXT NOT NULL,           -- insert | update | delete
  summary TEXT NOT NULL,      -- 人类可读（"Finz：义项 2 释义"）
  changed_at TEXT NOT NULL,
  device TEXT                 -- 可选：设备标记
);
```

用途：治理页"本地已修改 N 处"、发布预览、更新前提示、回退提示、诊断。
**不**用它做自动合并；不存全文旧值（避免膨胀），只存摘要——真要保留旧值，走恢复点（文件级）。

> 注意：台账表进入资产库后，CI 的"改内容必须 bump"规则会把它当成内容变化 → 每次编辑都会让资产库与台账不一致（CI 只在仓库资产库上跑，安装库不上传，所以**不影响 CI**）。但发布后新版本会带这张表 → 属于 schema 变更，需要一次版本 bump + 文档。

### 4.4 桥方法命名空间重整

| 命名空间 | 方法 | 状态 |
|---|---|---|
| `dict_*` | `dictionary_search` / `_examples` / `_song_lyrics` / `_update_word` / `_update_lyric` | 保留 |
| `data_*`（新） | `data_tables` / `data_page` / `data_row` / `data_create` / `data_update` / `data_delete` / `data_replace_preview` / `data_replace_apply` / `data_diagnose` / `data_export_*` | 新建 |
| `gov_*`（新） | `gov_identity` / `gov_backups` / `gov_backup_create` / `gov_backup_restore` / `gov_update_*` / `gov_publish_*` | 部分新建（更新/发布已有实现，改名收口） |
| `db_*` / `database_*` / 维护脚本名 | — | P4 删除（P2-P3 期间降级为 deprecated） |

### 4.5 维护动作加固

1. **正文源单一化**：定 `songs.lyric` 为唯一正文源，`raw` 降级为"导入存档（只读）"；`update_word_count` 改为读 `songs.lyric`，并在写完后触发同一套事件。
2. **脚本 pragma 修正**：去掉 `synchronous=OFF` / `journal_mode=MEMORY`；显式事务；异常不吞。
3. `classify_words` 缩成"重建 `no_class`"；12 张词性表的 DDL 与数据在下一版资产库里删除（需一次 bump）。
4. 维护动作期间不再 `_close_services()` 全关服务（改为"维护模式"：只挡写，读继续）。
5. 维护成功后统一 `translator reload` + 学习牌组刷新。

### 4.6 恢复点与回退

**恢复点（本地，先做）**

- 文件：`filesDir/backups/translated_<时间戳>_<原因>.db` + 同名 `.json` 元数据
  `{db_version, sha1, size, created_at, reason, local_edits_count}`。
- 创建时机：危险操作前自动（删除词条/歌、全局替换、整库导入、更新前）+ 手动。
- 恢复：先校验 `size + sha1 + marker`（复用 `replace_database` 的校验链，`mobile_bridge.py:675-681`），再**原子替换**（写临时文件 + `os.replace`），替换前自动为当前库再建一个恢复点。
- 清理策略：保留最近 N 个（如 10）+ 至少 1 个"更新前"点，其余按时间淘汰。

**版本回退（官方旧版本，后做，需要契约变更）**

现状做不了：台账只有 sha1/size，没有每版下载地址，raw URL 恒指 `main` HEAD。要做必须在发布侧增加"每版归档地址"（例如 GitHub Release asset 或 `db-versions/vN/translated.db`），并允许"降级安装"（当前 `DatabaseUpdateLogic` 只升不降）。**建议首版不做**，用"恢复点 + 设置标记"覆盖 90% 需求。

### 4.7 更新与"本地有修改"的交互

- 更新检查改用 `gov_identity`：返回 `local_db_version` / `published_version` / `local_modified` / `local_edits_count`。
- 更新对话框文案分层：
  - 无本地修改 → 原文案
  - 有本地修改 → "本次更新会覆盖 N 处本地修改；已自动创建恢复点，可在 数据库治理 → 恢复点 里回退"
- 不做自动合并；不做"跳过本次更新"以外的策略。

### 4.8 性能预算法

| 场景 | 目标 |
|---|---|
| `search()` | < 20 ms（现状 1–12 ms） |
| 单行编辑（含校验+事务+事件） | < 150 ms（不含翻译器重建） |
| 表分页（任意表） | 服务端分页；默认 50 行/页（`sentence_alignments` 约 62 KB）；上限 200 行仅用于旧 UI 兼容，单页约 250 KB |
| 批量编辑 100 行 | 单事务 + 一次翻译器重建 |
| 数据库信息刷新 | 不再每次编辑整库 SHA-256；`sha` 懒计算 + 编辑后标记 stale |

---

## 5. 分期实施计划

> 前置 **P-1（必做）**：把当前未提交的词典改造（歌曲检索/整首歌词/义项编辑 + 测试 + CI）落成一个 PR 并合并。
> 理由：本方案所有阶段都在这笔改动之上；不先落库，后续 diff 无法评审、也无法回滚。

### P0 地基（2–3 天，无 UI 变化）

| 项 | 内容 | 验收 |
|---|---|---|
| 统一数据层 | `DataCore` + WAL/`busy_timeout`/`foreign_keys`/`synchronous=NORMAL`；`DatabaseManagerService` 改为薄只读适配器 | `PRAGMA journal_mode` 返回 `wal`；并发写不再 `SQLITE_BUSY` |
| 孤儿审计与修复 | 修 1 条 `song_translations` 孤儿；开启 `foreign_keys` | `PRAGMA foreign_key_check` 空 |
| 写守卫骨架 | `data_schema.py` 表元数据 + `WriteGuard`（校验/事务/事件/审计） | 单测：非法列/缺失必填/唯一冲突全部被拒 |
| 恢复点 API | `gov_backups` / `create` / `restore`（原子替换 + 校验链） | 单测：创建→改库→恢复→sha1 回到原值 |
| 本地修改台账 | `local_edits` 表 + 写入钩子 | 单测：编辑一次→台账 1 条 |
| 测试先行 | `db_*` 写路径目前**零测试**；先补 `test_data_guard.py` | `unittest` 全绿并入 CI |

### P1 数据工作区（只读，2 天）

- 词典屏加 `[检索][数据]` 工作区切换（`rememberSaveable`）；数据区 = 表分组 + 表选择 + 服务端分页 + 行卡片。
- 行卡片「在词典中查看」跳回检索并定位。
- 旧 `DatabaseScreen` 保持可用（双轨过渡）。

验收：`sentence_alignments` 分页响应 < 200 KB；切 tab 返回后状态保留；横屏两 pane 正常。

### P2 数据工作区（写，4 天）

- 策展编辑器接入 `data_*`：词头/义项、歌曲、对齐、译文四类表单。
- 新增/删除词条与义项（含级联与恢复点）；检索区「+ 新增」入口。
- 写守卫全量接管：所有写走 `DataCore`；旧 `db_*` 入口从 UI 下线（桥方法保留但标记 deprecated）。
- 学习牌组/翻译器/数据库信息统一失效。

验收：新增词条 → 检索可见 → 翻译可用 → 学习 deck 刷新；删除词头 → 义项/别名级联；所有写前有恢复点。

### P3 维护动作迁移（2–3 天）

- 重算词频/泛度（正文源统一后）、重建 `no_class`、全局替换（白名单+预览）、导出、诊断。
- 脚本加固（pragma/事务/事件）；维护模式不再全关服务。

验收：改歌词 → 重算词频 → 词频变化符合预期；全局替换只命中白名单表且有预览与恢复点。

### P4 数据库治理页（3 天）

- 新 `DatabaseGovernanceScreen`（版本/更新/恢复点与回退/发布/来源）。
- 设置页合并为一个「数据库」卡片；删除设置页旧区块与重复导出入口。
- `gov_*` 桥方法收口；`DatabaseUpdateDialog` 接入 `local_modified` 提示。

验收：设置页只剩一张数据库卡片；恢复点列表/恢复可用；更新提示在"本地有修改"时显示覆盖提示。

### P5 收尾（2 天）

- 删除 `DatabaseScreen`、`dbmanager_service.py`、`db_*` 桥方法、ViewModel 死状态、Kotlin 死回调。
- 删除 12 张词性表 + `classify_words` 的 DDL 部分（需要一次数据库 bump + 台账/清单更新 + 文档）。
- 文档：`docs/DATABASE_VERSIONING.md`（新增"本地修改/恢复点"一节）、新契约文档、README 能力表。
- CI：把新测试接进必需检查；补 `test_prepare_publication.py` 到 PR 流程（当前缺口）。

验收：全仓 grep 不到 `DatabaseScreen` / `db_add|db_update|db_delete` / `DatabaseManagerService`；`./gradlew testDebugUnitTest` + 全部 Python 测试绿；数据库三方一致。

**总工期估算：约 15–17 个工作日**（不含 P-1 与一次数据库 bump 的评审时间）。

---

## 6. 风险与对策

| # | 风险 | 影响 | 对策 |
|---|---|---|---|
| R1 | 两条写路径并存期间不变量分叉 | 词典/翻译/学习读到不一致数据 | P0 就统一写层；P2 下线旧入口；双轨期只留旧入口只读 |
| R2 | 开启 `foreign_keys` + WAL 后行为变化 | 既有写入失败/性能变化 | P0 先做孤儿审计与全量测试；分批开（先 WAL 再 FK） |
| R3 | 本地修改台账与发布契约冲突 | 发布 PR 被 CI 拒 | 台账表只影响安装库与发布后的新资产库；P4 与 bump 一起做，CI 白名单不含新表路径 |
| R4 | 误删/误改（编辑器更强了） | 数据丢失 | 恢复点 + 级联预览 + 二次确认 + 审计；危险表只读 |
| R5 | 大表分页性能 | 卡顿/OOM | 服务端分页强制 `LIMIT`；单页 payload 预算；`sentence_alignments` 只按需字段查询 |
| R6 | 词典页变"万能页" | 认知负担、编译/维护成本 | 只有两个工作区 + 一个 ⋮ 菜单；编辑全部用对话框；不堆列表项 |
| R7 | `MainViewModel` 继续膨胀（已 1228 行） | 可维护性 | P1 起把管理状态收进 `DataWorkbenchState` 持有类；P4 拆出 `GovernanceViewModel` |
| R8 | 发布/回退语义被误解 | 用户以为能回退到任意历史版本 | UI 明说"恢复点 = 本机快照"；历史版本回退单独立项（4.6 后段） |
| R9 | 测试覆盖不足 | 搬迁在无网下改写路径 | P0 先补写层测试；每阶段验收含真库副本测试 |

---

## 7. 需要你拍板的决策

| # | 决策 | 选项 | 我的建议 |
|---|---|---|---|
| D1 | 数据工作区的形态 | (a) 词典内第二个工作区（SegmentedButton） (b) 新增底部第 6 个 tab | **(a)**：不增加导航负担，且"查/改/维护"是同一任务流 |
| D2 | 表编辑尺度 | (a) 策展白名单 + schema 校验 (b) 保留任意表任意列 | **(a)**；`database_metadata`/`raw`/派生表只读 |
| D3 | 回退范围首版 | (a) 仅本机恢复点 (b) 同时做"回退到任意已发布版本" | **(a)**；(b) 需要台账加每版地址 + 允许降级，建议单独立项 |
| D4 | 本地修改在发布时的处理 | (a) 一起发布，发布前只提示 (b) 发布前要求逐条确认 | **(a)** 首版；(b) 作为后续增强 |
| D5 | 12 张词性表 + 遗留表（`Album1-3`/`Single`/`All_words`/`Unknown`/`test`） | (a) 下一版资产库删除 (b) 保留只读 | **(a)**：零读者、减少攻击面；需要一次 bump |
| D6 | 是否需要编辑历史（可撤销单笔编辑） | (a) 只做摘要台账 (b) 存旧值、支持撤销 | **(a)** 首版；旧值靠文件级恢复点 |
| D7 | 治理页位置 | (a) 设置 → 「数据库」二级页 (b) 保留在设置首页平铺 | **(a)**：设置页已经很挤（875 行） |

---

## 8. 附录

### A. 需要一次性修复的数据问题

| 项 | 现状 | 处理 |
|---|---|---|
| `song_translations` 孤儿 | 1 条标题在 `songs` 中不存在 | **已修（db v2）**：随 bump 删除 |
| 外键未启用 | 3 条 FK 声明形同虚设 | P0 开启 `foreign_keys=ON` |
| 双正文源 | `songs.lyric` vs `raw.lyric_raw` | P3 定 `songs` 为唯一正文源 |
| `test` / `Signature` / `Album*` 等遗留表 | 32 张表混在一起 | **已修（db v2）**：删 12 张词性表 + `test`/`Album1-3`/`Single`/`All_words`/`Unknown`；保留 `raw`/`Signature`/`no_class`。业务表 32→13 |
| 备份无元数据 | 文件名即全部信息 | P0 新增 sidecar JSON |

### B. 验收命令（每阶段都要跑）

```powershell
# Python 侧
cd app/src/test/python
$env:PYTHONPATH = '<repo>/app/src/main/python'
python -m unittest test_dictionary_search -v
python -m unittest test_database_versioning test_verify_published_database
# 新增（P0 起）
python -m unittest test_data_guard -v
python -m unittest test_backup_restore -v

# Android 侧
.\gradlew.bat :app:compileDebugKotlin :app:testDebugUnitTest

# 数据库契约
python scripts/verify_database_manifest.py
python scripts/verify_database_versions.py
python scripts/update_database_manifest.py --status
git diff --check
```

### C. 术语

| 词 | 含义 |
|---|---|
| 内容层 | 词典里的日常操作：查询、编辑、维护、导出 |
| 治理层 | 版本、更新、回退、发布、数据来源 |
| 恢复点 | 本机文件级快照（`translated_*.db` + 元数据），可回退 |
| 本地修改 | 用户编辑造成、但尚未成为发布基线的字节变化 |
| 策展编辑 | 按 schema 校验、带级联与预览的表单式编辑，不是通用表格 |

---

## 9. 实施记录

### P0 地基 —— 已完成（2026-10-29）

落地内容：

| 文件 | 变化 |
|---|---|
| `webui_backend/data_schema.py`（新） | 33 张表的分组、可写性、必填/唯一/长度/级联规则、UI 摘要字段 |
| `webui_backend/data_core.py`（新） | 单写者连接、写守卫、服务端分页、本地修改台账、恢复点、诊断、原子替换、备份校验 |
| `webui_backend/dbmanager_service.py` | 从"第二个写连接"改为 `DataCore` 适配器；旧方法名/返回形状保留，但写路径全部过校验 |
| `webui_backend/dictionary_core.py` | `DatabaseHandler.attach()` + 连接所有权标记，可复用 `DataCore` 连接 |
| `webui_backend/dictionary_service.py` | `DictionaryService(..., core=...)` 单写者模式 |
| `mobile_bridge.py` | `_data_core` 生命周期；写后事件统一失效翻译缓存；`_table_page` 走服务端分页；新增 `data_tables` / `data_diagnose` / `gov_backups` / `gov_backup_create` / `gov_backup_restore`；词典/歌词编辑写入本地修改台账 |
| `app/src/test/python/test_data_guard.py`、`test_backup_restore.py`（新） | 真库副本回归测试；并入 CI |

与方案的偏差（均有理由，需评审确认）：

1. **不启用 WAL**，改用 `journal_mode=delete` + `synchronous=FULL`。
   原因：App 有两条既有文件级路径——Kotlin 直接复制 `.db` 导出、Android 云备份规则只列 `translated.db`；
   WAL 会让这些副本缺 `-wal` 数据。单写者已消除写-写竞争，`busy_timeout` 覆盖读-写竞争。
2. **`local_edits` 惰性建表**（首次成功写入时才建）。
   原因：若 `connect()` 就建表，全新安装的库字节立刻偏离官方版本，
   会削弱发布守卫"必须包含真实改动才能发布"。
3. **孤儿数据修复延期到 P5**：`song_translations` 的 1 条孤儿需要改资产库，
   而改资产库会触发台账/清单/CI 的 bump 流程；P0 先用 `data_diagnose` 暴露它。
   `foreign_keys=ON` 对既有数据无副作用（只约束新写入）。

验收记录（可重跑）：

```pwsh
cd app/src/test/python
$env:PYTHONPATH = '<repo>/app/src/main/python'
python -m unittest test_dictionary_search -v            # 14 tests OK
python -m unittest test_data_guard test_backup_restore -v
python -m unittest test_database_versioning test_verify_published_database   # 27 tests OK
```

真库诊断结果：`integrity=ok`、`foreign_key_violations=0`、
孤儿 4 项中仅 `song_translations` = 1；恢复点创建/列举/校验/原子恢复往返通过；
词典与数据层共用同一连接（`DictionaryService.db_handler.conn is DataCore.conn`）。

### P1 数据工作区（只读）—— 已完成（2026-10-29）

落地内容：

| 层 | 变化 |
|---|---|
| Python bridge | 新增 `data_page`：服务端分页 + 表元数据（label/group/editable/display），未知表返回中文错误 |
| `Models.kt` / `PythonRepository.kt` | `DataTableInfo` / `DataTableGroup` / `DataTablePage`（含 `pageIndex`/`pageCount`/`canGoPrevious`/`canGoNext`）；`dataTables()` / `dataPage()` |
| `MainViewModel.kt` | `dataTableGroups` / `dataTablePage` 状态；`loadDataTables()`（带缓存，换库后失效）、`loadDataTablePage()` |
| `DictionaryScreen.kt` | 顶部固定 `DictionaryHeader` + `[检索 \| 数据]` 切换器（竖屏/横屏一致）；数据区：数据组/数据表选择、关键词+精确+搜索、只读提示、`MetricRow(记录/页码/每页)`、只读行卡片、「在词典中查看」跳回检索、服务端上一页/下一页 |

关键行为：

- 只在明确动作时查库：进入数据工作区、换组、换表、点搜索/IME、翻页；输入关键词不发请求。
- 切回检索不会触发数据加载（`LaunchedEffect` 以 workspace 为键并提前返回）。
- 行卡片在 `dictionary_headwords` / `dictionary` / `phrase` / `songs` 上提供「在词典中查看」，
  跳转后自动用该值执行词典检索。
- 系统表与遗留表可浏览但只读（P2 才引入写入口）。

验收记录：

```pwsh
.\gradlew.bat :app:compileDebugKotlin :app:testDebugUnitTest   # BUILD SUCCESSFUL
cd app/src/test/python; $env:PYTHONPATH = '<repo>/app/src/main/python'
python -m unittest test_data_guard test_backup_restore          # 77 OK（P0 回归）
python -m unittest test_dictionary_search                       # 14 OK
```

`data_page` 实测：词头 50 行 = 6.8 KB；`sentence_alignments` 默认 50 行 = 62 KB、
上限 200 行 = 250 KB；未知表被拒；旧 `db_table_page` 返回形状不变（旧 DatabaseScreen 不受影响）。

### P2 数据写入（策展编辑）—— 已完成（2026-10-29）

落地内容：

| 层 | 变化 |
|---|---|
| `data_schema.py` | 字段中文名 `FIELD_LABELS` / `field_label()`、长文本集合 `MULTILINE_FIELDS`、声明式外键 `TableSpec.references`（历史表没有真 FK 时也能拦住孤儿） |
| `data_core.py` | `form_meta()`（schema 驱动的表单描述：必填/长度/类型/多行/引用）、`delete_preview()`（事务内真删+回滚，精确到 FK 级联）、`reference_options()`（引用字段候选值）；删除逻辑抽成 `_delete_rows`；写触发集合 `_touched_tables` 扩展（词头编辑连带 `dictionary`，修复 P0 时代翻译缓存漏刷新的缺口） |
| `dictionary_core.py` / `dictionary_service.py` | 策展写入：`create_word_entry`（词头+多义项，单事务）、`add_sense`、`delete_sense`（**保护最后一个义项**）、`delete_headword`（连带义项与语义别名）、`get_headword_entry` |
| `mobile_bridge.py` | 新增 `data_form` / `data_create` / `data_update` / `data_delete`（**删除前自动创建恢复点**，删除失败不产生备份语义）/ `data_delete_preview` / `data_reference_options` / `dictionary_create_word` / `dictionary_add_sense` / `dictionary_delete_sense` / `dictionary_delete_headword` / `dictionary_entry`；写入成功统一重载翻译缓存并记本地修改台账 |
| `Models.kt` / `PythonRepository.kt` | `DataFieldMeta` / `DataReference` / `DataCascadeInfo` / `DataFormMeta` / `DataDeletePreview` / `DataDeleteChild` / `DataReferenceOption` / `DataMutation` + 对应 repository 方法 |
| `MainViewModel.kt` | 表单/删除预览/引用候选/写入结果/编辑中词条状态；`submitDataMutation`（成功刷新检索与数据页、失败只进对话框）；新增/编辑/删除词条与行的封装 |
| `DataEditingDialogs.kt`（新） | `DataMutationEffect` 写入协议（成功关闭、失败保留输入并内联报错）、`DataFormDialog`（引用下拉、必填/长度校验）、`DataDeleteDialog`（影响预览+恢复点提示）、`DictionaryCreateWordDialog`、`SenseEditorCard`、`SenseAddDialog` |
| `DictionaryScreen.kt` | 检索区「+ 新增词条」；词条编辑统一走 VM（`dictionaryEditEntry`），支持保存/新增义项/删除义项/删除词条；数据行卡片按可写性显示「编辑/删除」（词头走策展编辑器，其余走 schema 表单 + 删除预览）；最后一个义项不可删（UI+后端双保险） |
| `DatabaseScreen.kt` | 旧写入口下线：移除新增/编辑/删除与全局搜索替换，保留浏览、维护动作、导出与分页；副标题改为「只读浏览 · 编辑已迁移到 词典 → 数据」 |
| 测试 | `test_data_editing.py` 22 条（DataCore / 策展服务 / bridge 三层 + 资产守卫）；CI 增加 `P2 data editing tests` 步骤 |

设计要点：

- **删除预览用「真删 + 回滚」计算**：预览在事务内执行同一条删除路径再 `ROLLBACK`，
  因此 FK 级联与声明式级联都被精确计入，且预览本身不改变数据库。
- **所有写入走 P0 的同一套守则**：只读表拒绝、字段/类型/长度/必填/唯一/引用校验、
  单事务、失败回滚、台账、成功后事件（翻译缓存）。
- 创建 `sentence_alignments` 时 `song_id`/`song_title` 是引用字段，表单通过
  `data_reference_options` 拉候选（最多 500 条），不再要求用户手输 id。

验收记录：

```pwsh
.\gradlew.bat :app:compileDebugKotlin :app:testDebugUnitTest    # BUILD SUCCESSFUL
cd app/src/test/python; $env:PYTHONPATH = '<repo>/app/src/main/python'
python -m unittest test_data_editing test_data_guard test_backup_restore test_dictionary_search  # 113 OK
python -m unittest test_database_versioning test_verify_published_database                       # 27 OK
```

端到端探针（真库副本）：表单元数据/删除预览/引用候选、通用增删改（只读拒绝、重复拒绝、
声明式外键防孤儿）、策展词条全生命周期（创建→检索可见→加义项→删义项→删词条）、
删除自动恢复点、最后义项保护、失败事务不留下半成品数据 —— 全部通过；
`translated.db` sha256 未变。

### P3 维护动作迁移 —— 已完成（2026-10-29，提交 28df84b / dd40db0 / 691927d）

| 项目 | 结果 |
|---|---|
| 唯一正文源 | `update_word_count.py` 从 `raw.lyric_raw` 改读 `songs.lyric`；`raw` 降级为只读存档 |
| 维护脚本加固 | 去掉 `synchronous=OFF` / `journal_mode=MEMORY`，改 `busy_timeout=5000` + `foreign_keys=ON`；统计写入显式单事务；逐词打印改 verbose-only |
| 维护恢复点 | bridge `_run_maintenance` 执行前自动创建恢复点，失败拒绝运行；服务重开即刷新翻译缓存 |
| no_class 收窄 | `DataCore.rebuild_no_class` 只重建 `no_class`（按 class 为空的义项按词去重、单事务、幂等），不再生成 13 张词性表 |
| 全局替换 | `data_replace_preview` / `data_replace_apply`：仅 6 张可写表、**区分大小写**子串（词库存在 `La`/`la` 变体，刻意如此）、预览门控、apply 前恢复点 |
| UI | 词典「数据」工作区「维护与导出」入口：重算词频 / 重建 no_class / 全局替换 / 导出 CSV(ZIP) / 导出 SQLite / 数据库诊断；DatabaseScreen 维护项全部迁走 |
| 验收 | 真库副本探针（a/Finz/Xia/end 词频与独立复算一致、替换 470 处仅 5 表、`raw` 未动）；`test_maintenance.py` 6/6；模拟器实测维护菜单与替换对话框（截图 10-12.png） |

### P4 数据库治理页 —— 已完成（2026-10-29，提交 335e62a / 8a2eab1）

| 项目 | 结果 |
|---|---|
| 前置修复 | 5 处 `with sqlite3.connect(...)` 只提交不关闭导致句柄泄漏，使 `atomic_replace_file` 在 Windows 报 WinError 5——恢复点回退与整库导入随机失败；新增 `_connect()` 上下文管理器 + `_close_services` 关闭写作单例连接（测试用 mutation 证明旧实现可复现失败） |
| `gov_identity` | 一次返回版本/发布时间/格式/sha256/大小/计数/本地修改数/恢复点数/最新恢复点 |
| 治理页 | `DatabaseGovernanceScreen`（830 行）五节：版本与身份、更新、恢复点与回退（创建/列表/恢复/恢复内置库）、发布（既有卡片与对话框迁入）、数据来源（上游检查/导入/导出） |
| 设置页 | 875→347 行，只保留一张「数据库」卡（副标题实时显示版本 + 本地修改数），点击进入治理页；启动更新弹窗不变 |
| 验收 | `test_governance.py` 6/6（含泄漏回归钉子）；全量 pytest 248 passed；模拟器实测五节渲染、创建恢复点成功并出现在列表（14-15.png） |

### P5 收尾 —— 进行中（2026-10-29，提交 88dc61b）

| 项目 | 结果 |
|---|---|
| 旧模块删除 | `DatabaseScreen.kt`（312 行）、`dbmanager_service.py`（136 行）、`db_*` 七个桥方法、`_table_page`、`classify_words` 维护分支；VM/Repo 旧面 9 个方法、`DbTablePage` 模型全部移除（净 −714 行） |
| 验证 | `compileDebugKotlin + testDebugUnitTest` BUILD SUCCESSFUL；六套件合跑 125 tests OK；`git grep` 确认旧符号零残留 |
| polish | 创建恢复点/恢复/恢复内置库的确认框不再复用通用恢复点提示，改为各自语义文案；三个发布对话框补 `Modifier.imePadding()` |
| 数据 bump（db v2） | 删除 12 张词性表 + 遗留 `test`/`Album1-3`/`Single`/`All_words`/`Unknown`（业务表 32→13）、删除 1 条孤儿译文行、VACUUM；`update_database_manifest.py --bump --tag v1.11.1` 写入库内 marker、追加台账、重写清单；体积 2,854,912→2,596,864 字节（−258,048）；台账 sha1 `81d9a576…`，资产 sha256 `ADDBEAE3…` |
| 数据验收 | `verify_database_versions.py` / `verify_database_manifest.py` OK；版本测试 27 OK；全量 pytest 248 passed；模拟器 v1→v2：治理页显示「v2 · 2026-10-29 · 1339/53/13 · 2.5 MB」，恢复内置库自动安全备份、无 FATAL（17.png） |
| 待办 | 推送/开 PR 时机由用户决定；推送后跑 `verify_database_versions.py --remote` 校验线上字节 |
