# GoldMiner v5.4.1 — 규정 6-4 [L1 동반 원칙] 개발명세서

- 베이스: `GoldMiner_v5_4_0_{internal,locked}_20260714.mq5`
- 산출: `GoldMiner_v5_4_1_{internal,locked}_L1PAIR.mq5`
- 상태: 정적검증 PASS · 행동시뮬 11/11 PASS · **F7 컴파일 및 백테스트 대기**
- 매직 202604 보존 / CRLF 보존 / 로직 외 변경 0

---

## 1. 확정 조문 (사장님 확정 2026-07-15)

> **[규정 6-4 · L1 동반 원칙]**
> 1. **대상 범위**: 사이클의 **기본랏(L1)과 그 다음 진입(L2)** 만 해당.
> 2. **금지**: L1이 살아 있으면 **L1 단독 소각 금지** — L2까지 같은 묶음으로 동시 청산.
> 3. **게이트 미달 시**: **발사 보류.** 가격이 올라와 L1+L2 처리 자금이 충분해지는 순간 **한 번에** 쏜다.
> 4. **상한 아님**: 기본 기준(탐욕 확장)대로 **L1+L2+L3을 한 번에 날려도 된다.** 2장은 하한.
> 5. **적용 종료**: L1·L2가 제거된 뒤에는 무관 — 잔여가 1장이든 3장이든 기존 탐욕 확장.
> 6. **철회 조건**: **생존 다리 4개 이하면 규칙 철회**, 그 전까지 유지. **청산된 다리는 계산 제외**(0).

**근거(사장님)**: 같은 연료로 L1(0.01)만 태우면 L1+L2(0.03)를 태울 수 있었던 기회를 버리는 것 —
연료로 쓰는 자금 대비 리스크 감소가 목적. 두 번에 나눠 쏠 것을 한 번에.

**실증(7/14 라이브 Eric 500054, C2740 buy)**: 연료 $70.15로 부채 $33.42만 제거 = 효율 0.48.
L1+L2였으면 $65.90 = 효율 0.94. 4시간 동안 1:1 페어 3회(22:23 / 22:45 / 02:34).

---

## 2. 변경표 (확정 실행분)

| # | 위치 | 변경 | 조문 |
|---|---|---|---|
| **G2** | `[SECTION 1]` const, L1010 | `const int GRIND_L1_RULE_MIN_LEGS = 4;` 신설 (0 = 규칙 끔) | 6항 |
| **G1** | `Grind_Try` L6291~6318 (`if(burned <= 0 \|\| gTP <= 0)` **앞**) | 탐욕 확장 종료 후 후처리 검증 → 조건 성립 시 `return false` (쿨다운 미기록 = 다음 틱 즉시 재시도) | 2·3항 |
| **G4** | `XGrind_PickTarget` L5624~5630 | `l1Rule` 산출 + 타깃 선정 루프에 `L1·L2 스킵` 1줄 | 2항 (우회 봉쇄) |

**G1 발동 조건 (전부 AND)**
```
GRIND_L1_RULE_MIN_LEGS > 0
&& n > GRIND_L1_RULE_MIN_LEGS        // 6항 철회① — n = Grind_Collect 반환 = 생존 다리 수
&& bufferLayer != 2                  // 철회② — L2가 완충이면 구조상 불가 → 영구 보류 방지
&& bundle에 L1 포함
&& legs에 L2 생존
&& bundle에 L2 미포함
→ return false (발사 보류)
```

**철회된 것**: **G3(`Grind_Eligible` 수정) — 실행 안 함.**
사유: `XGrind_Arm`의 양보 검사 `Grind_Eligible(fdir, fState)` 는 **연료측** 자격만 본다.
타깃측 보류는 XGrind를 막지 않으므로 **교착이 성립하지 않는다.** 남은 소비처
`LHEDGE_GrindBurn`(L15132)은 양보하는 게 **맞다** — 연료가 `g_trade` 정규 그리드 수익
다리(L15217)라, 양보를 풀면 셀프가 L1+L2용으로 아끼는 연료를 뺏는다.

---

## 3. 간섭 검수 — 전 청산 경로 30곳 전수

| 함수 | 그리드 L1 접근 | 판정 |
|---|---|---|
| `Grind_Try` | 대상 | **G1 적용** |
| `XGrind_PickTarget` / `XGrind_Monitor` | 타깃 = 최고참 = L1, 통째 청산 | **G4 적용** |
| `LHEDGE_Fire` L14822/14826 | 물린측 최고참 FIFO 연쇄 (`g_trade`) | 🟡 **미결 — 아래 5장** |
| `CloseProfitPositions` L5267 | `layerCount>=2 return` + 수익 다리만 | 무관 |
| `LHEDGE_PairClose` L15101 / `LHEDGE_ComboExit` L15307 | 연료 = 그리드 **수익** 다리만, 손실 불가침 | 6-4 무관 (연료 경합은 기존 동작) |
| `OverCap_Grind_Try` L6508/6509 | 대상·연료 모두 `layer > g_maxLayer`(L13+) | 무관 |
| `RecalcAndModifyGroupTP` / `VerifyAndFixGroupTP` / `ScanAndFixZeroTP` | 전량 동시 (통문) | 무관 — 보류 중에도 자연 청산 유지 = 이득 |
| `WLU_CloseAllGrid/ExecuteCuts/Tail` | 전량 · 섬(999) | 무관 (`Grind_Collect` 섬 필터로 정합) |
| `LHEDGE_CloseAllHedge/MergeUpdate/GrindBurn(ltk)` | 매직 111 | 무관 |
| `CloseSolverPositionRobust` | 매직 777 | 무관 |
| `CloseAllSymbolPositions` / `MOMANTIC_CloseAccount` | 전량 | 무관 |

