# 우리 전용 스킬 동기화 스크립트
#
# 레포의 skill\ 를 사용자 스킬 폴더(%USERPROFILE%\.claude\skills\)로 복사한다.
# skill\ 이 정본(git 추적)이고, .claude\skills\ 는 클로드가 읽는 활성 사본이다.
#
# 사용법: powershell -ExecutionPolicy Bypass -File .\tools\sync_skill.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$src      = Join-Path $repoRoot "skill"
$dst      = Join-Path $env:USERPROFILE ".claude\skills"

if (-not (Test-Path $src)) {
    Write-Host "[실패] 정본 폴더가 없습니다: $src" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $dst | Out-Null

$dirs = Get-ChildItem -Path $src -Directory
foreach ($d in $dirs) {
    $target = Join-Path $dst $d.Name
    New-Item -ItemType Directory -Force -Path $target | Out-Null
    Copy-Item (Join-Path $d.FullName "*") -Destination $target -Recurse -Force
    Write-Host ("  동기화  " + $d.Name)
}

Write-Host ""
Write-Host ("[완료] " + $dirs.Count + " 개 스킬 → " + $dst) -ForegroundColor Green
Write-Host "다음 클로드 세션부터 스킬이 로드됩니다."
