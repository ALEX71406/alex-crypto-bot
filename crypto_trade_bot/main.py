"""
Institutional-Grade AI Crypto Trading Bot
System Architecture: 'Trading With Sidhant' 5 Strict Rules + Quant Multi-Indicator Filter
Optimized for Rs 1,000 Capital on Delta Exchange India

Run directly:
    python main.py
"""
import sys
import time
from risk_manager import RiskManager
from market_data import fetch_btc_market_analysis
from trade_reviewer import review_trade
from order_executor import OrderExecutor
from paper_engine import PaperTradingEngine
import config


def print_banner():
    print("""
======================================================================
                          MADE BY ALEX
  🤖  AI CRYPTO TRADE SYSTEM (Trading With Sidhant Model - Pro)
  🛡️  Strict 5-Rules Engine  |  💰 Capital: Rs 1,000  |  🎯 Risk: Rs 25
======================================================================
""")


def display_dashboard(summary, wallet_info=None):
    inr_bal = wallet_info.get("balance_inr", 0.0) if wallet_info else 0.0
    usd_bal = wallet_info.get("balance_usd", 0.0) if wallet_info else 0.0
    conn_status = "CONNECTED 🟢" if wallet_info and wallet_info.get("success") else "DEMO MODE 🟡"

    print("┌────────────────────────────────────────────────────────────────────┐")
    print(f"│  DELTA EXCHANGE     : {conn_status:<15} LIVE WALLET INR: Rs {inr_bal:<14.2f} │")
    print(f"│  ACCOUNT SIZE       : Rs {summary['account_size']:<12.2f} LIVE WALLET USD: $  {usd_bal:<14.2f} │")
    print(f"│  TOTAL P&L          : Rs {summary['total_pnl_inr']:<12.2f} WIN RATE       : {summary['win_rate']:<17} │")
    print(f"│  WINS / LOSSES      : {summary['wins']}W - {summary['losses']}L            STREAK LOSSES   : {summary['consecutive_losses']} / {config.MAX_CONSECUTIVE_LOSSES:<13} │")
    print(f"│  TOTAL TRADES LOGGED: {summary['total_trades']:<12} TRADING MODE   : {config.TRADING_MODE:<17} │")
    print("└────────────────────────────────────────────────────────────────────┘")


def run_single_check(custom_direction=None):
    print("\n🔍 [STEP 1] Initializing Risk & Circuit Breaker Engine...")
    rm = RiskManager()
    paper = PaperTradingEngine(risk_manager=rm)
    is_safe, msg = rm.check_circuit_breaker()

    if not is_safe:
        print("\n" + "!" * 65)
        print(f"⛔ VERDICT: SKIP")
        print(f"WHY: {msg}")
        print("NEXT: 3 days off. Market se dur raho, account balance protect karo!")
        print("!" * 65 + "\n")
        return

    print("✅ Circuit Breaker: OK (No active lockout)")

    print("\n📡 [STEP 2] Fetching Live Bitcoin Market Analysis & Quant Data...")
    market = fetch_btc_market_analysis()
    if not market.get("success"):
        print(f"❌ Market Data Error: {market.get('error')}")
        return

    prior = market["prior_day"]
    before = market["day_before"]
    current = market["current_price"]

    # Update active paper position with latest live price
    pos_update = paper.update_price(current)
    if pos_update["event"] == "STOP_LOSS_HIT":
        print(f"\n🛑 [PAPER TRADE ALERT] Stop-Loss Hit at ${current:,.2f}!")
        print(f"   • Realized P&L: Rs {pos_update['details']['net_pnl_inr']:.2f} (Incl. Fees)")
    elif pos_update["event"] == "TAKE_PROFIT_HIT":
        print(f"\n🎯 [PAPER TRADE ALERT] Take-Profit Hit at ${current:,.2f}!")
        print(f"   • Realized P&L: Rs {pos_update['details']['net_pnl_inr']:.2f} (Incl. Fees)")
    elif pos_update["event"] == "HOLDING":
        pos = pos_update["details"]
        print(f"\n📊 [ACTIVE PAPER POSITION] {pos['direction']} Entry: ${pos['entry_price']:,.2f} | Current: ${current:,.2f} | Unrealized P&L: Rs {pos['unrealized_pnl_inr']:.2f}")

    print("\n📊 Quantitative Indicators Loaded:")
    print(f"   • Live BTC Price : ${current:,.2f}")
    print(f"   • Prior Day (1D) : High ${prior['high']:,.2f} | Low ${prior['low']:,.2f} | Close ${prior['close']:,.2f}")
    print(f"   • Day Before (1D): High ${before['high']:,.2f} | Low ${before['low']:,.2f} | Close ${before['close']:,.2f}")
    print(f"   • RSI (14-period): {market['rsi_14']} {'(Overbought ⚠️)' if market['rsi_14'] > 70 else '(Oversold ⚠️)' if market['rsi_14'] < 30 else '(Neutral ✅)'}")
    print(f"   • 20-Day EMA     : ${market['ema_20']:,.2f}")
    print(f"   • 14-Day ATR     : ${market['atr_14']:,.2f} (Daily Volatility Buffer)")
    print(f"   • Market Trend   : {market['trend']}")

    print("\n🧠 [STEP 3] Running AI Trade Reviewer Against 5 Rules...")
    has_active = paper.has_active_position()
    is_losing = paper.has_active_losing_position(current)
    review = review_trade(
        market_analysis=market,
        idea_direction=custom_direction,
        has_active_position=has_active,
        is_already_losing=is_losing,
        consecutive_losses=rm.history.get("consecutive_losses", 0)
    )

    print("\n" + "=" * 65)
    print("📋 AI TRADE REVIEW VERDICT:")
    print(f"VERDICT        : {review['verdict']}")

    if review["verdict"] == "SKIP":
        print(f"REASON (WHY)   : {review['why']}")
        print(f"NEXT ACTION    : {review['next_action']}")
        print("=" * 65 + "\n")
        return

    print(f"ACTION         : {review['direction']} BITCOIN")
    print(f"ENTRY PRICE    : ${review['entry']:,.2f}")
    print(f"STOP LOSS      : ${review['stop']:,.2f}")
    print(f"TARGET         : ${review['target']:,.2f}")
    print(f"RISK AMOUNT    : Rs {review['risk_amount_inr']:.2f} (Strict 2.5% max risk)")
    print(f"POSITION SIZE  : Rs {review['position_size_inr']:.2f} (Rule 5: No high leverage)")
    print(f"REWARD-TO-RISK : {review['reward_to_risk']}")
    print(f"RULES CHECK    : {review['rules_check']}")
    print(f"ANALYSIS       : {review['why']}")
    print("=" * 65)

    print("\n⚡ [STEP 4] Order Routing & Execution...")
    executor = OrderExecutor(paper_engine=paper)
    order_res = executor.place_order(
        direction=review["direction"],
        entry_price=review["entry"],
        stop_price=review["stop"],
        target_price=review["target"],
        position_inr=review["position_size_inr"],
        reward_to_risk=review["reward_to_risk"]
    )

    if order_res.get("success"):
        # Log trade into history and CSV
        rm.log_trade(review, result="OPEN", pnl_inr=0.0)
        print("📁 Trade successfully recorded in 'trade_history.json' and 'trade_log.csv'!")


