"""GoldMiner 사다리 설계 스크리너 — 백테스트 없이 조합을 걸러낸다.

랏 사다리 / 거리 배율 / 시간 계단 조합을 만들어, 시세 없이 순수 산술로
구조 지표를 계산한다. 백테스트는 여기서 살아남은 후보만 돌린다.

계산하는 것 (전부 시세 무관):
  - 만재까지 필요한 낙폭 ($)
  - 만재 시 부동손실 ($)            ← 계좌가 견뎌야 하는 최대 압력
  - 만재 평단 · 통문 필요 반등폭 ($) ← 살아 나오는 데 필요한 되돌림
  - 헷지 arm 도달 층 / 낙폭
  - 층별 누적 노출 · 캡 도달 층
  - 만재까지 최소 소요 시간 (시간게이트 합)

사용:
  python ladder_screener.py                 # 기본 스윕 + HTML 리포트
  python ladder_screener.py --top 40        # 상위 N개만
  python ladder_screener.py --base 0.02     # 복리 배수 반영
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

# ── 엔진 상수 (정본 GoldMiner_v5_5_4_internal_20260730.mq5) ──────────────
GRID_STEP_PT   = 300      # 기준 간격 (pt)
POINT          = 0.01     # XAUUSD 2자리
USD_PER_LOT = 100.0    # 1랏이 $1 움직일 때 손익 ($)
MAX_SIDE_LOTS  = 2.5      # 방향 총노출 캡 (그리드 + 헷징 합산)
HARD_MAX_LAYER = 12
LOT_STEP       = 0.01
MIN_LOT        = 0.01

TAKE_PROFIT_PT = 300      # 통문 base 오프셋 산출용
TP_MIN_NET_PT  = 10
COMMISSION_PT  = 6.0      # $/lot ≒ pt
SPREAD_PT      = 20       # 평시 가정 (MAX_SPREAD 60의 1/3)

LHEDGE_ARM_USD = 6000.0   # 헷지 발동 부동손실

# 현행 확정값 (기준선)
CUR_LADDER = [0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.18, 0.27, 0.31, 0.35, 0.31, 0.22]
CUR_DIST   = {"L1_5": 1.0, "L6_8": 1.5, "L9_10": 3.3, "L11": 5.3, "L12P": 3.3}
CUR_TIME   = {"base": 90, "L9": 300, "L10": 900, "L11": 1800, "L12P": 3600}


# ── 사다리 생성 ────────────────────────────────────────────────────────────
def bell_ladder(peak_layer: int, peak_lot: float, rise: float, fall: float,
                n: int = HARD_MAX_LAYER) -> list[float]:
    """벨형 사다리. 정점 층·정점 랏·상승/하강 기울기로 모양을 만든다.

    rise/fall 이 클수록 정점 주변이 뾰족해진다(=저층이 얇고 정점이 두꺼움).
    현행 사다리는 peak_layer=10, peak_lot=0.35, rise≈1.55, fall≈1.30 근처.
    """
    out = []
    for i in range(1, n + 1):
        if i <= peak_layer:
            v = peak_lot / (rise ** (peak_layer - i))
        else:
            v = peak_lot / (fall ** (i - peak_layer))
        v = max(MIN_LOT, round(v / LOT_STEP) * LOT_STEP)
        out.append(round(v, 2))
    return out


def scale_ladder(ladder: list[float], base: float) -> list[float]:
    """base 비례 (복리). base 0.01 이면 원본 그대로."""
    r = base / 0.01
    return [round(max(MIN_LOT, round(v * r / LOT_STEP) * LOT_STEP), 2) for v in ladder]


# ── 거리 / 시간 ────────────────────────────────────────────────────────────
def dist_mult(layer: int, d: dict) -> float:
    if layer <= 5:  return d["L1_5"]
    if layer <= 8:  return d["L6_8"]
    if layer <= 10: return d["L9_10"]
    if layer == 11: return d["L11"]
    return d["L12P"]


def gap_usd(layer: int, d: dict) -> float:
    """layer 로 들어가기 위해 직전 체결가에서 필요한 이격 ($)."""
    return GRID_STEP_PT * POINT * dist_mult(layer, d)


def time_gate(layer: int, t: dict) -> int:
    if layer <= 8:  return t["base"]
    if layer == 9:  return t["L9"]
    if layer == 10: return t["L10"]
    if layer == 11: return t["L11"]
    return t["L12P"]


# ── 구조 지표 계산 ─────────────────────────────────────────────────────────
@dataclass
class Profile:
    ladder: list[float]
    dist: dict
    time: dict
    label: str = ""
    tags: dict = field(default_factory=dict)


@dataclass
class Metrics:
    n_layers: int
    total_lots: float
    cap_hit_layer: int | None      # 캡에 닿는 층 (None = 12층까지 여유)
    drop_to_full: float            # 만재까지 누적 낙폭 ($)
    drop_to_L11: float
    float_loss_full: float         # 만재 시 부동손실 ($)
    avg_price_off: float           # 만재 평단이 최하층에서 얼마나 위인가 ($)
    rebound_needed: float          # 통문까지 필요 반등 ($)
    arm_layer: int | None          # 헷지 발동 도달 층
    arm_drop: float | None
    min_hours_full: float          # 만재까지 최소 소요 (시간)
    density: float                 # 랏 / 낙폭 — 압력 밀도
    tail_ratio: float              # 상위 3층 랏 비중
    gate_profit: float             # 만재 통문 체결 시 이익 ($)
    risk_reward: float             # 만재부동손실 ÷ 통문이익 — 얼마 걸고 얼마 버나


def evaluate(p: Profile) -> Metrics:
    n = len(p.ladder)
    # 층별 진입가 (L1 = 0 기준, 아래로 내려감 = 음수 깊이)
    depth = [0.0]
    for i in range(2, n + 1):
        depth.append(depth[-1] + gap_usd(i, p.dist))

    cum = 0.0
    cap_hit = None
    for i, lot in enumerate(p.ladder, start=1):
        cum += lot
        if cap_hit is None and cum > MAX_SIDE_LOTS + 1e-9:
            cap_hit = i
    total = round(sum(p.ladder), 2)

    # 만재(=마지막 층 체결) 시점 지표
    px_now = depth[-1]                       # 현재가 = 최하층 진입가
    float_loss = sum(lot * (px_now - dep) * USD_PER_LOT
                     for lot, dep in zip(p.ladder, depth))
    wsum = sum(lot * dep for lot, dep in zip(p.ladder, depth))
    avg_price = wsum / total if total else 0.0
    avg_off = px_now - avg_price             # 평단이 현재가보다 이만큼 위

    # 통문 오프셋
    base_off = TAKE_PROFIT_PT * POINT / n
    cost_off = (SPREAD_PT + COMMISSION_PT + TP_MIN_NET_PT) * POINT
    off = max(base_off, cost_off)
    rebound = avg_off + off

    # 헷지 arm 도달 층
    arm_layer = arm_drop = None
    run_loss = 0.0
    for k in range(1, n + 1):
        px_k = depth[k - 1]
        loss_k = sum(p.ladder[j] * (px_k - depth[j]) * USD_PER_LOT for j in range(k))
        if loss_k >= LHEDGE_ARM_USD:
            arm_layer, arm_drop = k, px_k
            break

    secs = sum(time_gate(i, p.time) for i in range(2, n + 1))
    tail = round(sum(p.ladder[-3:]) / total, 3) if total else 0.0

    # 만재에서 통문이 체결되면 버는 돈 = 오프셋 × 총랏 (약수익 헌법의 실제 크기)
    gate_profit = off * total * USD_PER_LOT
    rr = float_loss / gate_profit if gate_profit else float("inf")

    return Metrics(
        n_layers=n, total_lots=total, cap_hit_layer=cap_hit,
        drop_to_full=round(depth[-1], 2),
        drop_to_L11=round(depth[10], 2) if n >= 11 else float("nan"),
        float_loss_full=round(float_loss, 0),
        avg_price_off=round(avg_off, 3),
        rebound_needed=round(rebound, 3),
        arm_layer=arm_layer, arm_drop=round(arm_drop, 2) if arm_drop else None,
        min_hours_full=round(secs / 3600.0, 2),
        density=round(total / depth[-1], 4) if depth[-1] else 0.0,
        tail_ratio=tail,
        gate_profit=round(gate_profit, 0),
        risk_reward=round(rr, 2),
    )


# ── 스윕 ───────────────────────────────────────────────────────────────────
def sweep(base: float = 0.01) -> list[tuple[Profile, Metrics]]:
    rows: list[tuple[Profile, Metrics]] = []

    # 기준선 먼저
    cur = Profile(scale_ladder(CUR_LADDER, base), dict(CUR_DIST), dict(CUR_TIME),
                  label="현행 v5.5.4", tags={"kind": "baseline"})
    rows.append((cur, evaluate(cur)))

    # 랏 사다리 패밀리 — 격자로 만들어 이웃(평탄도) 계산이 가능하게 한다
    PEAKS = [9, 10, 11]
    PLOTS = [0.30, 0.35, 0.40]
    RISES = [1.4, 1.55, 1.7]
    FALLS = [1.2, 1.3, 1.45]

    ladders = {}   # (pi,li,ri,fi) -> (ladder, label)
    for pi, peak in enumerate(PEAKS):
        for li, plot in enumerate(PLOTS):
            for ri, rise in enumerate(RISES):
                for fi, fall in enumerate(FALLS):
                    lad = bell_ladder(peak, plot, rise, fall)
                    s = sum(lad)
                    if s > MAX_SIDE_LOTS - 0.30:   # 헷지 여유 0.30 남김
                        continue
                    # ★ 같은 체급끼리만 비교 — 합랏이 작으면 부동손실이 주는 건
                    #   개선이 아니라 그냥 덜 거래하는 것. 기준선 1.95 ±12% 밴드.
                    if not (1.72 <= s <= 2.19):
                        continue
                    ladders[(pi, li, ri, fi)] = (
                        lad, f"peak L{peak}/{plot:.2f} · r{rise} f{fall}")

    # 거리 프로파일 후보
    dists = [
        ("현행 (L11 벌림)",   {"L1_5":1.0,"L6_8":1.5,"L9_10":3.3,"L11":5.3,"L12P":3.3}),
        ("평탄 3.3",          {"L1_5":1.0,"L6_8":1.5,"L9_10":3.3,"L11":3.3,"L12P":3.3}),
        ("심층 계단",         {"L1_5":1.0,"L6_8":1.5,"L9_10":3.3,"L11":5.3,"L12P":5.3}),
        ("L9부터 벌림",       {"L1_5":1.0,"L6_8":1.5,"L9_10":4.5,"L11":5.3,"L12P":4.5}),
        ("저층도 벌림",       {"L1_5":1.3,"L6_8":2.0,"L9_10":3.3,"L11":5.3,"L12P":3.3}),
        ("전 구간 확대",      {"L1_5":1.3,"L6_8":2.0,"L9_10":4.0,"L11":6.0,"L12P":4.0}),
    ]

    # 시간 계단 후보
    times = [
        ("현행",       {"base":90,"L9":300,"L10":900,"L11":1800,"L12P":3600}),
        ("2배 감속",   {"base":180,"L9":600,"L10":1800,"L11":3600,"L12P":7200}),
        ("저층 감속",  {"base":300,"L9":300,"L10":900,"L11":1800,"L12P":3600}),
        ("심층 감속",  {"base":90,"L9":600,"L10":1800,"L11":3600,"L12P":7200}),
    ]

    for idx, (lad, lname) in ladders.items():
        for di, (dname, d) in enumerate(dists):
            for ti, (tname, t) in enumerate(times):
                p = Profile(scale_ladder(list(lad), base), dict(d), dict(t),
                            label=lname,
                            tags={"ladder": lname, "dist": dname, "time": tname,
                                  "idx": idx, "di": di, "ti": ti})
                rows.append((p, evaluate(p)))
    return rows


# ── 평탄도 (MQL5 art.22578 — "최고점이 아니라 평탄대를 골라라") ─────────────
def plateau_stability(rows: list[tuple[Profile, Metrics]]) -> dict[int, float]:
    """국소 안정성 = 이웃 목적값의 평균 ÷ 표준편차.

    사다리 격자에서 각 축(정점층·정점랏·상승·하강) ±1 칸을 이웃으로 본다.
    거리·시간 프로파일은 고정. 값이 클수록 '이웃이 다 비슷하게 좋은' 평탄대.
    고립된 봉우리(이웃이 나쁨)는 std 가 커져 점수가 떨어진다.
    """
    grid: dict[tuple, float] = {}
    for i, (p, m) in enumerate(rows):
        if "idx" not in p.tags:
            continue
        key = (*p.tags["idx"], p.tags["di"], p.tags["ti"])
        grid[key] = 1.0 / m.risk_reward if m.risk_reward else 0.0   # 클수록 좋음

    out: dict[int, float] = {}
    for i, (p, m) in enumerate(rows):
        if "idx" not in p.tags:
            out[i] = float("nan")
            continue
        pi, li, ri, fi = p.tags["idx"]
        di, ti = p.tags["di"], p.tags["ti"]
        vals = []
        for dp in (-1, 0, 1):
            for dl in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    for df in (-1, 0, 1):
                        v = grid.get((pi+dp, li+dl, ri+dr, fi+df, di, ti))
                        if v is not None:
                            vals.append(v)
        if len(vals) < 4:              # 이웃이 너무 적으면 판정 불가 (격자 가장자리)
            out[i] = float("nan")
            continue
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        sd = math.sqrt(var)
        out[i] = mean / sd if sd > 1e-12 else 999.0
    return out


# ── 순위 ───────────────────────────────────────────────────────────────────
def score(m: Metrics, base_m: Metrics) -> dict:
    """기준선 대비 상대 지표. 1.0 = 기준선과 같음."""
    return {
        "위험보상_비":  round(m.risk_reward / base_m.risk_reward, 3),
        "부동손실_비":  round(m.float_loss_full / base_m.float_loss_full, 3),
        "반등폭_비":    round(m.rebound_needed / base_m.rebound_needed, 3),
        "낙폭여유_비":  round(m.drop_to_full / base_m.drop_to_full, 3),
        "시간여유_비":  round(m.min_hours_full / base_m.min_hours_full, 3),
    }


def pareto(rows: list[tuple[Profile, Metrics]]) -> list[int]:
    """위험보상비 ↓ · 반등폭 ↓ · 낙폭여유 ↑ 3목적 파레토 프론트."""
    front = []
    for i, (_, a) in enumerate(rows):
        dominated = False
        for j, (_, b) in enumerate(rows):
            if i == j:
                continue
            if (b.risk_reward    <= a.risk_reward    and
                b.rebound_needed <= a.rebound_needed and
                b.drop_to_full   >= a.drop_to_full   and
                (b.risk_reward    < a.risk_reward    or
                 b.rebound_needed < a.rebound_needed or
                 b.drop_to_full   > a.drop_to_full)):
                dominated = True
                break
        if not dominated:
            front.append(i)
    return front


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", type=float, default=0.01, help="BaseLot (복리 배수)")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--out", type=Path, default=Path("ladder_screen.html"))
    ap.add_argument("--json", type=Path, default=None)
    a = ap.parse_args()

    rows = sweep(a.base)
    base_p, base_m = rows[0]
    front = set(pareto(rows))
    stab = plateau_stability(rows)

    # 평탄도 정규화 (중앙값 = 1.0) → 봉우리 후보를 눌러준다
    fin = sorted(v for v in stab.values() if v == v and v < 900)
    med = fin[len(fin)//2] if fin else 1.0

    scored = []
    for i, (p, m) in enumerate(rows):
        sc = score(m, base_m)
        st = stab.get(i, float("nan"))
        stn = (st / med) if (st == st and med) else float("nan")
        # 종합: 위험보상비·반등폭 ↓, 낙폭·시간 여유 ↑, 그리고 ★평탄도 ↑
        composite = (2.0 - sc["위험보상_비"]) * 1.5 + (2.0 - sc["반등폭_비"]) \
                    + sc["낙폭여유_비"] * 0.6 + sc["시간여유_비"] * 0.4
        if stn == stn:
            composite += min(stn, 3.0) * 0.8      # 평탄대 가산 (상한 있음)
        sc["평탄도"] = round(st, 2) if st == st else None
        scored.append((composite, i, p, m, sc, i in front))
    scored.sort(key=lambda r: -r[0])

    print(json.dumps({
        "조합수": len(rows),
        "파레토_프론트": len(front),
        "기준선": {
            "합랏": base_m.total_lots,
            "만재낙폭$": base_m.drop_to_full,
            "만재부동손실$": base_m.float_loss_full,
            "필요반등$": base_m.rebound_needed,
            "arm도달층": base_m.arm_layer,
            "만재최소시간h": base_m.min_hours_full,
        },
    }, ensure_ascii=False, indent=2))

    if a.json:
        a.json.write_text(json.dumps(
            [{"label": p.label, **p.tags, "ladder": p.ladder,
              **m.__dict__, **s, "pareto": f} for _, _, p, m, s, f in scored],
            ensure_ascii=False, indent=1), encoding="utf-8")

    a.out.write_text(render_html(scored, base_m, a.top, a.base), encoding="utf-8")
    print(f"→ {a.out}")


# ── HTML 리포트 ────────────────────────────────────────────────────────────
def render_html(scored, base_m: Metrics, top: int, base: float) -> str:
    def row(r, rank):
        _, _, p, m, s, is_front = r
        cap = f"L{m.cap_hit_layer}" if m.cap_hit_layer else "여유"
        arm = f"L{m.arm_layer} · ${m.arm_drop:,.0f}" if m.arm_layer else "미도달"
        badge = '<span class="pf">PARETO</span>' if is_front else ""
        cls = ' class="base"' if p.tags.get("kind") == "baseline" else ""
        return f"""<tr{cls}>
