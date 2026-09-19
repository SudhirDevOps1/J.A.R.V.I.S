"""Live NSE/BSE & Global stock lookup plugin (additive, free endpoint with smart caching)."""
from __future__ import annotations

import json
import time as _t
import urllib.request as _ur

PLUGIN = {
    "name": "stock_price",
    "description": (
        "Look up live NSE/BSE or Global stock prices (e.g. RELIANCE, TCS, INFY, TATA MOTORS, AAPL). "
        "Trigger on 'stock price', 'share bhav', 'Reliance ka rate', 'TCS share price'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "symbol": {"type": "STRING", "description": "e.g. RELIANCE, TCS, INFY, AAPL, MSFT"},
        },
        "required": ["symbol"],
    },
}

_CACHE: dict = {}


def run(parameters: dict, player=None, session_memory=None) -> str:
    raw_symbol = str((parameters or {}).get("symbol", "") or "").strip().upper()
    if not raw_symbol:
        return "Please specify a stock name or ticker, e.g. RELIANCE, TCS, or INFY."

    # Clean ticker name
    symbol = raw_symbol.replace(" ", "").replace("LIMITED", "").replace("LTD", "")

    now = _t.time()
    hit = _CACHE.get(symbol)
    if hit and now - hit[0] < 120:
        return hit[1]

    # Build candidates: If no exchange specified, try NSE (.NS), BSE (.BO), and raw
    candidates = [symbol]
    if "." not in symbol:
        candidates = [f"{symbol}.NS", f"{symbol}.BO", symbol]

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    # 1. Primary: Yahoo Finance API
    for sym in candidates:
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d"
            req = _ur.Request(url, headers=headers)
            with _ur.urlopen(req, timeout=7) as r:
                data = json.loads(r.read().decode("utf-8"))
                result_list = data.get("chart", {}).get("result", [])
                if not result_list:
                    continue
                meta = result_list[0].get("meta", {})
                price = meta.get("regularMarketPrice")
                if price is None:
                    continue
                currency = meta.get("currency", "INR")
                prev = meta.get("chartPreviousClose") or meta.get("previousClose")
                change_str = ""
                if price is not None and prev:
                    chg = price - prev
                    pct = (chg / prev) * 100
                    sign = "+" if chg >= 0 else ""
                    change_str = f" ({sign}{chg:.2f}, {sign}{pct:.2f}%)"
                out = f"{sym}: {price} {currency}{change_str}"
                _CACHE[symbol] = (now, out)
                if player:
                    try:
                        player.write_log(f"JARVIS: {out}")
                    except Exception:
                        pass
                return out
        except Exception:
            continue

    # 2. Fallback: Stooq CSV
    try:
        url = f"https://stooq.com/q/l/?s={symbol}&f=sd2t2ohlcv&h&e=csv"
        with _ur.urlopen(url, timeout=7) as r:
            text = r.read().decode("utf-8", "replace")
        lines = [l for l in text.strip().splitlines() if l.strip()]
        if len(lines) >= 2:
            parts = lines[1].split(",")
            close = parts[6] if len(parts) > 6 else "?"
            if close != "N/D" and close != "?":
                out = f"{symbol} last price {close} (Stooq)."
                _CACHE[symbol] = (now, out)
                if player:
                    try:
                        player.write_log(f"JARVIS: {out}")
                    except Exception:
                        pass
                return out
    except Exception:
        pass

    return f"Stock lookup nahi mila for '{raw_symbol}'. Please verify ticker symbol (e.g. RELIANCE, TCS, INFY)."
