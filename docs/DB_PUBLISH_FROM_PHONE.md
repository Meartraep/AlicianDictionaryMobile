# 手机端发布数据库

在手机上把本地数据库发布为新的数据库版本，并直接走 GitHub 合并流程。
本文件描述当前实现（方案 C：**手机盖章、CI 只校验**）、安全边界与运维要点。

版本契约见 [DATABASE_VERSIONING.md](DATABASE_VERSIONING.md)。

## 1. 谁负责什么

| 角色 | 职责 |
|---|---|
| 手机 | 读已发布台账 → 取 `last+1` → 把版本号写进**数据库副本**的 marker → 追加 `database-versions.json` → 重写 `database-manifest.json` → 用**自己的身份**一次提交这三个文件到 `db-publish/<UTC 时间戳>` 并开 PR |
| CI（Verify database published from phone） | 只校验：路径白名单、台账只能是"基线 + 恰好一条"且版本号必须是 `last+1`、sha1/size 必须等于上传的字节、库内 marker 必须等于该版本、manifest 必须是该条目的投影 |
| CI（Ledger, manifest and database agree） | 通用不变式（历史台账、清单投影、仓库内数据库与台账一致），**必需状态检查** |
| 你 | 检查通过后合并 PR |
| 客户端 | 下次启动读到新清单，提示下载；下载后校验 sha1 与库内 marker 才安装 |

两个关键性质：

1. **手机不能自定义版本号**：CI 会拒绝任何不是 `last+1` 的版本，也会拒绝改写历史台账。
2. **CI 不写仓库**：发布提交由真人身份的令牌推送，因此不产生 `action_required`（需人工放行）
   的挂起运行，PR 的必需检查会正常变绿——这是从"CI 盖章"换成"手机盖章"的直接原因。

## 2. 使用步骤

1. 在 GitHub 创建 **fine-grained token**：只授权 `Meartraep/AlicianDictionaryMobile`，
   权限只勾 **Contents: Read and write**，有效期选最短（如 30/90 天）。
2. App：设置 → 手机端发布 → 配置令牌 → 粘贴 → 保存并校验
   （用 `GET /repos/{repo}` 校验并确认具备 push 权限）。
3. 修改数据库（歌词/词条维护等），回到设置 → 发布新版本：
   - 预检：显示本地版本、大小、"将发布为 vN"、本地与已发布指纹；完全一致会直接拦住；
   - 填写版本说明（会写进台账/清单，并显示在所有用户的更新提示里）；
   - 上传 → 自动开 PR（三个文件一次提交）。
4. 等 **Ledger, manifest and database agree** 变绿，点"合并"。

## 3. 安全设计

| 措施 | 实现位置 |
|---|---|
| 只允许改数据库与台账/清单三个路径 | CI 的 `--changed-files` 白名单，越界即失败 |
| 版本号必须正好是 `last+1`、历史台账不可改写、sha1 唯一 | [verify_published_database.py](../scripts/verify_published_database.py)、[database_versioning.py](../scripts/database_versioning.py) |
| 版本号由手机写入副本，**不改动用户自己的数据库** | bridge `prepare_database_publication`（SQLite backup API 生成一致快照） |
| 令牌不明文落盘：Android Keystore 生成不可导出密钥，AES-GCM 加密后存独立首选项文件 | [PublishCredentialStore.kt](../app/src/main/java/com/meartraep/alician/mobile/data/PublishCredentialStore.kt) |
| 令牌不随备份外流：`alician_publish.xml` 已从云备份与设备迁移中排除 | [backup_rules.xml](../app/src/main/res/xml/backup_rules.xml)、[data_extraction_rules.xml](../app/src/main/res/xml/data_extraction_rules.xml) |
| 令牌只在内存中短暂解密，界面仅显示前缀后缀 | [PublishLogic.maskToken](../app/src/main/java/com/meartraep/alician/mobile/data/PublishLogic.kt) |
| 发布前本地预检 + 指纹对比，避免误发"没有改动"的库 | [PublishLogic.buildPreview](../app/src/main/java/com/meartraep/alician/mobile/data/PublishLogic.kt) |
| 只能写临时分支，不能写 main / tag | GitHub ruleset `Main_prot`（deletion、non_fast_forward、pull_request、required_status_checks） |
| 发布后线上字节与台账比对 | release 流水线的 `--remote` 校验 |

### 仍存在的风险（P2 要解决）

**令牌即信任**：拿到令牌的人可以推一个 `db-publish/*` 分支并开 PR。CI 会拒绝不一致的
版本号与越界路径，但**无法判断内容是不是你写的**。P2 用 Android Keystore 里不可导出的
签名密钥给发布请求签名，CI 验签后才接受；P3 再把长期令牌换成 GitHub App 短时令牌。

## 4. 运维要点

- **工作流必须先存在于 main**：`pull_request` 事件只运行基础分支上的工作流。
- 发布 PR 与普通 PR 使用同一套必需检查；若版本号不对，PR 会红，直接重发即可。
- 台账在你读取与 CI 校验之间被别人更新时，CI 会以"版本号必须是 last+1"拒绝，
  App 里重新点一次发布即可（bridge 也会先拒绝过期台账）。
- 令牌泄露或手机丢失：立刻在 GitHub 撤销该 token（设置页"清除令牌"只影响本机）。

## 5. 必需状态检查

规则集 `Main_prot`（`~DEFAULT_BRANCH`）已把 **Ledger, manifest and database agree** 设为必需，
由 [github_ruleset_required_check.py](../scripts/github_ruleset_required_check.py) 管理：

```bash
python scripts/github_ruleset_required_check.py --status   # 查看
python scripts/github_ruleset_required_check.py --add      # 启用（当前状态）
python scripts/github_ruleset_required_check.py --remove   # 取消
```

用脚本而不是页面：GitHub 规则集"添加检查"的下拉列表来自最近运行过的检查并带缓存，常搜不到。

该工作流在**所有 PR** 上都会报告（这是必需的：带 `paths` 过滤的检查在"未触及数据库"的 PR 上
永远不会出现，PR 会卡在 *Expected — Waiting for status to be reported*）。每次 PR 约 20 秒。

## 6. 未包含（P2/P3）

- 设备签名与验签（P2）
- GitHub App 短时令牌 / 中继服务（P3）
- 提交者身份区分（当前用令牌所属账号；P3 可换成专用机器账号）
