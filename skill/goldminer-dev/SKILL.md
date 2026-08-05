---
name: goldminer-dev
description: MOMANTIC GoldMiner 5.5.x 메인 엔진 개발·유지보수 전용 스킬 (사장님과 공동 고도화하는 정본). GoldMiner, 골드마이너, 뚜껑갈이(앤트가드·한스골드), 통문, 그라인딩, 돌려깎기, 레이어헷징, VT마켓 제재, §16 서버안전, 백테스트 A/B가 언급되거나 MQL5 EA 코드 수정·검증이 요청되면 반드시 사용. SHD 계보 스킬(goldminer-shd-dev)보다 이 스킬이 최신 — 충돌 시 이 스킬 우선.
---

# GoldMiner 개발 스킬 (우리 정본 · goldea 저장소 연동)

**정본 위치**: `D:\GitHub\goldea` — 이 스킬은 그 저장소의 색인이다. 코딩 전 반드시:
1. `docs/claude-import/gold/GOLD_INDEX.md` — 확정 파라미터(불가침)·검증 사다리·백로그
2. `agents/README.md` — 검증 에이전트 파이프라인 9종 (규정→결함이력→변경표→컨펌→패치→정적→시뮬→백테스트→반증)
3. `upgrade/backtest_20260805/` — 최신 라운드 감사 보고(3에이전트 검증·VT 트래픽 감사)

## 절대 규칙 (사장님 스타일)
- **설명 → 컨펌 → 코딩 → 검증 사다리.** 사장님 발의 개념은 복창(조문화) 후 진행. 판정 등급 [코드확인]/[데이터판독]/[추정] 필수 — 추정은 결론이 될 수 없다.
- **로컬 MT5 = 벤티지**(`D:\Apps\VantageMT5`, 데이터 `10E9E19F...`). XM은 모의계좌 차단으로 제외(파일 유지). 컴파일: `metaeditor64.exe /compile:"<mq5>" /log:"<log>"` 후 0 errors 확인.
- **정적 검증 세트**: 괄호 3종 균형(원본 대비 델타 0 — 절대값은 −4/−36/+1이 정상) / 신규 심볼 def=1·배선≥1 / bareLF·모지바케 불변 / CRLF 보존.
- **시뮬 하네스 함정**: MQL `TimeCurrent()`는 0 불가 — 파이썬 시뮬에서 t=0 시작은 센티널 충돌 오탐(8/5 실증). 에포크는 양수로.
- **라이브 투입은 A/B 백테스트(씨앗·대조군 필수) 통과 전 금지.** 신규 기능은 전부 인풋 게이트(A/B 가능하게) — FAR가 이 원칙을 놓쳤다가 8/5에 소급 수리됨.

## §16 서버신호 규율 (VT마켓 3회 차단의 교훈 — 2026-08-05 확정)
- **서버로 나가는 모든 호출(TP수정·청산 연쇄 포함)은 `CanSendOrder()` 확인 + `MarkSent()` 계수 경유.** 미경유 서버 호출은 코드 리뷰에서 결함으로 취급.
- **TP 수정 전 gTP 기통과 검사(FIX2/R1 동형) 필수** — 기통과면 수정 보류(INVALID_STOPS 반복 = 브로커가 보는 "비정상 주문 과다").
- ServerReady는 5축이어야 함(`ACCOUNT_TRADE_ALLOWED` 포함) — read-only 제재 중 노크가 재제재를 부른다.
- 감사 전문·수리 권고 9종·저널 판별 지문: `upgrade/backtest_20260805/VT_서버트래픽_감사_20260805.md`

## 고도화 프로토콜 (이 스킬을 키우는 법)
매 작업 라운드 종료 시:
1. 새로 확정된 조문·결함 교훈을 이 SKILL.md(간결 요지) + `docs/claude-import/gold/dev-notes/`(상세)에 추가
2. `tools/sync_skill.ps1` 실행 → 로컬 스킬 활성 사본 갱신
3. git commit (메시지에 라운드 요지) — 푸시는 GitHub Desktop [Publish/Push]
4. 진행 스냅샷(아래) 갱신 — 다음 세션이 여기서 재개한다

## 진행 스냅샷 (2026-08-05 r8 — 갱신할 것)
- 마스터: `src/mt5/GoldMiner_v5_5_5_internal_20260805.mq5` (r8, 벤티지 컴파일 0/0)
- 8/5 확정 반영: A2 · T-RE(18h=물림 나이·매직 무관) · P1(+집행부 대칭·회랑 존중) · FAR(UseFarTarget) · R1(gTP 기통과 정리)
  · E1/F1(★백테스트 미검증★) · **VT 수리 V1~V9**(ServerReady 5축·CRUSH §16·전 Modify 계수·미아 가드·PM 이식·수익청산 쿨·솔버 터미널 전면·주요 청산 계수·비터미널 150ms 중앙 간격 — 사장님 위임 "로직 무이슈면 적용" 하에 적용)
- V8 잔여(2차분·재판단 대상): LHEDGE Fire/CloseAllHedge/PlanExecute/MergeUpdate·WLU 계열 MarkSent 계수화, 원자 묶음 내부 per-leg CanSendOrder 게이트(집행 원자성 이슈), FLATCUT §16 게이트(주말 노출 위험 — 완주 우선 판단으로 미적용)
- 대기: ①A/B 백테스트(세트 준비됨) ②locked 소성 ③앤트가드 전파 ④VT 저널 지문 확인 후 재가동
- 미결 논점: F1 수리 범위, FAR 집행부 동조, E1×편입예산(mo), C1 위기 모집단 111 포함 여부
