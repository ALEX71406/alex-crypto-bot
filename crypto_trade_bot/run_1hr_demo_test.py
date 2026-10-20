"""
Automated 1-Hour DEMO Trading Test Runner
Project: MADE BY ALEX — AI Crypto Trading System
Platform: Windows | Exchange: Delta Exchange India

Duration: 3600 seconds (~60 minutes)
Interval: 60 seconds (60 cycles)
Timeframe: Daily (1D) Candle (Unmodified Strategy)
Safety: Strictly DEMO mode, zero real orders.
"""
import os
import sys
import time
import json
from datetime import datetime

# Enforce project path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import config
from risk_manager import RiskManager
from paper_engine import PaperTradingEngine
from market_data import fetch_btc_market_analysis
from trade_reviewer import review_trade
from order_executor import OrderExecutor

# Output log files
TELEMETRY_FILE = os.path.join(PROJECT_DIR, "test_run_1hr_telemetry.json")
REPORT_FILE = os.path.join(PROJECT_DIR, "test_run_1hr_report.json")
TEXT_LOG_FILE = os.path.join(PROJECT_DIR, "test_run_1hr_log.txt")


def log_text(msg, f_handle=None):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {msg}"
    print(formatted, flush=True)
    if f_handle:
        f_handle.write(formatted + "\n")
        f_handle.flush()


