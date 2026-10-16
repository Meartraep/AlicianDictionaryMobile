$ErrorActionPreference = 'Continue'
$env:GIT_TERMINAL_PROMPT = '0'
Write-Output '=== gradle confirm ==='
.\gradlew.bat :app:testDebugUnitTest :app:lintRelease :app:assembleRelease --console=plain 2>&1 | Select-Object -Last 2
$branch = 'feat/phone-stamps-database-version'
git checkout -b $branch 2>&1 | Select-Object -First 1
git add -A -- .github/workflows app/src/main scripts docs/DB_PUBLISH_FROM_PHONE.md app/src/test/python
git reset -q scripts/_msg_c.txt 2>&1 | Out-Null
git status --porcelain=v1 | Where-Object { $_ -notmatch '^\?\?' } | Select-Object -First 24
git commit -q -F scripts/_msg_c.txt
Write-Output ("commit exit=" + $LASTEXITCODE)
git log --oneline -1
$pushed = $false
for ($i = 1; $i -le 8; $i++) {
  gh auth setup-git 2>&1 | Out-Null
  git push -u origin $branch 2>&1 | Select-Object -Last 1
  if ($LASTEXITCODE -eq 0) { $pushed = $true; break }
  Write-Output ("push attempt " + $i + " failed"); Start-Sleep -Seconds 12
}
Write-Output ("pushed=" + $pushed)
if ($pushed) {
  gh pr create --base main --head $branch --title "改为手机盖章、CI 只校验" --body "手机读取已发布台账取 last+1，把版本写进数据库副本并提交数据库/台账/清单三个文件；CI 不再推提交，只校验版本号必须是 last+1 且路径在白名单内。这样发布 PR 的必需检查能正常变绿，不再出现 action_required 导致的 BLOCKED。" 2>&1 | Select-Object -Last 1
  Start-Sleep -Seconds 25
  Write-Output '=== waiting for the required check ==='
  $ok = $false
  for ($i = 1; $i -le 16; $i++) {
    $line = gh pr checks 2>&1 | Select-String -Pattern 'Ledger, manifest and database agree'
    Write-Output ("poll " + $i + ": " + ($line -join ' | '))
    if ($line -match '\tpass\t') { $ok = $true; break }
    if ($line -match '\tfail\t') { break }
    Start-Sleep -Seconds 15
  }
  Write-Output ("check_passed=" + $ok)
  if ($ok) {
    gh pr merge --squash --delete-branch --subject "feat(publish): 改为手机盖章、CI 只校验 (#23)" 2>&1 | Select-Object -Last 1
  }
  gh api repos/Meartraep/AlicianDictionaryMobile/commits/main --jq '.sha[0:12]' 2>&1
}
