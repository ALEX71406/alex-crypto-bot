"""
Enhanced Market Data Fetcher (Global Cloud & US Datacenter Compatible)
Uses Delta Exchange India as primary source, with Coinbase and Binance fallback.
"""
import requests
import time
from indicators import calculate_ema, calculate_rsi, calculate_atr


def fetch_btc_market_analysis():
    """
    Fetches 50 daily candles and computes key technical metrics.
    Robust against cloud datacenter geoblocking (e.g. Render US servers).
    """
    candles = []
    current_price = 0.0

    # 1. PRIMARY SOURCE: Delta Exchange India (Direct exchange feed)
    try:
        now_ts = int(time.time())
        start_ts = now_ts - (50 * 86400)
        url = "https://api.india.delta.exchange/v2/history/candles"
        params = {
            "resolution": "1d",
            "symbol": "BTCUSD",
            "start": start_ts,
            "end": now_ts
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            raw_candles = res.json().get("result", [])
            if len(raw_candles) >= 20:
                # Delta returns oldest to newest or sorted by time
                raw_sorted = sorted(raw_candles, key=lambda x: x["time"])
                for c in raw_sorted:
                    candles.append({
                        "timestamp": c["time"],
                        "open": float(c["open"]),
                        "high": float(c["high"]),
                        "low": float(c["low"]),
                        "close": float(c["close"]),
                        "volume": float(c.get("volume", 0.0))
                    })
                # Fetch live ticker for latest exact price
                ticker_res = requests.get("https://api.india.delta.exchange/v2/tickers/BTCUSD", timeout=5)
                if ticker_res.status_code == 200:
                    t_data = ticker_res.json().get("result", {})
                    current_price = float(t_data.get("mark_price") or t_data.get("close") or candles[-1]["close"])
                else:
                    current_price = candles[-1]["close"]
    except Exception:
        candles = []

    # 2. SECONDARY SOURCE: Coinbase Public API (Global, fast, US cloud friendly)
    if len(candles) < 20:
        try:
            url = "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400"
            headers = {"User-Agent": "Mozilla/5.0"}
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200:
                raw = res.json()
                if isinstance(raw, list) and len(raw) >= 20:
                    # Coinbase returns newest first [time, low, high, open, close, volume]
                    raw_sorted = sorted(raw[:50], key=lambda x: x[0])
                    candles = []
                    for c in raw_sorted:
                        candles.append({
                            "timestamp": c[0],
                            "open": float(c[3]),
                            "high": float(c[2]),
                            "low": float(c[1]),
                            "close": float(c[4]),
                            "volume": float(c[5])
                        })
                    current_price = candles[-1]["close"]
        except Exception:
            pass

    # 3. TERTIARY SOURCE: Binance
    if len(candles) < 20:
        try:
            url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=50"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if isinstance(data, list) and len(data) >= 20:
                    candles = []
                    for row in data:
                        candles.append({
                            "timestamp": row[0],
                            "open": float(row[1]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                            "close": float(row[4]),
                            "volume": float(row[5])
                        })
                    current_price = candles[-1]["close"]
        except Exception:
            pass

    if len(candles) < 20:
        return {"success": False, "error": "Unable to fetch sufficient candle data from all providers."}

    closes = [c["close"] for c in candles]
    prior_day = candles[-2]      # Yesterday's closed daily candle
    day_before = candles[-3]     # Day before yesterday's closed candle

    # Indicators
    rsi_14 = calculate_rsi(closes[:-1], period=14)
    ema_20 = calculate_ema(closes[:-1], period=20)
    ema_50 = calculate_ema(closes[:-1], period=50) if len(closes) >= 50 else None
    atr_14 = calculate_atr(candles[:-1], period=14)

    trend = "NEUTRAL"
    if ema_20:
        if current_price > ema_20 and prior_day["close"] > day_before["close"]:
            trend = "BULLISH"
        elif current_price < ema_20 and prior_day["close"] < day_before["close"]:
            trend = "BEARISH"

    return {
        "success": True,
        "current_price": current_price,
        "prior_day": prior_day,
        "day_before": day_before,
        "rsi_14": rsi_14,
        "ema_20": round(ema_20, 2) if ema_20 else None,
        "ema_50": round(ema_50, 2) if ema_50 else None,
        "atr_14": atr_14,
        "trend": trend,
        "volume_24h": round(candles[-1]["volume"], 2)
    }


if __name__ == "__main__":
    result = fetch_btc_market_analysis()
    print("Market Analysis:", result)
