# Alician Dictionary Mobile

[English](./README.en.md) | **简体中文**

爱丽丝语词典 Lite 的 Android 原生移动版（Android 7.0+）。

## 架构

- Kotlin 与 Jetpack Compose Material 3 用户界面。
- 基于 Chaquopy 承载的 Python 业务层，复用 Lite 版的词典、写作检查和
  双向翻译算法。
- 私有可写 SQLite 数据库，由内置的 `translated.db` 初始化。
- 使用 Storage Access Framework 导入/导出：无需宽泛的存储权限。

## 构建

在 `local.properties` 中设置 `sdk.dir`，然后运行：

```powershell
.\gradlew.bat testDebugUnitTest lintDebug assembleDebug
```

如需签名发布版，请根据 `app/build.gradle.kts` 中引用的密钥创建
`keystore.properties`，然后运行 `.\gradlew.bat assembleRelease`。

## 可验证的发布

推送 `v*` 标签后，GitHub 托管的 runner 会构建签名 APK，并为最终 APK 发布
Sigstore 签名的 SLSA 构建溯源凭证。仓库密钥配置、发布流程以及严格的消费者
验证方式详见 [`docs/SUPPLY_CHAIN.md`](docs/SUPPLY_CHAIN.md)。

## 语义别名数据

可选的翻译增强功能使用离线生成的、经过人工审核的中文别名；Android 运行时
不附带也不加载 text2vec 模型。在开发用 Python 环境中安装 `text2vec` 与
`jieba` 后，可从固定版本的本地模型重新生成内置数据集：

```powershell
python scripts\generate_semantic_aliases.py `
  --db app\src\main\assets\translated.db `
  --model-path C:\path\to\text2vec-base-chinese `
  --model-name shibing624/text2vec-base-chinese `
  --model-revision <pinned-revision> `
  --dry-run
```

仅在审阅完建议的别名-义项映射后，才移除 `--dry-run`。生成器会将模型、
Jieba 词典、阈值以及词典指纹记录在 `semantic_alias_metadata` 中。

## 归属与许可证

基于 `Meartraep/Alician_dictionary`，采用 CC BY-NC-SA 4.0 许可。
内置的爱丽丝语词典数据保留原始署名及非商业使用限制。爱丽丝语字体与应用
美术资源复制自源项目，以保证应用兼容性。

---

如需查阅英文版本，请点击 [English](./README.en.md)。
