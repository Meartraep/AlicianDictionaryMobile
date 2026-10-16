# 手机端发布数据库（P1）

在手机上把本地数据库发布为新的数据库版本，并直接进入 GitHub 的合并流程。
本文件描述已落地的 P1、安全边界，以及后续 P2/P3 要补的部分。

相关契约见 [DATABASE_VERSIONING.md](DATABASE_VERSIONING.md)。

## 1. 谁负责什么

| 角色 | 职责 |
|---|---|
| 手机 | 只上传一个文件：本地 `translated.db`，推到 `db-publish/<UTC 时间戳>` 分支并开 PR |
| CI（Publish database from phone） | 拒绝白名单之外的改动；从台账取 `last+1` 作为新版本；把版本写进库内 marker、追加 `database-versions.json`、重写 `database-manifest.json`；跑完全部不变式校验 |
| 你 | 看到检查通过后合并 PR（或在 GitHub 上开启 auto-merge） |
| 客户端 | 下次启动读到新清单，提示下载；下载后校验 sha1 与库内 marker 才安装 |

**手机永远不能决定版本号**，因此"忘记 bump / 版本重复 / 版本回退"在客户端不可能发生。

## 2. 使用步骤

1. 在 GitHub 创建 **fine-grained token**：只授权 `Meartraep/AlicianDictionaryMobile`，
   权限只勾 **Contents: Read and write**，有效期选最短（如 30/90 天）。
2. App：设置 → 手机端发布 → 配置令牌 → 粘贴 → 保存并校验（会用 `GET /repos/{repo}` 校验并确认具备 push 权限）。
3. 修改数据库（歌词/词条维护等），回到设置 → 发布新版本：
   - 预检：显示本地版本、大小、本地与已发布指纹；若完全一致会直接拦住（没有可发布的改动）；
   - 填写版本说明（会出现在清单与所有用户的更新提示里）；
   - 上传 → 自动开 PR。
4. 等 CI 把"Stamp the uploaded database"跑绿（它会写入版本号并校验），然后点"合并"；
   也可以用"检查状态"查看 PR 状态。

## 3. 安全设计（P1 已实现）

| 措施 | 实现位置 |
|---|---|
| 只允许改数据库与台账/清单三个路径 | CI 的 `--changed-files` 白名单，越界即失败 |
| 版本号服务端分配、单调递增、sha1 唯一 | [publish_database_from_branch.py](../scripts/publish_database_from_branch.py) + 台账校验 |
| 令牌不明文落盘：Android Keystore 生成不可导出密钥，AES-GCM 加密后存独立首选项文件 | [PublishCredentialStore.kt](../app/src/main/java/com/meartraep/alician/mobile/data/PublishCredentialStore.kt) |
| 令牌不随备份外流：`alician_publish.xml` 已从云备份与设备迁移中排除 | [backup_rules.xml](../app/src/main/res/xml/backup_rules.xml)、[data_extraction_rules.xml](../app/src/main/res/xml/data_extraction_rules.xml) |
| 令牌只在内存中短暂解密，界面仅显示前缀后缀 | [PublishLogic.maskToken](../app/src/main/java/com/meartraep/alician/mobile/data/PublishLogic.kt) |
| 发布前本地预检 + 指纹对比，避免误发"没有改动"的库 | [PublishLogic.buildPreview](../app/src/main/java/com/meartraep/alician/mobile/data/PublishLogic.kt) |
| 只能写临时分支，不能写 main / tag | GitHub ruleset（Main_prot / Main_protect：deletion、non_fast_forward、pull_request） |
| 发布后线上字节与台账比对 | release 流水线的 `--remote` 校验 |

### 仍存在的风险（P2 要解决）

**令牌即信任**：拿到令牌的人（例如手机被解锁后读取到解密后的令牌，或在别处泄露）
可以推一个 `db-publish/*` 分支并开 PR，CI 会照常为它分配版本号。
P1 的边界是"能写这个仓库的分支"，而不是"能发布任意内容"。

P2 的做法：用 Android Keystore 生成**不可导出**的签名密钥，手机在 PR 里附带
"prev_version + prev_sha1 + new_sha1 + 时间戳"的签名，CI 用仓库里的公钥验签后才 stamp，
被盗令牌无法伪造签名；P3 再把长期令牌换成 GitHub App 的短时 installation token。

## 4. 运维要点

- **工作流必须先存在于 main**：`pull_request` 事件只运行**基础分支**上的工作流，
  所以第一次上线时要先把这个 PR 合并，之后手机端发布才会被处理。
- 发布 PR 上 `Verify database versioning` 会被跳过（它面对的是"尚未 stamp 的库"，
  必然不通过）；真正的门禁是发布流水线自己的校验，且它会在 stamp 后
  用 `workflow_dispatch` 重新触发一次版本校验（`GITHUB_TOKEN` 推送不会触发工作流，
  而 `workflow_dispatch` 是例外）。
- 建议在 ruleset 里把 `Ledger, manifest and database agree` 设为 required check；
  若要开 auto-merge，请先上 P2 的签名门禁，否则被盗令牌即可自动发布。
- 令牌泄露或手机丢失：立刻在 GitHub 撤销该 token（设置页"清除令牌"只影响本机）。

## 5. 未包含（P2/P3）

- 设备签名与验签（P2）
- GitHub App 短时令牌 / 中继服务（P3）
- 提交者身份区分（当前用令牌所属账号；P3 可换成专用机器账号）
