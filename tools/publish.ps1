# 把本地仓库推到 GitHub（作者自用的一键脚本）
#   1. 从 SSH 认证信息里读出 GitHub 用户名
#   2. 仓库不存在时打开新建页面，建好后按回车
#   3. 加 remote 并 push
param(
    [string]$Repo = "ddl-widget",
    [string]$User = "",
    [switch]$Check
)

# 注意：这里不能用 Stop —— ssh / git 往 stderr 写东西会被当成异常
$ErrorActionPreference = "Continue"
Set-Location (Split-Path -Parent $PSScriptRoot)

if (-not (Test-Path ".git")) {
    Write-Host "[x] 当前目录不是 git 仓库" -ForegroundColor Red
    exit 1
}

if (-not $User) {
    $out = (ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -T git@github.com 2>&1 | Out-String)
    if ($out -match "Hi ([^!]+)!") {
        $User = $Matches[1]
    } else {
        Write-Host "[x] GitHub SSH 认证失败。先执行一次：ssh -T git@github.com" -ForegroundColor Red
        exit 1
    }
}

$remote = "git@github.com:$User/$Repo.git"
Write-Host "GitHub 用户 : $User"
Write-Host "目标仓库    : $remote"

$hasRemote = $false
git remote get-url origin 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) { $hasRemote = $true }

if ($Check) {
    Write-Host "[检查模式] 已配置 origin: $hasRemote"
    exit 0
}

if (-not $hasRemote) {
    git ls-remote $remote 2>$null | Out-Null
    $exists = ($LASTEXITCODE -eq 0)

    if (-not $exists) {
        Write-Host ""
        Write-Host "仓库还不存在，正在打开新建页面（名字填 $Repo，不要勾 README / .gitignore / license）" -ForegroundColor Yellow
        Start-Process "https://github.com/new?name=$Repo"
        Read-Host "建好后按回车继续"
    }
    git remote add origin $remote
}

git push -u origin main
if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[ok] 已推送: https://github.com/$User/$Repo" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[x] 推送失败，看上面的报错" -ForegroundColor Red
    exit 1
}