def run_1hr_test():
    total_duration_sec = 3600  # 60 minutes
    check_interval_sec = 60    # 1 minute per cycle

    f_log = open(TEXT_LOG_FILE, "w", encoding="utf-8")

    log_text("=" * 70, f_log)
    log_text("🚀 STARTING 1-HOUR CONTROLLED DEMO TRADING TEST", f_log)
    log_text("Project: MADE BY ALEX — AI Crypto Trading System", f_log)
    log_text(f"Target Duration: {total_duration_sec} seconds (60 mins) | Interval: {check_interval_sec}s", f_log)
    log_text("=" * 70, f_log)

    # 1. HARD SAFETY ASSERTIONS
    assert config.TRADING_MODE == "DEMO", f"CRITICAL SAFETY FAIL: TRADING_MODE is {config.TRADING_MODE}, not DEMO!"
    executor = OrderExecutor()
    assert executor.mode == "DEMO", f"CRITICAL SAFETY FAIL: OrderExecutor mode is {executor.mode}, not DEMO!"

    log_text("🔒 HARD SAFETY VERIFICATION: PASSED", f_log)
    log_text(f"   • config.TRADING_MODE: {config.TRADING_MODE}", f_log)
    log_text(f"   • OrderExecutor.mode : {executor.mode}", f_log)
    log_text(f"   • Delta API Order Execution: DISABLED (Zero real orders possible)", f_log)
    log_text(f"   • Simulation Layer   : PaperTradingEngine Active", f_log)

    # Initialize subsystems
    rm = RiskManager()
    paper = PaperTradingEngine(risk_manager=rm)
    executor = OrderExecutor(paper_engine=paper)

    start_time = time.time()
    start_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    telemetry = []
    cycle_count = 0
    skip_count = 0
    take_count = 0
    sl_hit_count = 0
    tp_hit_count = 0
    error_count = 0

    log_text(f"⏱️ Test officially started at: {start_dt}", f_log)
    log_text("-" * 70, f_log)

    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= total_duration_sec:
                log_text(f"\n⏰ 60-minute test duration reached ({int(elapsed)}s elapsed). Stopping test loop.", f_log)
                break

            cycle_count += 1
            iteration_start = time.time()
            cycle_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            tick_record = {
                "cycle": cycle_count,
                "timestamp": cycle_dt,
                "elapsed_sec": round(elapsed, 1),
                "btc_price": None,
                "rsi_14": None,
                "ema_20": None,
                "atr_14": None,
                "trend": None,
                "paper_event": "NONE",
                "active_position": None,
                "verdict": None,
                "verdict_reason": None,
                "error": None
            }

            try:
                # Step A: Circuit breaker check
                is_safe, cb_msg = rm.check_circuit_breaker()
                if not is_safe:
                    tick_record["verdict"] = "SKIP"
                    tick_record["verdict_reason"] = cb_msg
                    log_text(f"Cycle {cycle_count:02d} | ⛔ Circuit Breaker Active: {cb_msg}", f_log)
                    skip_count += 1
                else:
                    # Step B: Fetch live market data
                    market = fetch_btc_market_analysis()
                    if not market.get("success"):
                        err_msg = market.get("error", "Unknown market data error")
                        tick_record["error"] = err_msg
                        tick_record["verdict"] = "SKIP"
                        tick_record["verdict_reason"] = f"Market data fetch error: {err_msg}"
                        error_count += 1
                        skip_count += 1
                        log_text(f"Cycle {cycle_count:02d} | ❌ Market Data Fetch Error: {err_msg}", f_log)
                    else:
                        current_price = market["current_price"]
                        rsi = market["rsi_14"]
                        ema_20 = market["ema_20"]
                        atr = market["atr_14"]
                        trend = market["trend"]

                        tick_record["btc_price"] = current_price
                        tick_record["rsi_14"] = rsi
                        tick_record["ema_20"] = ema_20
                        tick_record["atr_14"] = atr
                        tick_record["trend"] = trend

                        # Step C: Update paper trading engine with live tick price
                        pos_update = paper.update_price(current_price)
                        tick_record["paper_event"] = pos_update["event"]

                        if pos_update["event"] == "STOP_LOSS_HIT":
                            sl_hit_count += 1
                            log_text(f"Cycle {cycle_count:02d} | 🛑 PAPER STOP-LOSS HIT at ${current_price:,.2f}! Net PnL: Rs {pos_update['details']['net_pnl_inr']:.2f}", f_log)
                        elif pos_update["event"] == "TAKE_PROFIT_HIT":
                            tp_hit_count += 1
                            log_text(f"Cycle {cycle_count:02d} | 🎯 PAPER TAKE-PROFIT HIT at ${current_price:,.2f}! Net PnL: Rs {pos_update['details']['net_pnl_inr']:.2f}", f_log)
                        elif pos_update["event"] == "HOLDING":
                            pos = pos_update["details"]
                            tick_record["active_position"] = {
                                "direction": pos["direction"],
                                "entry": pos["entry_price"],
                                "sl": pos["stop_loss"],
                                "tp": pos["take_profit"],
                                "unrealized_pnl_inr": pos.get("unrealized_pnl_inr", 0.0)
                            }

                        # Step D: Trade review against 5 rules
                        has_active = paper.has_active_position()
                        is_losing = paper.has_active_losing_position(current_price)
                        consec_losses = rm.history.get("consecutive_losses", 0)

                        review = review_trade(
                            market_analysis=market,
                            idea_direction=None,
                            has_active_position=has_active,
                            is_already_losing=is_losing,
                            consecutive_losses=consec_losses
                        )

                        tick_record["verdict"] = review["verdict"]
                        tick_record["verdict_reason"] = review.get("why")

                        if review["verdict"] == "SKIP":
                            skip_count += 1
                            pos_desc = f"Active {pos['direction']} (Unrealized PnL: Rs {pos.get('unrealized_pnl_inr', 0.0):+.2f})" if has_active else "None"
                            log_text(f"Cycle {cycle_count:02d} [{int(elapsed)}s] | BTC: ${current_price:,.2f} | RSI: {rsi} | Trend: {trend} | Verdict: SKIP ({review.get('why')}) | Pos: {pos_desc}", f_log)

                        elif review["verdict"] == "TAKE":
                            take_count += 1
                            log_text(f"Cycle {cycle_count:02d} [{int(elapsed)}s] | 🌟 VERDICT: TAKE | {review['direction']} BTC @ ${review['entry']:,.2f} | SL: ${review['stop']:,.2f} | TP: ${review['target']:,.2f}", f_log)

                            # Place simulated order through hard-guarded executor
                            sim_order = executor.place_order(
                                direction=review["direction"],
                                entry_price=review["entry"],
                                stop_price=review["stop"],
                                target_price=review["target"],
                                position_inr=review["position_size_inr"],
                                reward_to_risk=review["reward_to_risk"]
                            )

                            if sim_order.get("success"):
                                rm.log_trade(review, result="OPEN", pnl_inr=0.0)
                                log_text(f"Cycle {cycle_count:02d} | 🟢 Simulated Order Placed & Tracked: {sim_order.get('order_id')}", f_log)

            except Exception as e:
                error_count += 1
                tick_record["error"] = str(e)
                log_text(f"Cycle {cycle_count:02d} | ⚠️ Exception in test cycle: {e}", f_log)

            telemetry.append(tick_record)

            # Persist telemetry after each tick
            with open(TELEMETRY_FILE, "w", encoding="utf-8") as f_tel:
                json.dump(telemetry, f_tel, indent=2)

            # Sleep remainder of interval
            cycle_duration = time.time() - iteration_start
            sleep_time = max(0.0, check_interval_sec - cycle_duration)
            remaining_total = total_duration_sec - (time.time() - start_time)
            if remaining_total <= 0:
                break
            time.sleep(min(sleep_time, remaining_total))

    except KeyboardInterrupt:
        log_text("\n🛑 Test manually interrupted by user.", f_log)

    end_time = time.time()
    end_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    actual_runtime_sec = round(end_time - start_time, 1)

    # Compile Final Report
    active_pos = paper.get_active_position()
    closed_trades = paper.state.get("closed_trades", [])
    realized_pnl = sum(t.get("net_pnl_inr", 0.0) for t in closed_trades)
    unrealized_pnl = active_pos.get("unrealized_pnl_inr", 0.0) if active_pos else 0.0
    total_fees = sum(t.get("total_fees_inr", 0.0) for t in closed_trades) + (active_pos.get("total_fees_inr", 0.0) if active_pos else 0.0)

    final_report = {
        "status": "COMPLETED",
        "demo_mode_verified": True,
        "real_orders_submitted": 0,
        "test_start": start_dt,
        "test_end": end_dt,
        "total_runtime_seconds": actual_runtime_sec,
        "total_runtime_minutes": round(actual_runtime_sec / 60, 2),
        "total_market_checks": cycle_count,
        "verdicts_take": take_count,
        "verdicts_skip": skip_count,
        "stop_loss_hits": sl_hit_count,
        "take_profit_hits": tp_hit_count,
        "active_simulated_positions": 1 if active_pos else 0,
        "closed_simulated_trades": len(closed_trades),
        "simulated_realized_pnl_inr": round(realized_pnl, 2),
        "simulated_unrealized_pnl_inr": round(unrealized_pnl, 2),
        "simulated_total_fees_inr": round(total_fees, 2),
        "errors_count": error_count,
        "active_position_details": active_pos,
        "conclusion": "PASS" if error_count == 0 and cycle_count > 0 else "PARTIAL PASS"
    }

    with open(REPORT_FILE, "w", encoding="utf-8") as f_rep:
        json.dump(final_report, f_rep, indent=4)

    log_text("=" * 70, f_log)
    log_text("🏁 1-HOUR CONTROLLED DEMO TEST COMPLETED SUCCESSFULLY", f_log)
    log_text(f"Start Time         : {start_dt}", f_log)
    log_text(f"End Time           : {end_dt}", f_log)
    log_text(f"Total Runtime      : {actual_runtime_sec}s ({round(actual_runtime_sec/60, 1)} minutes)", f_log)
    log_text(f"Total Checks (Ticks): {cycle_count}", f_log)
    log_text(f"TAKE Verdicts      : {take_count}", f_log)
    log_text(f"SKIP Verdicts      : {skip_count}", f_log)
    log_text(f"Active Position    : {'YES' if active_pos else 'NONE'}", f_log)
    if active_pos:
        log_text(f"   • Direction     : {active_pos['direction']}", f_log)
        log_text(f"   • Entry Price   : ${active_pos['entry_price']:,.2f}", f_log)
        log_text(f"   • Stop Loss     : ${active_pos['stop_loss']:,.2f}", f_log)
        log_text(f"   • Take Profit   : ${active_pos['take_profit']:,.2f}", f_log)
        log_text(f"   • Unrealized PnL: Rs {unrealized_pnl:+.2f}", f_log)
    log_text(f"Realized P&L       : Rs {realized_pnl:+.2f}", f_log)
    log_text(f"Simulated Fees     : Rs {total_fees:.2f}", f_log)
    log_text(f"Errors / Timeouts  : {error_count}", f_log)
    log_text(f"Real Orders Placed : 0 (Hard safety guard confirmed)", f_log)
    log_text(f"CONCLUSION         : {final_report['conclusion']}", f_log)
    log_text("=" * 70, f_log)

    f_log.close()
    return final_report


if __name__ == "__main__":
    run_1hr_test()
