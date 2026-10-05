import aiohttp
from config import API_URL

def fmt(pair): return f"{pair[:3]}/{pair[3:]}"

async def get_candles(pair, count=300):
    async with aiohttp.ClientSession() as s:
        async with s.get(API_URL, params={"pair": pair, "count": count}, timeout=aiohttp.ClientTimeout(total=20)) as r:
            j = await r.json(content_type=None)
    if not j.get("success"):
        return []
    # API returns newest first -> make oldest first
    return sorted(j["data"], key=lambda c: c["epoch"])

def ema(vals, n):
    k = 2 / (n + 1); out = [vals[0]]
    for v in vals[1:]: out.append(v * k + out[-1] * (1 - k))
    return out

def rsi(vals, n=14):
    g = l = 0.0
    for i in range(1, n + 1):
        d = vals[-i] - vals[-i - 1]
        g += max(d, 0); l += max(-d, 0)
    if l == 0: return 100.0
    rs = g / l
    return 100 - 100 / (1 + rs)

def analyze(candles):
    """Return dict(direction, trend, score 0-100) based on EMA trend, RSI, last candle momentum."""
    closed = [c for c in candles][:-1] if len(candles) > 60 else candles
    closes = [c["close"] for c in closed]
    if len(closes) < 60: return None
    e9, e21, e50 = ema(closes, 9)[-1], ema(closes, 21)[-1], ema(closes, 50)[-1]
    r = rsi(closes)
    last3 = closed[-3:]
    greens = sum(1 for c in last3 if c["close"] > c["open"])
    up = down = 0
    if e9 > e21: up += 1
    else: down += 1
    if e21 > e50: up += 1
    else: down += 1
    if greens >= 2: up += 1
    elif greens <= 1: down += 1
    if r < 30: up += 1
    elif r > 70: down += 1
    elif r > 50: up += 0.5
    else: down += 0.5
    direction = "CALL" if up >= down else "PUT"
    agree = max(up, down) / (up + down)
    trend = "Uptrend Follow" if e21 > e50 else "Downtrend Follow"
    if (direction == "CALL") != (e21 > e50): trend = "Reversal"
    return {"direction": direction, "trend": trend, "score": round(agree * 100),
            "rsi": round(r, 1), "payout": candles[-1].get("payout", 0)}
