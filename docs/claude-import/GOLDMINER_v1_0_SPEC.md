# GOLD MINER v1.0 — 개발 스펙 문서

> **파일**: `GOLDMINER_v1_0_20260401.mq5` (~2,297줄)
> **플랫폼**: MetaTrader 5 (MQL5) | **심볼**: XAUUSD | **헤지 모드 필수**
> **브랜드**: Windsor Trader / seohakant.com
> **최종 수정**: 2026-04-02
> **베이스**: AntGuard Gold v1.5 → PROFIT No.05 → GOLD MINER

---

## 1. 프로젝트 개요

PROFIT No.05 (일간 5% 목표 후 정지) → GOLD MINER (1% 쿨다운 무한 반복) 확장.
AntGuard Gold v1.5 베이스 100% 유지. XAUUSD 전용 양방향 헤지 그리드 마틴게일.
"금 채굴기" 메타포 — BaseBalance의 1%를 1블럭으로, 블럭 달성 시 15분 쿨다운(COOLING) 후 무한 반복.
당일 청산 목적 — DayClose(GMT 18시) 이후 신규 차단, TradeStop(GMT 21시)까지 TP 자연 종료.

---

## 2. Input Parameters (13개)

### ⛏ 채굴 설정 (5개)
```
BaseLot          = 0.01       기본 로트
UseAutoLot       = true       복리 로트 ON/OFF
LotUnit          = 100000     복리 기준 금액 ($)
BaseBalance      = 20000.0    기준 잔고 ($) — 블럭 단가 계산용
MagicNumber      = 202604     매직넘버
```

### 💰 목표 설정 (5개)
```
UseDailyMine     = false      일간 목표 ON/OFF
DailyMineAmt     = 0.0        일간 목표 금액 ($) — 0=미사용
DailyMinePct     = 0.0        일간 목표 수익률 (%) — 0=미사용
UseHarvest       = false      총 목표 달성 시 영구 정지
HarvestAmt       = 1000.0     목표 자금 ($) — 잔고-크래딧 기준
```

### 🛡 안전장치 (3개)
```
UseCrushGuard    = false      손실 가드 ON/OFF
CrushPercent     = 30.0       손절 기준 (%) — 당일 시작잔고 대비
CommissionPerLot = 6.0        IB 수수료 ($/std lot)
```

---

## 3. 코드 내 상수 (25개 #define)

```
전략:    GRID_STEP=300  TAKE_PROFIT=300  HARD_MAX_LAYER=12  LOT_MULTIPLIER=1.5
감속:    PROG_MULT_L6=1.5  PROG_MULT_L9=2.0  PROG_MULT_L11=3.0
채굴:    COOLDOWN_PCT=1.0  COOLDOWN_MINUTES=15
시간:    USE_GMT=true  TRADE_START_HOUR=0  TRADE_STOP_HOUR=21  DAY_CLOSE_HOUR=18
뉴스:    USE_NEWS_GUARD=true  NEWS_MINS_BEFORE=30  NEWS_MINS_AFTER=30
ATR:     USE_ATR_GUARD=true  ATR_TRIGGER_RATIO=2.5  ATR_ABS_TRIGGER=2.0
         ATR_RESUME_RATIO=1.5  ATR_COOLDOWN_MIN=15
드리프트: USE_DRIFT_GUARD=true  DRIFT_BLOCK_USD=50.0  DRIFT_RESUME_USD=20.0
DD:      USE_DD_GUARD=false  MAX_DD_PERCENT=25.0
실행:    MAX_SPREAD=50  SLIPPAGE=30  MAX_RETRY=3
시스템:  DEBUG_LEVEL=1  DASH_INTERVAL=2
```

---

## 4. 기능별 동작

### 4.1 Gold Miner (블럭 채굴)
```
블럭 단가 = BaseBalance × COOLDOWN_PCT / 100
블럭 달성 → 15분 COOLING → 자동 재개 → 무한 반복
```

### 4.2 Daily Mine (일간 목표)
```
금액($) OR 수익률(%) 먼저 도달 시 발동
→ 신규 차단 → TP 대기 → 전부 종료 시 당일 정지 → 자정 자동 리셋
대시보드: "MINED +$1000" (녹색) / "MINED 2pos" (대기)
```

### 4.3 Harvest (총 목표)
```
기준: AccountBalance - AccountCredit (크래딧 제외)
→ 신규 차단 → TP 대기 → 영구 정지 (자정 리셋 안 됨)
대시보드: "HARVEST $20000" (골드) / "HARVEST 2pos" (대기)
```

### 4.4 Crush Guard (손실 한도)
```
당일 시작잔고 대비 Equity 손실률 >= CrushPercent(30%)
→ 전포지션 강제 청산 + 당일 정지 + 잔여 매 틱 재청산 → 자정 리셋
대시보드: "CRUSHED -$3000" (빨강)
```

### 4.5 Drift Guard (원웨이 감지)
```
기준: 당일 D1 시가 대비 현재가 편차 (USD, 브로커 무관)
★ iOpen(PERIOD_D1, 0) 사용 → 장중 재시작 시에도 동일 기준점
차단: |편차| >= $50 / 재개: |편차| < $20 (히스테리시스)
자정 리셋 (새 D1 시가 기준)
대시보드: "DRIFT -$85" / "DRIFT +$62" (골드)
```

### 4.6 News Guard (지표 방어)
```
MT5 CalendarValueHistory() — USD High-Impact 전후 30분 차단
30초 캐싱, 브로커 미지원 시 자동 비활성화
대시보드: "NEWS -28m" (골드)
```

