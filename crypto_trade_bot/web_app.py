"""
Web Dashboard & 24/7 Cloud Background Worker for MADE BY ALEX
Works 100% out of the box on Render.com / Railway without complex dependencies.
Uses Python's built-in threaded HTTP server to serve a sleek mobile dashboard
while running the automated trading bot 24/7 in a background thread.
"""
import os
import sys
import time
import json
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

import config
from risk_manager import RiskManager
from paper_engine import PaperTradingEngine
from market_data import fetch_btc_market_analysis
from trade_reviewer import review_trade
from order_executor import OrderExecutor

# Global state for dashboard
BOT_STATE = {
    "status": "INITIALIZING",
    "last_check_time": "Never",
    "btc_price": 0.0,
    "rsi_14": 50.0,
    "trend": "NEUTRAL",
    "active_position": None,
    "total_trades": 0,
    "total_pnl_inr": 0.0,
    "mode": config.TRADING_MODE,
    "recent_logs": []
}

def log_event(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry, flush=True)
    BOT_STATE["recent_logs"].insert(0, entry)
    if len(BOT_STATE["recent_logs"]) > 20:
        BOT_STATE["recent_logs"].pop()

def background_trading_loop():
    log_event("🚀 24/7 Cloud Trading Worker Started!")
    rm = RiskManager()
    paper = PaperTradingEngine(risk_manager=rm)
    executor = OrderExecutor(paper_engine=paper)

    while True:
        try:
            BOT_STATE["status"] = "CHECKING MARKET"
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            BOT_STATE["last_check_time"] = now_str

            # 1. Fetch live market analysis
            market = fetch_btc_market_analysis()
            if market.get("success"):
                current_price = market["current_price"]
                rsi = market["rsi_14"]
                trend = market["trend"]

                BOT_STATE["btc_price"] = current_price
                BOT_STATE["rsi_14"] = rsi
                BOT_STATE["trend"] = trend

                # 2. Update active paper position
                pos_update = paper.update_price(current_price)
                if pos_update["event"] == "STOP_LOSS_HIT":
                    log_event(f"🛑 STOP-LOSS HIT at ${current_price:,.2f}! Net PnL: Rs {pos_update['details']['net_pnl_inr']}")
                elif pos_update["event"] == "TAKE_PROFIT_HIT":
                    log_event(f"🎯 TAKE-PROFIT HIT at ${current_price:,.2f}! Net PnL: Rs {pos_update['details']['net_pnl_inr']}")
                
                # Update dashboard active position
                active_pos = paper.get_active_position()
                BOT_STATE["active_position"] = active_pos
                BOT_STATE["total_pnl_inr"] = rm.history.get("total_pnl_inr", 0.0)
                BOT_STATE["total_trades"] = len(rm.history.get("trades", []))

                # 3. Check 5 rules
                has_active = paper.has_active_position()
                is_losing = paper.has_active_losing_position(current_price)
                consec = rm.history.get("consecutive_losses", 0)

                review = review_trade(
                    market_analysis=market,
                    idea_direction=None,
                    has_active_position=has_active,
                    is_already_losing=is_losing,
                    consecutive_losses=consec
                )

                if review["verdict"] == "TAKE":
                    log_event(f"🌟 VERDICT: TAKE | {review['direction']} BTC @ ${review['entry']:,.2f}")
                    sim_res = executor.place_order(
                        direction=review["direction"],
                        entry_price=review["entry"],
                        stop_price=review["stop"],
                        target_price=review["target"],
                        position_inr=review["position_size_inr"],
                        reward_to_risk=review["reward_to_risk"]
                    )
                    if sim_res.get("success"):
                        rm.log_trade(review, result="OPEN", pnl_inr=0.0)
                        log_event(f"Order Registered: {sim_res.get('order_id')}")
                else:
                    BOT_STATE["status"] = "MONITORING / HOLD"
            else:
                log_event(f"⚠️ Market Data Error: {market.get('error')}")

        except Exception as e:
            log_event(f"❌ Error in loop: {e}")

        # Sleep 60 seconds between checks
        time.sleep(60)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        pos = BOT_STATE["active_position"]
        pos_html = """
        <div style="background:#1e293b; padding:15px; border-radius:10px; margin-bottom:20px;">
            <p style="color:#94a3b8; margin:0;">No active trade currently running. Waiting for next daily setup.</p>
        </div>
        """
        if pos:
            unrealized = pos.get("unrealized_pnl_inr", 0.0)
            color = "#10b981" if unrealized >= 0 else "#ef4444"
            pos_html = f"""
            <div style="background:#1e293b; padding:15px; border-radius:10px; margin-bottom:20px; border-left: 5px solid {color};">
                <h3 style="margin:0 0 10px 0; color:#38bdf8;">ACTIVE {pos['direction']} POSITION</h3>
                <p style="margin:4px 0;"><b>Entry:</b> ${pos['entry_price']:,.2f}</p>
                <p style="margin:4px 0;"><b>Stop Loss:</b> ${pos['stop_loss']:,.2f}</p>
                <p style="margin:4px 0;"><b>Target:</b> ${pos['take_profit']:,.2f}</p>
                <p style="margin:4px 0;"><b>Unrealized P&L:</b> <span style="color:{color}; font-weight:bold; font-size:18px;">Rs {unrealized:+.2f}</span></p>
            </div>
            """

        logs_html = "".join([f"<li style='margin:4px 0; font-family:monospace; color:#cbd5e1;'>{log}</li>" for log in BOT_STATE["recent_logs"][:10]])

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MADE BY ALEX — Crypto Bot 24/7</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#0f172a; color:#f8fafc; margin:0; padding:20px; }}
        .card {{ background:#1e293b; padding:18px; border-radius:12px; margin-bottom:15px; }}
        .header {{ text-align:center; padding:10px 0 20px 0; }}
        .badge {{ background:#10b981; color:#0f172a; padding:4px 10px; border-radius:20px; font-weight:bold; font-size:12px; }}
        .badge-mode {{ background:#f59e0b; color:#0f172a; padding:4px 10px; border-radius:20px; font-weight:bold; font-size:12px; }}
        .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
        .stat {{ background:#334155; padding:12px; border-radius:8px; text-align:center; }}
        .val {{ font-size:20px; font-weight:bold; margin-top:5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin:0; color:#38bdf8;">MADE BY ALEX</h2>
        <p style="color:#94a3b8; margin:5px 0 10px 0;">AI Crypto Trading System 24/7</p>
        <span class="badge">RUNNING 24/7 🟢</span>
        <span class="badge-mode">MODE: {BOT_STATE['mode']}</span>
    </div>

    <div class="grid">
        <div class="stat">
            <div style="color:#94a3b8; font-size:13px;">Bitcoin Live</div>
            <div class="val" style="color:#facc15;">${BOT_STATE['btc_price']:,.2f}</div>
        </div>
        <div class="stat">
            <div style="color:#94a3b8; font-size:13px;">RSI (14)</div>
            <div class="val">{BOT_STATE['rsi_14']}</div>
        </div>
    </div>

    <h3 style="margin:20px 0 10px 0;">Trade Position</h3>
    {pos_html}

    <div class="grid">
        <div class="stat">
            <div style="color:#94a3b8; font-size:13px;">Total Trades</div>
            <div class="val">{BOT_STATE['total_trades']}</div>
        </div>
        <div class="stat">
            <div style="color:#94a3b8; font-size:13px;">Total P&L</div>
            <div class="val" style="color:#38bdf8;">Rs {BOT_STATE['total_pnl_inr']:+.2f}</div>
        </div>
    </div>

    <h3 style="margin:20px 0 10px 0;">Live Activity Log</h3>
    <div class="card">
        <ul style="padding-left:15px; margin:0;">
            {logs_html}
        </ul>
        <p style="font-size:11px; color:#64748b; margin-top:10px;">Page auto-refreshes every 30s • Last checked: {BOT_STATE['last_check_time']}</p>
    </div>
</body>
</html>"""
        self.wfile.write(html.encode("utf-8"))

def start_server():
    port = int(os.environ.get("PORT", 8080))
    # Start trading loop in background daemon thread
    worker = threading.Thread(target=background_trading_loop, daemon=True)
    worker.start()

    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    print(f"🌐 Web Dashboard live on http://0.0.0.0:{port}")
    server.serve_forever()

if __name__ == "__main__":
    start_server()
