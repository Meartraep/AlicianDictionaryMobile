# 数据库版本唯一性（DATABASE VERSIONING）

本文件是"数据库版本号"这一改动的**契约**：它规定版本号的含义、必须成立的不变式、
以及这些不变式由哪些机器检查来强制。任何发布数据库内容的人都必须遵守这里的流程。

## 1. 为什么需要它

App 通过对比"本地数据库版本"与"GitHub 上发布的版本"来决定是否提示更新：

- 本地版本 = 数据库自带的 `database_metadata.db_version`（随文件走，用户导入/恢复内置库时自动跟着变）；
- 远端版本 = 仓库根目录 `database-manifest.json` 里的 `db_version`。

只有 `远端 > 本地` 才会提示（[DatabaseUpdateLogic](app/src/main/java/com/meartraep/alician/mobile/data/DatabaseUpdateLogic.kt)）。
因此一旦"内容变了但版本号没变"，老用户就**永远不会收到更新**，而且完全静默——
这是本机制要防的头号故障。

## 2. 三个身份，各司其职

| 名称 | 位置 | 含义 |
|---|---|---|
| `db_version` | 库内 `database_metadata` + 清单 + 台账 | **发布基线**的编号：严格递增的正整数，永不重用 |
| `sha1` / `size` | 清单 + 台账 | **确切字节**的身份：一个版本号只能对应一份字节内容 |
| `database-versions.json` | 仓库根目录 | **追加式台账**：记录曾经发布过的每一个版本 |

台账条目：

```json
{
  "db_version": 1,
  "sha1": "5f5cb1389bae746327ce385b2f5b7d6c010aff82",
  "size": 2854912,
  "published_at": "2026-10-14",
  "app_tag": "v1.9.0",
  "notes": "官方日/英译逐句对齐：…"
}
```

清单 `database-manifest.json` 是**台账末条的投影**（由脚本生成，不手改）。

## 3. 不变式

1. `db_version` 为正整数，严格递增，**永不复用**。
2. 一个 `db_version` ↔ 一份字节内容（一个 `sha1`）；`sha1` 也不得重复。
3. 仓库中 `app/src/main/assets/translated.db` 必须**恰好等于**台账末条（大小 + sha1 + 库内 marker + 发布日期）。
4. `database-manifest.json` 必须等于台账末条的投影。
5. 发布到 GitHub 的字节必须等于台账记录的字节（发布后由 CI 校验）。
6. App 只安装"库内 marker 与清单版本一致"的下载文件，且只接受严格更高的版本。

## 4. 发布一个新数据库版本

```bash
# 1) 修改 app/src/main/assets/translated.db（例如重新生成译词）
python scripts/realign/assemble.py
python scripts/realign/write_db.py --apply

# 2) 一条命令完成：写入库内 marker → 追加台账 → 重写清单 → 自检
python scripts/update_database_manifest.py --bump --tag v1.9.1 --notes "本次改了什么"

# 3) 本地校验（含线上字节，推送后执行）
python scripts/verify_database_versions.py
python scripts/verify_database_versions.py --remote
```

查看当前状态：`python scripts/update_database_manifest.py --status`

### 脚本会拒绝的情况

| 情况 | 结果 |
|---|---|
| 内容变了但没加 `--bump` | 退出码 **2**，提示必须用 `--bump --tag` 发布 |
| 内容没变却 `--bump` | 退出码 **1**（两个版本号对应同一内容是被禁止的） |
| 库内 marker 高于台账末条 | 退出码 **1**，要求先补记台账或回退 marker |
| 台账出现重复版本号 / 重复 sha1 / 非递增 | 退出码 **1**（校验脚本同样报错） |
| 清单与库不一致 | 退出码 **1** |

## 5. 强制手段（不靠自觉）

| 检查 | 位置 | 时机 |
|---|---|---|
| `verify_database_manifest.py` + `verify_database_versions.py` + `update_database_manifest.py`（拒错模式） | [verify-database.yml](.github/workflows/verify-database.yml) | 每次 push/PR 触碰数据库或清单相关文件 |
| 同上三步 | [release-slsa.yml](.github/workflows/release-slsa.yml) | **打 tag 构建前**：不一致就发不出 APK |
| `--remote` 线上字节比对 | release-slsa.yml 末尾 | 发布完成后 |
| 12 项 Python 单测（含"拒错"演练） | [test_database_versioning.py](app/src/test/python/test_database_versioning.py) | 两个工作流都会跑 |
| 下载后校验库内 marker == 清单版本 | [PythonRepository.kt](app/src/main/java/com/meartraep/alician/mobile/data/PythonRepository.kt) + [mobile_bridge.py](app/src/main/python/mobile_bridge.py) | 用户点"立即更新"时 |

于是"忘记 bump"不再是静默风险，而是 **CI 红灯**。

## 6. 运行时行为与边界

- 下载会校验 `size` + `SHA-1`（[PythonRepository.kt](app/src/main/java/com/meartraep/alician/mobile/data/PythonRepository.kt)），
  再校验库内 marker 与清单一致，任一不符即取消更新并保留原库。
- 只升不降：远端版本不高于本地时不提示；`稍后` 只抑制该版本，出现更高版本会再次提示。
- 用户手动改库（歌词编辑、导入导出）**不会**改变 `db_version`：版本号描述的是**发布基线**，
  文件哈希描述的是**确切字节**。用户改动后哈希与清单不再相等是预期现象，不影响更新判断。

## 7. 已知边界

- `main` 被强推或 tag 被移动时，raw 链接的内容会变；这属于仓库权限问题，建议开启分支保护与 tag 保护。
  即便发生，App 的 SHA-1 校验也会拒绝安装不一致的内容（失败关闭）。
- 台账只覆盖**本仓库发布的 Lite 数据库**；上游 `Alician_dictionary` 全量库是另一套数据，
  其导入入口在设置页单独提供，不参与版本号体系。
