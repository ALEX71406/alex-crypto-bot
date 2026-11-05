"""
Enhanced AI Trade Reviewer Engine — v2.0
Strictly evaluates trades against Sidhant's 5 rules + Full Quant Filter Suite:
  1. Risk capped at Rs 25–30
  2. Stop loss buffer adjusted by Volatility (ATR) past prior day high/low
  3. Never add to a losing trade
  4. 3 consecutive losses = 3 days off
  5. Position size capped below account size (Max Rs 300)
  + v2.0: Composite multi-indicator gate (MACD + Volume + Structure + Patterns)
"""
import config


def review_trade(market_analysis, idea_direction=None, has_active_position=False,
                 is_already_losing=False, consecutive_losses=0):
    """
    Evaluates market setup with full quant checks.
    """
    # Active Position Check (Single Market Rule: Max 1 position at a time)
    if has_active_position:
        return {
            "verdict": "SKIP",
            "why": "Active position already open in Bitcoin. Single market rule enforces max 1 trade at a time.",
            "next_action": "Hold active position until Stop Loss or Take Profit is triggered."
        }

    # Rule 4: Circuit Breaker
    if consecutive_losses >= config.MAX_CONSECUTIVE_LOSSES:
        return {
            "verdict": "SKIP",
            "why": "3 consecutive losses reached. Circuit breaker active.",
            "next_action": "3 days off. Strictly observe cooling period."
        }

    # Rule 3: Open losing position
    if is_already_losing:
        return {
            "verdict": "SKIP",
            "why": "Account already has an active losing trade. Never add to a loser.",
            "next_action": "Never add to a loser. Wait for position to settle."
        }

    prior_day     = market_analysis["prior_day"]
    day_before    = market_analysis["day_before"]
    current_price = market_analysis["current_price"]
    rsi           = market_analysis.get("rsi_14", 50.0)
    atr           = market_analysis.get("atr_14", 500.0)

    # Determine direction if not provided
    if not idea_direction:
        direction = "LONG" if prior_day["close"] >= day_before["close"] else "SHORT"
    else:
        direction = idea_direction.upper()

    # ── Original RSI Sanity Filter ──────────────────────────────────────────
    if direction == "LONG" and rsi >= 75.0:
        return {
            "verdict": "SKIP",
            "why": f"RSI is extremely overbought ({rsi}). High risk of buying the top.",
            "next_action": "Wait for RSI to cool off before entering LONG."
        }
    if direction == "SHORT" and rsi <= 25.0:
        return {
            "verdict": "SKIP",
            "why": f"RSI is deeply oversold ({rsi}). High risk of shorting the bottom.",
            "next_action": "Wait for a relief bounce before entering SHORT."
        }

    # ── v2.0 Composite Multi-Indicator Filter ───────────────────────────────
    composite_score = market_analysis.get("composite_score", 0)
    composite_bias  = market_analysis.get("composite_bias", "NEUTRAL")
    macd_signal     = market_analysis.get("macd_signal", "NEUTRAL")
    vol_signal      = market_analysis.get("volume_signal", "NORMAL")
    struct_1d       = market_analysis.get("structure_1d", "RANGING")
    patterns        = market_analysis.get("candle_patterns", [])

    # Block trade if composite indicators strongly oppose direction
    if direction == "LONG" and composite_bias == "BEARISH" and composite_score <= -4:
        return {
            "verdict": "SKIP",
            "why": (f"Composite score ({composite_score}) strongly BEARISH. "
                    f"MACD: {macd_signal}, Structure: {struct_1d}. Indicators oppose LONG entry."),
            "next_action": "Wait for MACD crossover + bullish structure before entering LONG."
        }
    if direction == "SHORT" and composite_bias == "BULLISH" and composite_score >= 4:
        return {
            "verdict": "SKIP",
            "why": (f"Composite score ({composite_score}) strongly BULLISH. "
                    f"MACD: {macd_signal}, Structure: {struct_1d}. Indicators oppose SHORT entry."),
            "next_action": "Wait for MACD bearish cross + downtrend structure before entering SHORT."
        }

    # Volume note (allow trade, just flag)
    vol_note = ""
    if vol_signal == "WEAK":
        vol_ratio = market_analysis.get("volume_ratio", 1.0)
        vol_note = f" ⚠️ Weak volume ({vol_ratio}x avg) — lower conviction."

    # Candle pattern note
    pat_note = ""
    if patterns:
        pat_note = " Patterns: " + ", ".join(f"{name}({bias})" for bias, name in patterns) + "."

    # ── Dynamic ATR Volatility Buffer (Rule 2) ──────────────────────────────
    buffer = max(atr * 0.15, current_price * 0.001)

    if direction == "LONG":
        entry_price = round(current_price, 2)
        stop_price  = round(prior_day["low"] - buffer, 2)

        if stop_price >= entry_price:
            return {
                "verdict": "SKIP",
                "why": "Current price is already below prior day low buffer.",
                "next_action": "Setup invalidated. Wait for next daily candle."
            }

        risk_distance = entry_price - stop_price
        target_price  = round(entry_price + (risk_distance * config.MIN_REWARD_TO_RISK), 2)

    else:  # SHORT
        entry_price = round(current_price, 2)
        stop_price  = round(prior_day["high"] + buffer, 2)

        if stop_price <= entry_price:
            return {
                "verdict": "SKIP",
                "why": "Current price is already above prior day high buffer.",
                "next_action": "Setup invalidated. Wait for next daily candle."
            }

        risk_distance = stop_price - entry_price
        target_price  = round(entry_price - (risk_distance * config.MIN_REWARD_TO_RISK), 2)

    risk_pct = risk_distance / entry_price
    if risk_pct <= 0:
        return {
            "verdict": "SKIP",
            "why": "Calculated risk distance is zero or negative.",
            "next_action": "Wait for valid candle range."
        }

    # Position sizing: Risk (Rs 25) / Risk%  — capped at MAX_ORDER_VALUE_INR
    calculated_position_size = round(config.RISK_AMOUNT_INR / risk_pct, 2)
    allowed_position_inr     = min(calculated_position_size, config.MAX_ORDER_VALUE_INR)

    target_distance  = abs(target_price - entry_price)
    reward_to_risk   = round(target_distance / risk_distance, 2)

    if reward_to_risk < config.MIN_REWARD_TO_RISK:
        return {
            "verdict": "SKIP",
            "why": f"Reward-to-risk ratio ({reward_to_risk}) is below minimum threshold ({config.MIN_REWARD_TO_RISK}).",
            "next_action": "Wait for setup with favorable asymmetric payoff."
        }

    analysis_note = (
        f"Clean {direction} setup confirmed. "
        f"Stop placed {round(buffer, 1)} pts past prior day level with {reward_to_risk}:1 R:R. "
        f"RSI: {rsi}. MACD: {macd_signal}. Structure: {struct_1d}. "
        f"Composite score: {composite_score} ({composite_bias}).{vol_note}{pat_note}"
    )

    return {
        "verdict":          "TAKE",
        "direction":        direction,
        "entry":            entry_price,
        "stop":             stop_price,
        "target":           target_price,
        "risk_amount_inr":  config.RISK_AMOUNT_INR,
        "position_size_inr": allowed_position_inr,
        "reward_to_risk":   f"{reward_to_risk} : 1",
        "rules_check":      "Rule 1 OK, Rule 2 OK (ATR buffer), Rule 3 OK, Rule 4 OK, Rule 5 OK",
        "rsi":              rsi,
        "atr":              atr,
        "composite_score":  composite_score,
        "composite_bias":   composite_bias,
        "why":              analysis_note
    }
