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
| **每次发布都必须由设备密钥签名（P2）** | [PublishSigningKey.kt](../app/src/main/java/com/meartraep/alician/mobile/data/PublishSigningKey.kt)、[verify_publication_signature.py](../scripts/verify_publication_signature.py) |

### P2：设备签名（已启用）

**解决了什么**：在此之前"令牌即信任"——拿到令牌的人推一个 `db-publish/*` 分支就能发布。
现在 CI 只接受用**登记在 main 上的公钥**对应的私钥签名的发布，而那把私钥
（Android Keystore，不可导出）永远不离开手机。

签名内容（两边实现必须逐字节一致，测试互相钉住）：

```
alician-db-publish-v1
prev_version=<签名时台账末条版本>
prev_sha1=<签名时台账末条 sha1>
version=<新版本>
sha1=<新数据库字节 sha1>
size=<字节数>
published_at=<发布日期>
notes_sha256=<版本说明的 sha256>
```

- 绑定 `prev_*` ⇒ **旧签名无法重放**（台账已前进，消息就对不上）。
- 绑定 `sha1`/`size` ⇒ 签名只对**这一份字节**有效。
- 绑定 `notes_sha256` ⇒ 有令牌的人也无法改写已签名发布的说明文字。
- 公钥**从目标分支读取**，发布 PR 不得修改它（不在白名单内）⇒ 攻击者不能"自带权威"。

设备侧细节：

- 私钥由 Android Keystore 生成（EC P-256 / SHA-256），不可导出。
- 设备设置了锁屏时，密钥额外要求**用户验证**后才能签名（签名前弹设备凭据确认），
  因此"捡到一台已解锁手机"也不足以发布；界面会显示当前是哪种模式。
- 密钥指纹（公钥 SPKI 的 sha256 前 16 位）会写进发布提交，CI 用它比对登记的公钥。

**一次性配置**：App → 设置 → 手机端发布 → 生成密钥 → 复制公钥 → 用**普通 PR** 把内容提交为
`.github/db-publish-pubkey.pem` 并合并。之后才能发布；换手机或删除密钥后需要重新登记。

**当前登记的密钥指纹**：`6324261ecd9114a0`（与 App 设置页显示的"密钥指纹"一致，才说明是同一把密钥）。
指纹是公钥 SPKI 的 sha256 前 16 位；更换密钥后请同步更新这一行。

凭证寿命部分见下一节 **P3**（GitHub App 设备流）：P2 管"谁有权发布"，P3 管"凭证多久失效"。

## 4. 运维要点

- **工作流必须先存在于 main**：`pull_request` 事件只运行基础分支上的工作流。
- 发布 PR 与普通 PR 使用同一套必需检查；若版本号不对，PR 会红，直接重发即可。
- 台账在你读取与 CI 校验之间被别人更新时，CI 会以"版本号必须是 last+1"拒绝，
  App 里重新点一次发布即可（bridge 也会先拒绝过期台账）。
- 令牌泄露或手机丢失：立刻在 GitHub 撤销该 token（设置页"清除令牌"只影响本机）。
  令牌泄露本身已不足以发布：缺少设备签名时 CI 会拒绝。
- 换手机 / 删除签名密钥后：重新生成并登记公钥（旧公钥随之替换），否则发布一律被拒。

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

## 6. P3：GitHub App 设备流（已实现，需一次性创建 App）

**解决了什么**：手机不再保存长期仓库凭证。之前是一个有效期数月的 fine-grained PAT；
现在是一个 **GitHub App**：手机上只留下**可轮换的刷新令牌**，访问令牌约 8 小时有效、
临近过期自动刷新（[GitHubDeviceFlow.kt](../app/src/main/java/com/meartraep/alician/mobile/data/GitHubDeviceFlow.kt)、
[PublishAuth.kt](../app/src/main/java/com/meartraep/alician/mobile/data/PublishAuth.kt)）。
在 GitHub 卸载该 App，**所有设备一次性失效**；权限也只有该 installation 授予的那些。

**与 P2 的关系（重要）**：两者解决不同问题，P3 **不能替代设备签名**。

| | 解决的问题 | 没有它会怎样 |
|---|---|---|
| P2 设备签名 | **谁有权发布内容** | 任何拿到有效令牌的人（哪怕只有 1 小时）都能发一版恶意数据库 |
| P3 GitHub App | **凭证的寿命与撤销面** | 手机上长期存在一个可用数月的仓库写凭证 |

因此发布仍然要求：目标分支上登记了公钥 + 每次发布由设备密钥签名。

### 创建 App（一次性，约 2 分钟）

1. 打开 <https://github.com/settings/apps/new>
2. **GitHub App name**：`Alician DB Publisher`（可自取，全局唯一）
   **Homepage URL**：`https://github.com/Meartraep/AlicianDictionaryMobile`
3. 取消勾选 **Active**（Webhook），不需要回调地址
4. **Repository permissions** → **Contents: Read and write**（其余保持 No access）
5. **Where can this GitHub App be installed?** → *Only on this account* → **Create GitHub App**
6. 创建后在该 App 页面：**Identifying and authorizing users** → 勾选 **Enable Device Flow** → **Save changes**
7. 同一页面点 **Install App** → 选择 `AlicianDictionaryMobile`
8. 复制页面上的 **Client ID**（公开信息，可以随便发）

然后：App → 设置 → 手机端发布 → **用 GitHub App 登录** → 填入 Client ID → 按提示在浏览器
输入用户码并批准。登录成功后卡片会显示"GitHub App（短时令牌，自动刷新）"。

已有的长期 PAT 仍然可用（作为回退）；切到 App 登录后可点"清除全部凭据"把 PAT 删掉。

### 仍未包含

- 中继服务（把 App 私钥放在服务端，设备完全不持有任何 GitHub 凭据）——当前设备流不需要它
- 提交者身份区分（发布提交署名仍是令牌所属账号）
- 多把在册公钥并行（当前替换公钥需要一次普通 PR）
