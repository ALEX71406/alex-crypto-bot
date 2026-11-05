"""
Web Dashboard & 24/7 Cloud Background Worker for MADE BY ALEX
Features:
- Live Interactive TradingView Bitcoin Chart
- Visual P&L / Equity Growth Curve
- Active Trade Card (Entry, SL, TP, Unrealized P&L in INR)
- Daily Trade Ledger & Journal Table directly on the page
- Endpoints:
  * GET /              -> Mobile responsive dashboard with live charts & trade table
  * GET /api/sync      -> JSON endpoint to sync online cloud trades to local PC
  * GET /download/csv  -> One-click download of trade_log.csv for Excel/Sheets
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
from risk_manager import RiskManager, CSV_LOG_FILE
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

# Global references for sync handler
GLOBAL_RM = None
GLOBAL_PAPER = None

def log_event(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    entry = f"[{ts}] {msg}"
    print(entry, flush=True)
    BOT_STATE["recent_logs"].insert(0, entry)
    if len(BOT_STATE["recent_logs"]) > 25:
        BOT_STATE["recent_logs"].pop()

def background_trading_loop():
    global GLOBAL_RM, GLOBAL_PAPER
    log_event("🚀 24/7 Cloud Trading Worker Active!")
    GLOBAL_RM = RiskManager()
    GLOBAL_PAPER = PaperTradingEngine(risk_manager=GLOBAL_RM)
    executor = OrderExecutor(paper_engine=GLOBAL_PAPER)

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
                pos_update = GLOBAL_PAPER.update_price(current_price)
                if pos_update["event"] == "STOP_LOSS_HIT":
                    log_event(f"🛑 STOP-LOSS HIT at ${current_price:,.2f}! Net PnL: Rs {pos_update['details']['net_pnl_inr']}")
                    BOT_STATE["pnl_history"].append(GLOBAL_RM.history.get("total_pnl_inr", 0.0))
                elif pos_update["event"] == "TAKE_PROFIT_HIT":
                    log_event(f"🎯 TAKE-PROFIT HIT at ${current_price:,.2f}! Net PnL: Rs {pos_update['details']['net_pnl_inr']}")
                    BOT_STATE["pnl_history"].append(GLOBAL_RM.history.get("total_pnl_inr", 0.0))

                active_pos = GLOBAL_PAPER.get_active_position()
                BOT_STATE["active_position"] = active_pos
                BOT_STATE["total_pnl_inr"] = GLOBAL_RM.history.get("total_pnl_inr", 0.0)
                BOT_STATE["total_trades"] = len(GLOBAL_RM.history.get("trades", []))

                has_active = GLOBAL_PAPER.has_active_position()
                is_losing = GLOBAL_PAPER.has_active_losing_position(current_price)
                consec = GLOBAL_RM.history.get("consecutive_losses", 0)

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
                        GLOBAL_RM.log_trade(review, result="OPEN", pnl_inr=0.0)
                        log_event(f"Order Placed & Tracked: {sim_res.get('order_id')}")

        except Exception as e:
            log_event(f"❌ Error in loop: {e}")

        time.sleep(60)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. API Endpoint for Syncing Local & Cloud Data
        if self.path.startswith("/api/sync") or self.path.startswith("/api/trades"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            rm = GLOBAL_RM or RiskManager()
            paper = GLOBAL_PAPER or PaperTradingEngine(risk_manager=rm)

            sync_payload = {
                "status": "SUCCESS",
                "synced_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "account_size_inr": config.ACCOUNT_SIZE_INR,
                "current_btc_price": BOT_STATE["btc_price"],
                "total_pnl_inr": rm.history.get("total_pnl_inr", 0.0),
                "wins": rm.history.get("wins", 0),
                "losses": rm.history.get("losses", 0),
                "total_trades": len(rm.history.get("trades", [])),
                "active_position": paper.get_active_position(),
                "trades": rm.history.get("trades", []),
                "closed_trades": paper.state.get("closed_trades", [])
            }
            self.wfile.write(json.dumps(sync_payload, indent=2).encode("utf-8"))
            return

        # 2. Endpoint to Download trade_log.csv for Excel
        if self.path.startswith("/download/csv"):
            if os.path.exists(CSV_LOG_FILE):
                with open(CSV_LOG_FILE, "rb") as f:
                    csv_data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=\"trade_log.csv\"")
                self.end_headers()
                self.wfile.write(csv_data)
                return
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b"trade_log.csv not generated yet.")
                return

        # 3. Web Dashboard HTML Page
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
                    <div><span style="color:#94a3b8;">Trade Purchase Value:</span> <b style="color:#facc15;">Rs {pos.get('position_inr', config.MAX_ORDER_VALUE_INR):,.2f}</b></div>
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

        # Build trade history table
        rm = GLOBAL_RM or RiskManager()
        trades = rm.history.get("trades", [])
        trades_rows = ""
        for t in reversed(trades[-10:]):
            pnl_val = t.get("pnl_inr", 0.0)
            res_color = "#10b981" if pnl_val > 0 or t.get("result") == "WIN" else ("#ef4444" if pnl_val < 0 or t.get("result") == "LOSS" else "#38bdf8")
            trades_rows += f"""
            <tr style="border-bottom:1px solid #334155; font-size:13px;">
                <td style="padding:8px 4px;">{t.get('date', '').split(' ')[0]}</td>
                <td style="padding:8px 4px; font-weight:bold;">{t.get('direction', '')}</td>
                <td style="padding:8px 4px;">${t.get('entry', 0):,.1f}</td>
                <td style="padding:8px 4px;"><span style="color:{res_color}; font-weight:bold;">{t.get('result', '')}</span></td>
                <td style="padding:8px 4px; color:{res_color}; font-weight:bold;">Rs {pnl_val:+.2f}</td>
            </tr>
            """
        if not trades_rows:
            trades_rows = "<tr><td colspan='5' style='text-align:center; padding:15px; color:#94a3b8;'>No trade history yet.</td></tr>"

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
        .btn {{ display:inline-block; background:#38bdf8; color:#0b1120; padding:8px 16px; border-radius:8px; font-weight:bold; text-decoration:none; margin-top:10px; font-size:13px; }}
        table {{ width:100%; border-collapse:collapse; margin-top:10px; }}
        th {{ text-align:left; color:#94a3b8; font-size:12px; padding:6px 4px; border-bottom:1px solid #475569; }}
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

    <!-- Capital & Account Summary Cards -->
    <div class="grid" style="grid-template-columns: 1fr 1fr; margin-bottom: 12px;">
        <div class="stat" style="border-top: 3px solid #38bdf8;">
            <div style="color:#94a3b8; font-size:12px;">Allocated Capital</div>
            <div class="val" style="color:#38bdf8;">Rs {config.ACCOUNT_SIZE_INR:,.2f}</div>
            <div style="color:#64748b; font-size:10px; margin-top:3px;">Base Initial Balance</div>
        </div>
        <div class="stat" style="border-top: 3px solid #10b981;">
            <div style="color:#94a3b8; font-size:12px;">Current Account Balance</div>
            <div class="val" style="color:#10b981;">Rs {(config.ACCOUNT_SIZE_INR + BOT_STATE['total_pnl_inr']):,.2f}</div>
            <div style="color:#64748b; font-size:10px; margin-top:3px;">Capital + Realized P&L</div>
        </div>
    </div>
    <div class="grid">
        <div class="stat">
            <div style="color:#94a3b8; font-size:12px;">Max Order Size (Cap)</div>
            <div class="val" style="color:#f59e0b;">Rs {config.MAX_ORDER_VALUE_INR:,.0f}</div>
            <div style="color:#64748b; font-size:10px; margin-top:3px;">Per Trade Allocation</div>
        </div>
        <div class="stat">
            <div style="color:#94a3b8; font-size:12px;">Booked P&L / Trades</div>
            <div class="val" style="color:#38bdf8;">Rs {BOT_STATE['total_pnl_inr']:+.2f} <span style="font-size:13px; color:#94a3b8;">({BOT_STATE['total_trades']} trades)</span></div>
            <div style="color:#64748b; font-size:10px; margin-top:3px;">Fresh Cycle</div>
        </div>
    </div>

    <!-- Trade History & Daily Sheets Table -->
    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <h3 style="margin:0; font-size:16px; color:#e2e8f0;">📊 Trade History & Sheets</h3>
            <a href="/download/csv" class="btn" style="margin:0; padding:5px 10px; font-size:11px;">📥 Download CSV</a>
        </div>
        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>Result</th>
                    <th>PnL</th>
                </tr>
            </thead>
            <tbody>
                {trades_rows}
            </tbody>
        </table>
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