**무접촉 확인**: 완충 로직, 게이트 공식(`CalcCostAwareTPOffset` = 헌법), 연료 전량 규칙,
L1~12 부분청산 금지 원칙, 쿨다운, `Grind_Eligible`, 통문 계열, HCELL, WLU, PM(555), Solver(777).

---

## 4. 검증 결과

**정적 (internal / locked 동일)**
- 괄호 3종 균형: 원본 `(-4, -36, 1)` → 패치 `(-4, -36, 1)` | **변화 (0,0,0)**
- 줄 수: 16,059 → 16,096 (+37) / 16,055 → 16,092 (+37)
- CRLF 보존 · 함수 정의 중복 0 (`Grind_Try` 1 / `XGrind_PickTarget` 1 / `Grind_Eligible` 1)
- 신규 심볼 배선: `GRIND_L1_RULE_MIN_LEGS` = 정의 1 + 코드 2(G1·G4) + 주석 2
- `Grind_Eligible` 내 `L1_RULE` 참조 0건 (G3 미적용 확인)
- 지역변수 신규 4종(`l1Rule`·`l1InBundle`·`l2InBundle`·`l2Alive`) 이름 충돌 0

**행동 시뮬 11/11 PASS** (`sim.py` — 패치 로직 이식 + 브로커 제약 반영)

| # | 단언 | 결과 |
|---|---|---|
| A1 | 7/14 실측 재현(n=9, L1만 게이트 통과) → **보류** | ✅ |
| A2 | 미패치(rule off) → 기존 동작(L1 단독 발사 `[9,1]`) | ✅ |
| A3 | 철회① 생존 4다리(6항) → L1 단독 허용 | ✅ |
| A4 | 철회② L2가 완충층 → 규칙 해제 | ✅ |
| A5 | 다이얼 0 = 규칙 끔 → 기존 동작 | ✅ |
| A6 | 연료 충분 → L1·L2 동시 청산 (4항: 3장 이상도 허용) | ✅ |
| A7 | 5항: L1·L2 제거 후 → 규칙 미발동 | ✅ |
| B1 | XGrind n=9(유지) → L1·L2 스킵, 타깃 = L3 | ✅ |
| B2 | XGrind n=4(철회) → 기존대로 L1 | ✅ |
| B3 | XGrind 미패치 → L1 | ✅ |
| B4 | 최대손실 모드(`XGRIND_TARGET_MODE=1`)에서도 L1·L2 불가침 | ✅ |

*1차 실행 5건 FAIL → 전부 시뮬 기댓값 오류(묶음 순서 = 연료 선행 / NOBURN은 게이트 사유 /
최악 다리 = L7 −97.38)로 판명, 셋업 교정 후 전승. 코드 무수정. (교훈 L16 부류)*

---

## 5. 미결 — 별건 결정 대기

### 🟡 `LHEDGE_Fire` (L14822/14826) — 6-4 우회 경로 1건
```mql5
while(LHEDGE_OldestSnapLeg(tk, lot, pnl))   // 물린측 스냅 최고참 = L1
{
   double cost = MathMax(0.0, -pnl) + 0.5 * lot * 100.0;
   if(avail < cost) { 꼬리 부분소각; break; }
   if(!g_trade.PositionClose(tk, ULONG_MAX)) break;   // ← L1 통째
   avail -= cost;
}
```
`avail`이 L1은 덮고 L2를 못 덮으면 **L1 단독 청산**이 성립.
- **실발생 가능성 낮음**: 발동 = 물린측 L11 도달 + `avail ≥ LHEDGE_MIN_BURN_USD($500)` → 대개 L1~L8을 한 번에 쓸어감.
- **미적용 사유**: 여기에 6-4를 넣으면 **v5.2.3 "꼬리 부분소각" 확정 규정**(7/12)을 건드림 → 확정사항 번복은 컨펌 없이 불가.
- **선택지**: (가) 현행 유지 (나) 6-4 종속 = `avail`이 L1+L2를 못 덮으면 발사 자체 보류 (다) L1을 스냅 타깃에서 제외

### 보류 중인 기존 항목
- **연료 경합**: `LHEDGE_PairClose` / `LHEDGE_ComboExit`는 `Grind_Eligible` 양보 검사가 **없어서** 셀프가 기다리는 연료(그리드 수익 다리)를 가져갈 수 있음. **패치 이전부터 있던 동작**이라 이번 범위 밖. 6-4 보류 구간이 길어지면 실효가 커질 수 있어 백테스트 관찰 항목.

---

## 6. 다음 단계

1. **F7 컴파일** (사장님)
2. **백테스트 A/B** — 판정 지표:
   - `L1-PAIR 보류` 로그 발생 수 · 보류 지속시간 분포
   - 소각 회당 **연료 $ 대비 제거 부채 $** (기준: 미패치 0.48 → 목표 ≥ 0.9)
   - 셀프 그라인딩 발사 수 (감소 예상 — 대기가 정책)
   - 최종 에쿼티 / 최대 낙폭 / MSL 발동 수
   - **회귀 확인**: XGrind 발사 수·타깃 층 분포 (G4로 L3+ 이동해야 정상)
3. 라이브 투입은 위 통과 후
