"""
Technical Indicators Engine
Calculates standard quantitative indicators for daily candles:
- RSI (Relative Strength Index)
- EMA 20 & EMA 50 (Trend Direction)
- ATR (Average True Range - Volatility for Stop Loss Buffer)
"""

def calculate_sma(data, period):
    if len(data) < period:
        return None
    return sum(data[-period:]) / period

def calculate_ema(data, period):
    if len(data) < period:
        return None
    multiplier = 2 / (period + 1)
    ema = sum(data[:period]) / period  # Start with SMA
    for price in data[period:]:
        ema = (price - ema) * multiplier + ema
    return ema

def calculate_rsi(closes, period=14):
    if len(closes) <= period:
        return 50.0  # Neutral default

    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))

    if len(gains) < period:
        return 50.0

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calculate_atr(candles, period=14):
    """
    Calculates Average True Range (ATR) for dynamic volatility buffer.
    Candles format: list of dicts with 'high', 'low', 'close'
    """
    if len(candles) < 2:
        return 500.0 # Safe fallback for BTC

    tr_list = []
    for i in range(1, len(candles)):
        current = candles[i]
        prev = candles[i - 1]
        tr = max(
            current["high"] - current["low"],
            abs(current["high"] - prev["close"]),
            abs(current["low"] - prev["close"])
        )
        tr_list.append(tr)

    if len(tr_list) < period:
        return round(sum(tr_list) / len(tr_list), 2)
    return round(sum(tr_list[-period:]) / period, 2)
