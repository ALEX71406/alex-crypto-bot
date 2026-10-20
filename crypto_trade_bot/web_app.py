"""
Web Dashboard & 24/7 Cloud Background Worker for MADE BY ALEX
Features:
- Live Interactive TradingView Bitcoin Chart
- Visual P&L / Equity Growth Curve
- Active Trade Card (Entry, SL, TP, Unrealized P&L in INR)
- Real-time Activity Ledger & Auto-refresh
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
    "recent_logs": [],
    "pnl_history": [0.0]
}

def log_event(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry, flush=True)
    BOT_STATE["recent_logs"].insert(0, entry)
    if len(BOT_STATE["recent_logs"]) > 20:
        BOT_STATE["recent_logs"].pop()

def background_trading_loop():
    log_event("🚀 24/7 Cloud Trading Worker Active!")
    rm = RiskManager()
    paper = PaperTradingEngine(risk_manager=rm)
    executor = OrderExecutor(paper_engine=paper)

    while True:
        try:
            BOT_STATE["status"] = "ACTIVE"
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            BOT_STATE["last_check_time"] = now_str

            market = fetch_btc_market_analysis()
            if market.get("success"):
                current_price = market["current_price"]
                BOT_STATE["btc_price"] = current_price
                BOT_STATE["rsi_14"] = market["rsi_14"]
                BOT_STATE["trend"] = market["trend"]

                # Update active position
                pos_update = paper.update_price(current_price)
                if pos_update["event"] == "STOP_LOSS_HIT":
                    log_event(f"🛑 STOP-LOSS HIT at ${current_price:,.2f}! Net PnL: Rs {pos_update['details']['net_pnl_inr']}")
                    BOT_STATE["pnl_history"].append(rm.history.get("total_pnl_inr", 0.0))
                elif pos_update["event"] == "TAKE_PROFIT_HIT":
                    log_event(f"🎯 TAKE-PROFIT HIT at ${current_price:,.2f}! Net PnL: Rs {pos_update['details']['net_pnl_inr']}")
                    BOT_STATE["pnl_history"].append(rm.history.get("total_pnl_inr", 0.0))

                active_pos = paper.get_active_position()
                BOT_STATE["active_position"] = active_pos
                BOT_STATE["total_pnl_inr"] = rm.history.get("total_pnl_inr", 0.0)
                BOT_STATE["total_trades"] = len(rm.history.get("trades", []))

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
                        log_event(f"Order Placed & Tracked: {sim_res.get('order_id')}")

        except Exception as e:
            log_event(f"❌ Error in loop: {e}")

        time.sleep(60)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        pos = BOT_STATE["active_position"]
        pos_html = """
        <div style="background:#1e293b; padding:15px; border-radius:10px; margin-bottom:15px;">
            <p style="color:#94a3b8; margin:0;">No active position. Waiting for next daily candle setup.</p>
        </div>
        """
        if pos:
            unrealized = pos.get("unrealized_pnl_inr", 0.0)
            color = "#10b981" if unrealized >= 0 else "#ef4444"
            pos_html = f"""
            <div style="background:#1e293b; padding:18px; border-radius:12px; margin-bottom:15px; border-left: 6px solid {color}; box-shadow:0 4px 6px rgba(0,0,0,0.3);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <h3 style="margin:0; color:#38bdf8;">ACTIVE {pos['direction']} POSITION</h3>
                    <span style="background:{color}; color:#fff; padding:3px 8px; border-radius:12px; font-weight:bold; font-size:12px;">LIVE</span>
                </div>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-top:12px;">
                    <div><span style="color:#94a3b8;">Entry:</span> <b>${pos['entry_price']:,.2f}</b></div>
                    <div><span style="color:#94a3b8;">Risk Cap:</span> <b>Rs {pos.get('risk_amount_inr', 25.0):.2f}</b></div>
                    <div><span style="color:#ef4444;">Stop Loss:</span> <b>${pos['stop_loss']:,.2f}</b></div>
                    <div><span style="color:#10b981;">Target (TP):</span> <b>${pos['take_profit']:,.2f}</b></div>
                </div>
                <div style="margin-top:14px; padding-top:10px; border-top:1px solid #334155; display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#94a3b8;">Unrealized P&L:</span>
                    <span style="color:{color}; font-size:22px; font-weight:bold;">Rs {unrealized:+.2f}</span>
                </div>
            </div>
            """

        logs_html = "".join([f"<li style='margin:4px 0; font-family:monospace; color:#cbd5e1;'>{log}</li>" for log in BOT_STATE["recent_logs"][:8]])

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MADE BY ALEX — Crypto Trading Terminal</title>
    <meta http-equiv="refresh" content="30">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background:#0b1120; color:#f8fafc; margin:0; padding:15px; }}
        .header {{ text-align:center; padding:10px 0 15px 0; }}
        .badge {{ background:#10b981; color:#0f172a; padding:5px 12px; border-radius:20px; font-weight:bold; font-size:12px; }}
        .badge-mode {{ background:#f59e0b; color:#0f172a; padding:5px 12px; border-radius:20px; font-weight:bold; font-size:12px; }}
        .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; margin-bottom:15px; }}
        .stat {{ background:#1e293b; padding:14px; border-radius:10px; text-align:center; }}
        .val {{ font-size:22px; font-weight:bold; margin-top:5px; }}
        .card {{ background:#1e293b; padding:15px; border-radius:12px; margin-bottom:15px; }}
        .chart-box {{ height:380px; border-radius:12px; overflow:hidden; margin-bottom:15px; }}
    </style>
</head>
<body>
    <div class="header">
        <h2 style="margin:0; color:#38bdf8; letter-spacing:1px;">MADE BY ALEX</h2>
        <p style="color:#94a3b8; margin:4px 0 10px 0; font-size:14px;">Institutional AI Crypto Trading System</p>
        <span class="badge">RUNNING 24/7 🟢</span>
        <span class="badge-mode">MODE: {BOT_STATE['mode']}</span>
    </div>

    <!-- Live Stats -->
    <div class="grid">
        <div class="stat">
            <div style="color:#94a3b8; font-size:12px;">Bitcoin Live</div>
            <div class="val" style="color:#facc15;">${BOT_STATE['btc_price']:,.2f}</div>
        </div>
        <div class="stat">
            <div style="color:#94a3b8; font-size:12px;">RSI (14-period)</div>
            <div class="val">{BOT_STATE['rsi_14']}</div>
        </div>
    </div>

    <!-- Live TradingView Chart -->
    <h3 style="margin:0 0 8px 0; font-size:16px; color:#e2e8f0;">📈 Live Bitcoin Chart</h3>
    <div class="chart-box">
        <div id="tradingview_chart" style="height:100%; width:100%;"></div>
        <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
        <script type="text/javascript">
        new TradingView.widget({{
            "autosize": true,
            "symbol": "BINANCE:BTCUSDT",
            "interval": "D",
            "timezone": "Asia/Kolkata",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "toolbar_bg": "#0b1120",
            "enable_publishing": false,
            "hide_side_toolbar": false,
            "container_id": "tradingview_chart"
        }});
        </script>
    </div>

    <!-- Active Trade Details -->
    <h3 style="margin:15px 0 8px 0; font-size:16px; color:#e2e8f0;">⚡ Position & P&L Monitor</h3>
    {pos_html}

    <div class="grid">
        <div class="stat">
            <div style="color:#94a3b8; font-size:12px;">Total Trades</div>
            <div class="val">{BOT_STATE['total_trades']}</div>
        </div>
        <div class="stat">
            <div style="color:#94a3b8; font-size:12px;">Booked P&L</div>
            <div class="val" style="color:#38bdf8;">Rs {BOT_STATE['total_pnl_inr']:+.2f}</div>
        </div>
    </div>

    <!-- Activity Log -->
    <h3 style="margin:15px 0 8px 0; font-size:16px; color:#e2e8f0;">📋 Real-time Activity Log</h3>
    <div class="card">
        <ul style="padding-left:18px; margin:0; font-size:13px;">
            {logs_html}
        </ul>
        <p style="font-size:11px; color:#64748b; margin:10px 0 0 0;">Auto-refreshes every 30s • Last scan: {BOT_STATE['last_check_time']}</p>
    </div>
</body>
</html>"""
        self.wfile.write(html.encode("utf-8"))

def start_server():
    port = int(os.environ.get("PORT", 8080))
    worker = threading.Thread(target=background_trading_loop, daemon=True)
    worker.start()
    server = HTTPServer(("0.0.0.0", port), DashboardHandler)
    server.serve_forever()

if __name__ == "__main__":
    start_server()