<td class="r">{rank}</td>
<td>{p.tags.get('ladder', p.label)}{badge}<em>{p.tags.get('dist','')} · {p.tags.get('time','')}</em></td>
<td class="m">{' '.join(f'{v:.2f}' for v in p.ladder)}</td>
<td class="n">{m.total_lots:.2f}</td>
<td class="n">{cap}</td>
<td class="n">${m.drop_to_full:,.0f}</td>
<td class="n {'up' if m.float_loss_full < base_m.float_loss_full else 'dn'}">${m.float_loss_full:,.0f}</td>
<td class="n {'up' if m.rebound_needed < base_m.rebound_needed else 'dn'}">${m.rebound_needed:.2f}</td>
<td class="n {'up' if m.risk_reward < base_m.risk_reward else 'dn'}"><b>{m.risk_reward:.1f}</b></td>
<td class="n">{('%.1f' % s['평탄도']) if s.get('평탄도') else '—'}</td>
<td class="n">{arm}</td>
<td class="n">{m.min_hours_full:.1f}h</td>
<td class="n">{m.tail_ratio:.2f}</td></tr>"""

    body = "\n".join(row(r, i + 1) for i, r in enumerate(scored[:top]))
    return f"""<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<title>사다리 설계 스크리너</title><style>
:root{{--bg:#0e0e0d;--sf:#1a1a19;--ln:#33322e;--ink:#f4f3ee;--ink2:#c3c2b7;--ink3:#8b8a80;
--gold:#c98500;--goldb:#eda100;--up:#199e70;--dn:#d95926;
--mono:"SFMono-Regular",Consolas,monospace}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:"Pretendard","Malgun Gothic",system-ui,sans-serif;font-size:14px;line-height:1.7}}
.w{{max-width:1400px;margin:0 auto;padding:44px 26px 90px}}
h1{{font-size:30px;font-weight:800;margin:0 0 8px;letter-spacing:-.025em}}
.sub{{color:var(--ink2);max-width:76ch;margin:0 0 26px}}
.eyebrow{{font:600 11px/1 var(--mono);letter-spacing:.2em;color:var(--gold);text-transform:uppercase;margin-bottom:14px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:0 0 30px}}
.t{{background:var(--sf);border:1px solid var(--ln);border-radius:11px;padding:14px 16px}}
.t .l{{font:600 10.5px/1.4 var(--mono);letter-spacing:.09em;color:var(--ink3);text-transform:uppercase}}
.t .v{{font:700 23px/1.2 var(--mono);color:var(--goldb);margin-top:5px}}
.t .n{{font-size:11.5px;color:var(--ink3)}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
th,td{{padding:8px 9px;border-bottom:1px solid var(--ln);text-align:left;vertical-align:top}}
th{{font:600 10.5px/1.4 var(--mono);letter-spacing:.07em;color:var(--gold);text-transform:uppercase;
border-bottom:1px solid #3a2a05;position:sticky;top:0;background:var(--bg);white-space:nowrap}}
td.n,td.r,th.n{{text-align:right;font-family:var(--mono)}}
td.m{{font-family:var(--mono);font-size:11px;color:var(--ink3);letter-spacing:-.02em}}
td em{{display:block;font-style:normal;font-size:11px;color:var(--ink3);margin-top:2px}}
tr:hover{{background:#ffffff07}}
tr.base{{background:#c9850014}}
tr.base td{{border-bottom-color:#c9850044}}
.up{{color:var(--up)}} .dn{{color:var(--dn)}}
.pf{{display:inline-block;margin-left:7px;font:600 9.5px/1.5 var(--mono);letter-spacing:.06em;
padding:1px 6px;border-radius:4px;color:var(--goldb);border:1px solid #c9850055;background:#c9850014}}
.note{{margin-top:26px;padding:16px 19px;background:#c9850010;border:1px solid #c9850044;border-radius:10px;font-size:13.5px;color:var(--ink2)}}
.note b{{color:var(--goldb);display:block;margin-bottom:5px;font-family:var(--mono);font-size:12px;letter-spacing:.05em}}
</style></head><body><div class="w">
<div class="eyebrow">GoldMiner · Ladder Design Screener</div>
<h1>사다리 설계 스크리너</h1>
<p class="sub">시세 없이 순수 산술로 계산한 구조 지표입니다. 백테스트가 아니라 <b>백테스트 대상을 고르는 도구</b>입니다.
초록 = 기준선보다 유리, 주황 = 불리. PARETO 표시는 세 목적(부동손실↓ · 반등폭↓ · 낙폭여유↑)에서
어느 것도 더 나은 조합이 없는 후보입니다.</p>

<div class="tiles">
<div class="t"><div class="l">기준선 합랏</div><div class="v">{base_m.total_lots:.2f}</div><div class="n">BaseLot {base}</div></div>
<div class="t"><div class="l">만재 낙폭</div><div class="v">${base_m.drop_to_full:,.0f}</div><div class="n">L1 → L12 누적</div></div>
<div class="t"><div class="l">만재 부동손실</div><div class="v">${base_m.float_loss_full:,.0f}</div><div class="n">계좌가 견딜 압력</div></div>
<div class="t"><div class="l">필요 반등</div><div class="v">${base_m.rebound_needed:.2f}</div><div class="n">통문까지</div></div>
<div class="t"><div class="l">헷지 arm</div><div class="v">L{base_m.arm_layer or '—'}</div><div class="n">${base_m.arm_drop or 0:,.0f} 낙폭</div></div>
<div class="t"><div class="l">만재 최소시간</div><div class="v">{base_m.min_hours_full:.1f}h</div><div class="n">시간게이트 합</div></div>
</div>

<table><thead><tr>
<th class="n">#</th><th>조합</th><th>랏 사다리 L1→L12</th><th class="n">합</th><th class="n">캡</th>
<th class="n">만재낙폭</th><th class="n">만재부동손실</th><th class="n">필요반등</th><th class="n">위험/보상</th><th class="n">평탄도</th>
<th class="n">헷지 arm</th><th class="n">만재시간</th><th class="n">꼬리비중</th>
</tr></thead><tbody>
{body}
</tbody></table>

<div class="note"><b>읽는 법 — 트레이드오프가 전부입니다</b>
<p style="margin:0 0 8px">랏을 키우면 <b>필요 반등폭이 줄어</b> 빨리 나오지만 <b>만재 부동손실이 커집니다</b>.
거리를 벌리면 만재까지 낙폭 여유가 늘지만 그만큼 평단이 나빠져 반등폭이 커집니다.
공짜 개선은 없고, 어느 쪽 위험을 살 것인지의 문제입니다.</p>
<p style="margin:0 0 8px"><b>★ 이번 스윕에서 나온 가장 중요한 사실 — 부동손실을 줄이는 조합은 곧 방패가 안 켜지는 조합입니다.</b>
방패는 부동손실 −$6,000에서 켜지는데, <b>현행 사다리는 만재(L12)가 되어야 겨우 $6,291로 임계를 넘습니다.</b>
상위 후보들은 만재 부동손실이 $4,000대라 <b>arm이 아예 도달하지 않습니다</b>. 즉 "더 안전한 사다리"를 고르면
방패가 영영 안 켜지는 설계가 됩니다. 이 둘은 같이 정해야 합니다 — 사다리를 얇게 하려면 ARM_USD도 같이 내려야 합니다.</p>
<p style="margin:0 0 8px"><b>그리고 이건 실측과 어긋납니다.</b> 이론상 방패는 만재에서야 겨우 켜지는데,
라이브에서는 "너무 빨리 발동한다"는 관측이 있었습니다. 이론과 실제가 다르다면 원인은 사다리가 아니라
① arm 모집단 오염(해결사 777 등이 섞임) ② 복리 배수로 실랏이 커진 상태 ③ 되돌림·재진입으로 실제 평단이
이론보다 나쁨 — 셋 중 하나입니다. <b>사다리를 손대기 전에 이것부터 규명해야 합니다.</b></p>
<p style="margin:0"><b>이 표는 판정이 아니라 후보 선별입니다.</b> 상위 5~10개를 골라 TEST_A로 대조군 A/B를 돌려야 판정이 됩니다.
단독 런은 관찰이지 판정이 아닙니다.</p></div>
</div></body></html>"""


if __name__ == "__main__":
    main()