def run_watcher(interval_minutes=60):
    print(f"\n⏱️ Starting Continuous Market Watcher (Checking every {interval_minutes} mins)...")
    print("Press Ctrl+C anytime to stop.\n")
    try:
        while True:
            print(f"\n--- Checking Market at {time.strftime('%Y-%m-%d %H:%M:%S')} ---")
            run_single_check()
            print(f"\n💤 Sleeping for {interval_minutes} minutes...")
            time.sleep(interval_minutes * 60)
    except KeyboardInterrupt:
        print("\n🛑 Watcher stopped by user.")


def main():
    print_banner()
    rm = RiskManager()
    summary = rm.get_summary()
    executor = OrderExecutor()
    wallet_info = executor.get_wallet_balance()
    display_dashboard(summary, wallet_info)

    print("""
Select an option:
  [1] Run Full Live Market Check & Trade (Instant)
  [2] Review Custom Trade Idea (Enter LONG/SHORT manually)
  [3] View Trade Journal & Performance History
  [4] Start Continuous Watcher (Background Monitor)
  [5] Exit
""")

    # If no interactive input available or auto flag, run default
    if not sys.stdin.isatty():
        print("Running Instant Analysis Mode by default...")
        run_single_check()
        return

    choice = input("Enter choice (1-5) [Default: 1]: ").strip()
    if choice == "2":
        dir_input = input("Enter direction (LONG or SHORT): ").strip()
        run_single_check(custom_direction=dir_input)
    elif choice == "3":
        print("\n📜 Recent Trade History:")
        trades = rm.history.get("trades", [])
        if not trades:
            print("No trades logged yet. Run a trade check to start logging!")
        else:
            for i, t in enumerate(trades[-5:], 1):
                print(f"  {i}. {t['date']} | {t['direction']} | Entry: ${t['entry']} | SL: ${t['stop']} | Status: {t['result']} | PnL: Rs {t['pnl_inr']}")
            print(f"\nFull ledger saved in: D:\\crypto_trade_bot\\trade_log.csv")
    elif choice == "4":
        mins = input("Enter interval in minutes [Default: 60]: ").strip()
        interval = int(mins) if mins.isdigit() and int(mins) > 0 else 60
        run_watcher(interval_minutes=interval)
    elif choice == "5":
        print("Goodbye!")
    else:
        run_single_check()


if __name__ == "__main__":
    main()
