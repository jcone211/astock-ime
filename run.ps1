# astock-ime 一键刷新（PowerShell）
#   .\run.ps1              # 等价于 python build.py all
#   .\run.ps1 build --limit 3000
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$UserArgs)

$ErrorActionPreference = 'Stop'
$py = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }

if (-not $UserArgs -or $UserArgs.Count -eq 0) { $UserArgs = @('all') }

Write-Host ">> $py build.py $($UserArgs -join ' ')" -ForegroundColor Cyan
& $py "$PSScriptRoot\build.py" @UserArgs
if ($LASTEXITCODE -ne 0) { throw "构建失败（退出码 $LASTEXITCODE）" }

Write-Host "`n产物目录：$PSScriptRoot\dist" -ForegroundColor Green
