"""
Enhanced Technical Indicators Engine — v2.0
Extends the original RSI + EMA + ATR with:
  - MACD (momentum confirmation)
  - Volume Analysis (fake breakout filter)
  - Candle Patterns (Engulfing, Hammer, Shooting Star, Doji)
  - Market Structure (Higher Highs / Lower Lows)
  - 4H Multi-timeframe confirmation
"""

import requests


# ─── ORIGINAL INDICATORS (preserved exactly) ─────────────────────────────────

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
    Average True Range — dynamic volatility buffer for stop loss placement.
    Candles format: list of dicts with 'high', 'low', 'close'
    """
    if len(candles) < 2:
        return 500.0  # Safe fallback for BTC

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


# ─── NEW: MACD ───────────────────────────────────────────────────────────────

def calculate_macd(closes, fast=12, slow=26, signal_period=9):
    """
    MACD = EMA(12) - EMA(26)
    Signal Line = EMA(9) of MACD
    Histogram = MACD - Signal
    Returns: (macd_val, signal_val, histogram) or (None, None, None) if insufficient data.
    """
    if len(closes) < slow + signal_period:
        return None, None, None

    def _ema_series(data, period):
        k = 2 / (period + 1)
        ema = sum(data[:period]) / period
        result = [ema]
        for price in data[period:]:
            ema = price * k + ema * (1 - k)
            result.append(ema)
        return result

    fast_ema = _ema_series(closes, fast)
    slow_ema = _ema_series(closes, slow)

    min_len = min(len(fast_ema), len(slow_ema))
    macd_line = [fast_ema[-min_len + i] - slow_ema[i] for i in range(min_len)]

    signal_line = _ema_series(macd_line, signal_period)
    histogram = macd_line[-1] - signal_line[-1]

    return round(macd_line[-1], 4), round(signal_line[-1], 4), round(histogram, 4)


def get_macd_signal(closes):
    """
    Returns MACD direction signal and reason string.
    Compatible with market_data return format.
    """
    macd, sig, hist = calculate_macd(closes)
    if macd is None:
        return "NEUTRAL", 0.0, 0.0, 0.0

    if macd > sig and hist > 0:
        label = "BULLISH"
    elif macd < sig and hist < 0:
        label = "BEARISH"
    elif macd > sig:
        label = "BULLISH_FORMING"
    else:
        label = "BEARISH_FORMING"

    return label, macd, sig, round(hist, 4)


# ─── NEW: VOLUME ANALYSIS ────────────────────────────────────────────────────

def volume_confirmation(candles, lookback=10):
    """
    Checks if current volume confirms the price move.
    Returns: (label, ratio)
      STRONG  — 1.5x+ above average (confirms move)
      NORMAL  — 0.8x–1.5x (healthy)
      WEAK    — below 0.8x (potential fake breakout, caution)
    """
    if len(candles) < lookback + 1:
        return "NORMAL", 1.0

    recent_vols = [c["volume"] for c in candles[-lookback - 1:-1]]
    avg_vol = sum(recent_vols) / len(recent_vols)
    if avg_vol == 0:
        return "NORMAL", 1.0

    current_vol = candles[-1]["volume"]
    ratio = round(current_vol / avg_vol, 2)

    if ratio >= 1.5:
        return "STRONG", ratio
    if ratio >= 0.8:
        return "NORMAL", ratio
    return "WEAK", ratio


# ─── NEW: CANDLE PATTERN DETECTION ───────────────────────────────────────────

def detect_candle_patterns(candles):
    """
    Detects key reversal and continuation patterns on the last 2 candles.
    Returns list of (bias, pattern_name) tuples:
      bias: 'BULLISH', 'BEARISH', or 'NEUTRAL'
    """
    if len(candles) < 2:
        return []

    patterns = []
    c = candles[-1]    # current candle
    p = candles[-2]    # previous candle

    body       = abs(c["close"] - c["open"])
    high_wick  = c["high"] - max(c["close"], c["open"])
    low_wick   = min(c["close"], c["open"]) - c["low"]
    full_range = c["high"] - c["low"]

    if full_range < 1:
        return patterns

    # Doji — indecision candle
    if body / full_range < 0.1:
        patterns.append(("NEUTRAL", "Doji"))

    # Hammer — bullish reversal (long lower wick, small body, little upper wick)
    if (low_wick > 2 * body
            and high_wick < body * 0.5
            and c["close"] >= c["open"]):
        patterns.append(("BULLISH", "Hammer"))

    # Shooting Star — bearish reversal (long upper wick, small body)
    if (high_wick > 2 * body
            and low_wick < body * 0.5
            and c["close"] <= c["open"]):
        patterns.append(("BEARISH", "Shooting Star"))

    # Bullish Engulfing — green candle engulfs previous red
    if (c["close"] > c["open"]
            and p["close"] < p["open"]
            and c["close"] > p["open"]
            and c["open"] < p["close"]):
        patterns.append(("BULLISH", "Bullish Engulfing"))

    # Bearish Engulfing — red candle engulfs previous green
    if (c["close"] < c["open"]
            and p["close"] > p["open"]
            and c["close"] < p["open"]
            and c["open"] > p["close"]):
        patterns.append(("BEARISH", "Bearish Engulfing"))

    return patterns


# ─── NEW: MARKET STRUCTURE ───────────────────────────────────────────────────

def market_structure_trend(candles, lookback=20):
    """
    Identifies trend via Higher Highs/Higher Lows (Uptrend)
    or Lower Highs/Lower Lows (Downtrend).
    Returns: (label, description)
      UPTREND, DOWNTREND, RANGING
    """
    if len(candles) < lookback:
        return "RANGING", "Insufficient data"

    recent = candles[-lookback:]
    highs  = [c["high"]  for c in recent]
    lows   = [c["low"]   for c in recent]

    hh = highs[-1] > max(highs[:-1])
    hl = lows[-1]  > min(lows[:-1])
    lh = highs[-1] < max(highs[:-1])
    ll = lows[-1]  < min(lows[:-1])

    if hh and hl:
        return "UPTREND",   "HH + HL — Classic uptrend structure"
    if lh and ll:
        return "DOWNTREND", "LH + LL — Classic downtrend structure"
    if hh:
        return "UPTREND",   "New Higher High — Bullish momentum"
    if ll:
        return "DOWNTREND", "New Lower Low — Bearish momentum"
    return "RANGING", "Sideways / ranging market"


# ─── NEW: 4H CANDLE FETCHER ──────────────────────────────────────────────────

def fetch_4h_candles(limit=60):
    """
    Fetches 4-hour candles for multi-timeframe confirmation.
    Uses Coinbase → Binance fallback (same as market_data.py pattern).
    Returns list of candle dicts or [] on failure.
    """
    # Coinbase 4H (granularity 14400 seconds)
    try:
        url = "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=14400"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            raw = res.json()
            if isinstance(raw, list) and len(raw) >= 20:
                raw_sorted = sorted(raw[:limit], key=lambda x: x[0])
                return [{"timestamp": c[0], "open": float(c[3]), "high": float(c[2]),
                         "low": float(c[1]), "close": float(c[4]), "volume": float(c[5])}
                        for c in raw_sorted]
    except Exception:
        pass

    # Binance 4H fallback
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&limit={limit}"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) >= 20:
                return [{"timestamp": r[0], "open": float(r[1]), "high": float(r[2]),
                         "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])}
                        for r in data]
    except Exception:
        pass

    return []


# ─── COMPOSITE SCORE (used by market_data.py) ────────────────────────────────

def compute_composite_score(candles_1d, candles_4h=None):
    """
    Runs all new indicators and returns a composite dictionary
    ready to be merged into the market_analysis result dict.

    Fields added:
      macd_signal, macd_val, macd_sig_val, macd_hist
      volume_signal, volume_ratio
      candle_patterns           (list of (bias, name) tuples)
      structure_1d, structure_1d_desc
      structure_4h, structure_4h_desc
      composite_score           (-10 to +10, positive = bullish)
      composite_bias            BULLISH / BEARISH / NEUTRAL
    """
    closes = [c["close"] for c in candles_1d]
    score = 0

    # MACD
    macd_signal_label, macd_val, macd_sig_val, macd_hist = get_macd_signal(closes)
    if "BULLISH" in macd_signal_label:
        score += 2 if macd_signal_label == "BULLISH" else 1
    elif "BEARISH" in macd_signal_label:
        score -= 2 if macd_signal_label == "BEARISH" else 1

    # Volume
    vol_label, vol_ratio = volume_confirmation(candles_1d)

    # Candle Patterns
    patterns = detect_candle_patterns(candles_1d)
    for bias, _ in patterns:
        if bias == "BULLISH":
            score += 2
        elif bias == "BEARISH":
            score -= 2

    # Daily Market Structure
    struct_1d, struct_1d_desc = market_structure_trend(candles_1d, lookback=20)
    if struct_1d == "UPTREND":
        score += 2
    elif struct_1d == "DOWNTREND":
        score -= 2

    # 4H Structure (lighter weight)
    struct_4h, struct_4h_desc = "N/A", "4H data unavailable"
    if candles_4h:
        struct_4h, struct_4h_desc = market_structure_trend(candles_4h, lookback=20)
        if struct_4h == "UPTREND":
            score += 1
        elif struct_4h == "DOWNTREND":
            score -= 1

    # Volume weakens conviction (not directional)
    if vol_label == "WEAK":
        score = int(score * 0.7)  # 30% penalty on weak volume

    if score >= 3:
        bias = "BULLISH"
    elif score <= -3:
        bias = "BEARISH"
    else:
        bias = "NEUTRAL"

    return {
        "macd_signal":      macd_signal_label,
        "macd_val":         macd_val,
        "macd_sig_val":     macd_sig_val,
        "macd_hist":        macd_hist,
        "volume_signal":    vol_label,
        "volume_ratio":     vol_ratio,
        "candle_patterns":  patterns,
        "structure_1d":     struct_1d,
        "structure_1d_desc": struct_1d_desc,
        "structure_4h":     struct_4h,
        "structure_4h_desc": struct_4h_desc,
        "composite_score":  score,
        "composite_bias":   bias,
    }