### 4.7 ATR Guard (변동성 방어)
```
M1 ATR 14바 vs 480바(8시간) — ratio >= 2.5 OR abs >= 2.0 이중 체크
해제: 쿨다운(15분) + R OR A 정상 / 15분 후 무조건 강제 해제
대시보드: "QUAKE -15m" (골드)
```

### 4.8 GMT 자동 보정
```
매 틱 UpdateGMTHours() → TimeGMTOffset()으로 DST 자동 대응
Input GMT 기준 → g_srvStart/g_srvStop/g_srvClose 내부 변환
```

---

## 5. 대시보드 상태 우선순위 (12단계)

```
순위  상태              색상    리셋        의미
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 1   CRUSHED -$3000    빨강    자정        💀 손실 가드
 2   HARVEST $20000    골드    영구        💰 총 목표
 3   HARVEST 2pos      골드    영구        💰 총 목표 대기
 4   MINED +$1000      녹색    자정        💰 일간 목표
 5   MINED 2pos        녹색    자정        💰 일간 목표 대기
 6   COOLING -14m      사이언  자동        ⛏ 블럭 쿨다운
 7   DRIFT -$85        골드    가격복귀    ⚡ 원웨이
 8   CLOSE -90m        빨강    시간        🔒 장마감
 9   OFF -3h           빨강    시간        🔒 시간외
10   NEWS -28m         골드    시간        ⚡ 지표
11   QUAKE -15m        골드    자동        ⚡ 변동성
12   MINING            녹색    -           ✅ 정상
```

---

## 6. OnTick 실행 흐름

```
① UpdateGMTHours()
② News/ATR 가드 체크
③ Drift Guard 체크 (D1 시가 기준)
④ 일간 리셋 (자정: Drift/Crush/DailyMine/블럭 초기화)
⑤ 대시보드 갱신
⑥ TP 안전망 (5중 방어)
⑦ CalcDailyProfit + UpdateGoldMiner (Harvest/DailyMine/Cooldown)
⑧ harvestDone → return (영구)
⑨ dailyMinedDone → return (당일)
⑩ dailyCrushed → return (재청산)
⑪ crushCheck → return (발동)
⑫ spread → return
⑬ 시간 가드 → canTrade
⑭ canOpenNew (8개 조건)
⑮ ManageCycle (BUY/SELL)
```

### canOpenNew 조건
```
canTrade && !g_newsBlock && !g_atrBlock && !g_driftBlock
&& !g_gm_harvest && !g_gm_dailyMined
&& !g_gm_inCooldown && !g_gm_dayClosing
```

---

## 7. 자정 리셋 정리

| 항목 | 리셋 | 비고 |
|------|------|------|
| g_gm_dailyProfit | ✅ | 오늘 수익 |
| g_gm_cooldownUntil / inCooldown | ✅ | 쿨다운 |
| g_gm_blockCount | ✅ | 블럭 카운트 |
| g_gm_dailyMined / dailyMinedDone | ✅ | 다음날 재구동 |
| g_dailyCrushed / g_crushLossAmt | ✅ | 다음날 재구동 |
| g_dayOpenPrice / g_driftBlock | ✅ | 새 D1 시가 |
| g_gm_harvest / g_gm_harvestDone | ❌ | 영구 정지 |

---

## 8. 용어 체계

| 대시보드 | 코드 변수 | 의미 |
|---------|----------|------|
| MINING | (기본) | 정상 채굴 중 |
| COOLING | g_gm_inCooldown | 블럭 쿨다운 15분 |
| MINED | g_gm_dailyMined | 일간 목표 달성 |
| HARVEST | g_gm_harvest | 총 목표 달성 |
| CRUSHED | g_dailyCrushed | 손실 가드 발동 |
| DRIFT | g_driftBlock | 원웨이 감지 |
| NEWS | g_newsBlock | 지표 가드 |
| QUAKE | g_atrBlock | 변동성 가드 |

로그 태그: [MINE] [MINED] [HARVEST] [CRUSH] [DRIFT]

---

## 9. 대시보드 디자인

```
PW=222, PH=380, CORNER_RIGHT_LOWER
Gauge 반원: center y=114, R=40
수익률: C'255,130,50' 오렌지 Consolas Bold 20pt
제목: Georgia Bold 14pt 골드
테마: GOLD MINER (딥네이비 배경)
```

---

## 10. 버그 수정 이력 (13건)

| # | 위험도 | 버그 | 수정 |
|---|--------|------|------|
| 1 | 치명 | newsClr 항상 GREEN 덮어씌기 | else 중괄호 |
| 2 | 치명 | Drift _Point 브로커 의존 | USD 직접비교 |
| 3 | 치명 | Drift 시가 = 현재가 (재시작 버그) | iOpen(D1) |
| 4 | 중간 | Harvest dailyProfit 기준 | 잔고-크래딧 |
| 5 | 중간 | Harvest 자정 리셋됨 | 영구 정지 |
| 6 | 중간 | Crush 재청산 없음 | 매 틱 재시도 |
| 7 | 중간 | L_BI2 commTotal 중복 | next $X |
| 8 | 중간 | 바차트/구분선 겹침 | 위치 이동 |
| 9 | 중간 | "+-" 이중부호 | %+.1f 포맷 |
| 10 | 낮음 | Rig 배경 미커버 | 배경 확장 |
| 11 | 낮음 | 미사용 dayLabels | 제거 |
| 12 | 낮음 | gmPaused 누락 | dailyMinedDone/driftBlock 추가 |
| 13 | 낮음 | CRUSHED 금액 미표시 | g_crushLossAmt 표시 |

---

## 11. 빌드 정보
```
소스:    GOLDMINER_v1_0_20260401.mq5
줄 수:   ~2,297줄
의존성:  <Trade\Trade.mqh>
매직:    202604
심볼:    XAUUSD
```
