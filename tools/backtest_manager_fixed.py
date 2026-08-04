"""Collect, classify, and analyze MT4/MT5 backtest and trade reports.

The manager is intentionally local-first: raw reports and generated summaries
stay under data/backtests and reports, both of which are git-ignored.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


SUPPORTED = {".html", ".htm", ".xlsx", ".xlsm", ".csv", ".tsv"}
CLASS_RULES = {
    "gold": ("goldminer", "goldguard", "goldsun", "goldferrari", "hansgold", "primegold", "s_bomb", "xau", "gold"),
    "fx": ("nexus", "forex", "fx", "sidejobmaster", "fp_trader", "eurusd", "gbpusd", "usdjpy"),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(path: Path, text: str = "") -> str:
    haystack = f"{path.name} {text[:10000]}".lower()
    for category, tokens in CLASS_RULES.items():
        if any(token in haystack for token in tokens):
            return category
    return "other"


def strategy_name(path: Path, category: str) -> str:
    stem = re.sub(r"[ _-]+", " ", path.stem).strip()
    return stem if stem else category


def number(value) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).replace(",", "").strip()
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    return float(match.group(0)) if match else None


def parse_mt5_html(path: Path) -> pd.DataFrame:
    tables = pd.read_html(path)
    frames = []
    for table in tables:
        if table.shape[1] < 13:
            continue
        # Standard MT5 tester table: time, order, symbol, side, in/out,
        # volume, price, position, commission, swap, profit, balance, comment.
        rows = table.iloc[:, :13].copy()
        direction = rows.iloc[:, 4].astype(str).str.lower().str.strip()
        closed = rows[direction.isin({"out", "close", "closed"})]
        if closed.empty:
            continue
        result = pd.DataFrame({
            "time": closed.iloc[:, 0],
            "ticket": closed.iloc[:, 1],
            "symbol": closed.iloc[:, 2],
            "side": closed.iloc[:, 3],
            "direction": closed.iloc[:, 4],
            "volume": closed.iloc[:, 5].map(number),
            "price": closed.iloc[:, 6].map(number),
            "profit": closed.iloc[:, 10].map(number),
            "balance": closed.iloc[:, 11].map(number),
            "comment": closed.iloc[:, 12].astype(str),
        })
        frames.append(result)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).drop_duplicates(subset=["ticket", "time", "profit"])


def find_header(raw: pd.DataFrame) -> int | None:
    for i in range(min(len(raw), 40)):
        values = {str(v).strip().lower() for v in raw.iloc[i].tolist() if not pd.isna(v)}
        if "profit" in values or "ticket" in values or "거래번호" in values:
            return i
    return None


def parse_tabular_file(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".html", ".htm"}:
        return parse_mt5_html(path)
    if path.suffix.lower() in {".csv", ".tsv"}:
        raw = pd.read_csv(path, header=None, sep="\t" if path.suffix.lower() == ".tsv" else ",", encoding_errors="ignore")
        sheets = [("csv", raw)]
    else:
        sheets = [(name, pd.read_excel(path, sheet_name=name, header=None)) for name in pd.ExcelFile(path).sheet_names]

    frames = []
    for sheet, raw in sheets:
        header = find_header(raw)
        if header is None:
            continue
        data = raw.iloc[header + 1 :].copy()
        data.columns = [str(v).strip() for v in raw.iloc[header].tolist()]
        rename = {}
        for col in data.columns:
            low = col.lower()
            if low in {"profit", "p/l", "pnl", "손익", "수익"}:
                rename[col] = "profit"
            elif low in {"item", "symbol", "통화", "종목"}:
                rename[col] = "symbol"
            elif low in {"ticket", "거래번호", "주문"}:
                rename[col] = "ticket"
            elif "close time" in low or "청산" in low:
                rename[col] = "time"
            elif "open time" in low or "진입" in low:
                rename[col] = "time"
            elif low in {"type", "종류", "방향"}:
                rename[col] = "side"
            elif low in {"size", "volume", "거래량"}:
                rename[col] = "volume"
        data = data.rename(columns=rename)
        # Reports often repeat labels such as time/price across grouped columns.
        # Keep the first normalized column so concatenation remains deterministic.
        data = data.loc[:, ~data.columns.duplicated()]
        if "profit" not in data.columns:
            continue
        keep = [c for c in ["time", "ticket", "symbol", "side", "volume", "profit"] if c in data.columns]
        data = data[keep].copy()
        data["profit"] = data["profit"].map(number)
        data = data.dropna(subset=["profit"])
        data["sheet"] = sheet
        frames.append(data)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def metrics(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trade_count": 0, "status": "no-trades"}
    profit = pd.to_numeric(trades["profit"], errors="coerce").dropna()
    wins = profit[profit > 0]
    losses = profit[profit < 0]
    curve = trades.get("balance", pd.Series(dtype=float))
    if curve.empty or curve.dropna().empty:
        curve = profit.cumsum()
    else:
        curve = pd.to_numeric(curve, errors="coerce").ffill().dropna()
    drawdown = curve - curve.cummax()
    gross_loss = abs(losses.sum())
    return {
        "trade_count": int(len(profit)),
        "win_count": int(len(wins)),
        "loss_count": int(len(losses)),
        "win_rate": round(float(len(wins) / len(profit)), 6) if len(profit) else None,
        "net_profit": round(float(profit.sum()), 4),
        "gross_profit": round(float(wins.sum()), 4),
        "gross_loss": round(float(gross_loss), 4),
        "profit_factor": round(float(wins.sum() / gross_loss), 6) if gross_loss else None,
        "avg_trade": round(float(profit.mean()), 4),
        "avg_win": round(float(wins.mean()), 4) if len(wins) else None,
        "avg_loss": round(float(losses.mean()), 4) if len(losses) else None,
        "max_drawdown": round(float(abs(drawdown.min())), 4) if len(drawdown) else None,
        "status": "ok",
    }


def iter_files(sources: Iterable[Path]):
    seen = set()
    for source in sources:
        if source.is_file() and source.suffix.lower() in SUPPORTED:
            candidates = [source]
        elif source.exists():
            candidates = source.rglob("*")
        else:
            continue
        for path in candidates:
            if path.is_file() and path.suffix.lower() in SUPPORTED:
                key = str(path.resolve()).lower()
                if key not in seen:
                    seen.add(key)
                    yield path


def process_file(path: Path, repo: Path) -> dict:
    text = ""
    if path.suffix.lower() in {".html", ".htm", ".txt", ".csv", ".tsv"}:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")[:10000]
        except OSError:
            pass
    category = classify(path, text)
    digest = sha256(path)
    raw_dir = repo / "data" / "backtests" / "raw" / category
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / f"{digest[:10]}_{path.name}"
    if not dest.exists():
        shutil.copy2(path, dest)
    try:
        trades = parse_tabular_file(path)
        status = "ok" if not trades.empty else "no-trades"
        error = ""
    except Exception as exc:  # keep one bad report from stopping the scan
        trades = pd.DataFrame()
        status = "parse-error"
        error = f"{type(exc).__name__}: {exc}"
    result = {
        "source": str(path),
        "archived": str(dest),
        "filename": path.name,
        "category": category,
        "strategy": strategy_name(path, category),
        "file_type": path.suffix.lower().lstrip("."),
        "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
        "sha256": digest,
        "parse_status": status,
        "error": error,
    }
    result.update(metrics(trades))
    result["_trades"] = trades
    return result


def scan(sources: list[Path], repo: Path) -> None:
    rows = []
    all_trades = []
    for path in iter_files(sources):
        result = process_file(path, repo)
        trades = result.pop("_trades")
        if not trades.empty:
            trades.insert(0, "source", str(path))
            trades.insert(1, "category", result["category"])
            trades.insert(2, "strategy", result["strategy"])
            all_trades.append(trades)
        rows.append(result)
    data_dir = repo / "data" / "backtests"
    report_dir = repo / "reports"
    data_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    index = pd.DataFrame(rows).sort_values(["category", "modified_at"], ascending=[True, False]) if rows else pd.DataFrame()
    index.to_csv(data_dir / "index.csv", index=False, encoding="utf-8-sig")
    trades = pd.concat(all_trades, ignore_index=True) if all_trades else pd.DataFrame()
    trades.to_csv(data_dir / "trades.csv", index=False, encoding="utf-8-sig")
    with pd.ExcelWriter(report_dir / "backtest_summary.xlsx", engine="openpyxl") as writer:
        index.to_excel(writer, sheet_name="runs", index=False)
        trades.to_excel(writer, sheet_name="trades", index=False)
        if not index.empty:
            by_category = index.groupby("category", dropna=False).agg(
                runs=("filename", "count"), net_profit=("net_profit", "sum"),
                avg_win_rate=("win_rate", "mean"), worst_drawdown=("max_drawdown", "max"),
            ).reset_index()
        else:
            by_category = pd.DataFrame(columns=["category", "runs", "net_profit", "avg_win_rate", "worst_drawdown"])
        by_category.to_excel(writer, sheet_name="by_category", index=False)
    print(json.dumps({"files": len(rows), "parsed": int((index.get("parse_status", pd.Series()) == "ok").sum()) if not index.empty else 0, "output": str(report_dir / "backtest_summary.xlsx")}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage MT4/MT5 backtest reports")
    parser.add_argument("command", choices=["scan", "watch"])
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--source", action="append", type=Path, required=True)
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()
    if args.command == "scan":
        scan(args.source, args.repo)
    else:
        known = set()
        while True:
            current = {str(p.resolve()): p.stat().st_mtime_ns for p in iter_files(args.source)}
            if current != known:
                scan(args.source, args.repo)
                known = current
            time.sleep(max(args.interval, 5))


if __name__ == "__main__":
    main()
