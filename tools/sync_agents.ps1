# 개발 에이전트 활성화 스크립트
#
# 이 레포의 agents\ 를 .claude\agents\ 로 복사한다.
# agents\ 가 정본(git 추적 대상)이고, .claude\agents\ 는 클로드가 읽는 활성 사본이다.
#
# 사용법: 레포 루트에서
#   powershell -ExecutionPolicy Bypass -File .\tools\sync_agents.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$src      = Join-Path $repoRoot "agents"
$dst      = Join-Path $repoRoot ".claude\agents"

if (-not (Test-Path $src)) {
    Write-Host "[실패] 정본 폴더가 없습니다: $src" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $dst | Out-Null

$files = Get-ChildItem -Path $src -Filter *.md
foreach ($f in $files) {
    Copy-Item $f.FullName -Destination $dst -Force
    Write-Host ("  복사  " + $f.Name)
}

Write-Host ""
Write-Host ("[완료] " + $files.Count + " 개 파일 → " + $dst) -ForegroundColor Green
Write-Host "이 폴더에서 클로드를 실행하면 에이전트가 로드됩니다."
