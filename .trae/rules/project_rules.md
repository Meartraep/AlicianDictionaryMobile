# 项目规则

## 提交与推送：常规方式失败时直接改用 gh

用户要求提交 / 推送变更时：

1. 先用常规方式执行：`git add <files>` → `git commit -m "<conventional message>"` → `git push origin <branch>`。
2. 常规方式一旦失败，不要反复重试、也不要让用户手动处理，直接改用 `gh` CLI 兜底完成同一操作。失败情形包括但不限于：
   - 推送被拒 / 非快进、认证或代理报错、超时、网络不可达；
   - GitHub MCP 连接器报错（例如 `MCP tool invocation failed: list tools failed`）。
3. `gh` 兜底步骤：
   - `gh auth status` 确认已登录；
   - 推送：`gh auth setup-git` 后重试 `git push`，必要时用 `gh api` 兜底；
   - 创建 PR：`gh pr create --draft --fill --head $(git branch --show-current)`。
4. 兜底完成后，在回复中一并说明常规方式失败的原因。
