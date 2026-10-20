"""
Enhanced Market Data Fetcher
Fetches live & historical daily candles to compute RSI, EMA, ATR, and Market Structure.
"""
import requests
from indicators import calculate_ema, calculate_rsi, calculate_atr

def fetch_btc_market_analysis():
    """
    Fetches 50 daily candles and computes key technical metrics.
    """
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": "BTCUSDT",
        "interval": "1d",
        "limit": 50
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()

        if not isinstance(data, list) or len(data) < 20:
            return {"success": False, "error": "Insufficient candle data received."}

        candles = []
        closes = []
        for row in data:
            candle = {
                "timestamp": row[0],
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5])
            }
            candles.append(candle)
            closes.append(candle["close"])

        prior_day = candles[-2]      # Yesterday's closed daily candle
        day_before = candles[-3]     # Day before yesterday's closed candle
        current_candle = candles[-1] # Today's live candle

        current_price = current_candle["close"]

        # Calculate Indicators
        rsi_14 = calculate_rsi(closes[:-1], period=14) # RSI of closed candles
        ema_20 = calculate_ema(closes[:-1], period=20)
        ema_50 = calculate_ema(closes[:-1], period=50) if len(closes) >= 50 else None
        atr_14 = calculate_atr(candles[:-1], period=14)

        # Trend Determination
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
            "volume_24h": round(current_candle["volume"], 2)
        }

    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    result = fetch_btc_market_analysis()
    print("Market Analysis:", result)
