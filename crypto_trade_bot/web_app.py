"""
Institutional-Grade AI Crypto Trading Terminal & Live Web Server
Features:
- Live TradingView 24/7 Charts
- Multi-Indicator Technical Analysis Monitor (RSI, MACD, EMA Stack, ATR)
- Real-time PnL & Position Tracking
- Paper Trading Execution Simulator with auto-recovery
- Modern Glassmorphism High-Tech UI
"""
import os
import sys
import time
import json
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

import config
from indicators import get_macd_signal
from market_data import fetch_btc_market_analysis
from risk_manager import RiskManager
from trade_reviewer import review_trade
from order_executor import OrderExecutor
from paper_engine import PaperTradingEngine

CSV_LOG_FILE = os.path.join(os.path.dirname(__file__), "trade_log.csv")

GLOBAL_RM = None
GLOBAL_PAPER = None

BOT_STATE = {
    "status": "RUNNING 24/7",
    "btc_price": 0.0,
    "rsi_14": 50.0,
    "trend": "NEUTRAL",
    "macd_signal": "NEUTRAL",
    "composite_score": 0,
    "last_check_time": "Initializing...",
    "active_position": None,
    "total_pnl_inr": 0.0,
    "total_trades": 0,
    "recent_logs": [],
    "pnl_history": [],
    "mode": config.TRADING_MODE
}


def log_event(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    entry = f"[{timestamp}] {message}"
    BOT_STATE["recent_logs"].insert(0, entry)
    if len(BOT_STATE["recent_logs"]) > 30:
        BOT_STATE["recent_logs"].pop()
    print(entry)


def background_trading_loop():
    global GLOBAL_RM, GLOBAL_PAPER
    GLOBAL_RM = RiskManager()
    GLOBAL_PAPER = PaperTradingEngine(risk_manager=GLOBAL_RM)
    executor = OrderExecutor(paper_engine=GLOBAL_PAPER)

    log_event("🚀 24/7 Cloud Trading Worker Active! Starting AI scanner...")

    while True:
        try:
            BOT_STATE["last_check_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            market = fetch_btc_market_analysis()
            if market.get("success"):
                current_price = market["current_price"]
                BOT_STATE["btc_price"] = current_price
                BOT_STATE["rsi_14"] = market.get("rsi_14", 50.0)
                BOT_STATE["trend"] = market.get("trend", "NEUTRAL")
                BOT_STATE["macd_signal"] = market.get("macd_signal", "NEUTRAL")
                BOT_STATE["composite_score"] = market.get("composite_score", 0)

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
        # 1. API Endpoints
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

        # 2. CSV Download
        if self.path.startswith("/download/csv"):
            if os.path.exists(CSV_LOG_FILE):
                with open(CSV_LOG_FILE, "rb") as f:
                    csv_data = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", 'attachment; filename="trade_log.csv"')
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
        if pos:
            unrealized = pos.get("unrealized_pnl_inr", 0.0)
            color = "#10b981" if unrealized >= 0 else "#ef4444"
            direction_color = "#10b981" if pos['direction'] == 'LONG' else "#f43f5e"
            pos_html = f"""
            <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%); padding:22px; border-radius:16px; margin-bottom:20px; border: 1px solid rgba(255,255,255,0.08); border-left: 6px solid {direction_color}; box-shadow: 0 10px 30px rgba(0,0,0,0.4);">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#94a3b8; font-weight:600;">Active Trade</span>
                        <h3 style="margin:2px 0 0 0; font-size:20px; color:{direction_color}; font-weight:800;">{pos['direction']} BITCOIN</h3>
                    </div>
                    <span style="background:{direction_color}; color:#fff; padding:4px 12px; border-radius:20px; font-weight:700; font-size:11px; letter-spacing:0.5px;">RUNNING LIVE</span>
                </div>
                <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:14px; margin-top:16px; background:rgba(0,0,0,0.25); padding:14px; border-radius:12px;">
                    <div><span style="color:#94a3b8; font-size:11px; display:block;">Entry Price</span> <b style="font-size:15px; color:#f8fafc;">${pos['entry_price']:,.2f}</b></div>
                    <div><span style="color:#94a3b8; font-size:11px; display:block;">Purchase Size</span> <b style="font-size:15px; color:#facc15;">Rs {pos.get('position_inr', config.MAX_ORDER_VALUE_INR):,.2f}</b></div>
                    <div><span style="color:#94a3b8; font-size:11px; display:block;">Stop Loss</span> <b style="font-size:15px; color:#f87171;">${pos['stop_loss']:,.2f}</b></div>
                    <div><span style="color:#94a3b8; font-size:11px; display:block;">Take Profit</span> <b style="font-size:15px; color:#4ade80;">${pos['take_profit']:,.2f}</b></div>
                </div>
                <div style="margin-top:16px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.06); display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#94a3b8; font-size:13px; font-weight:500;">Unrealized P&L:</span>
                    <span style="color:{color}; font-size:26px; font-weight:800; text-shadow: 0 0 20px {color}44;">Rs {unrealized:+.2f}</span>
                </div>
            </div>
            """
        else:
            pos_html = """
            <div style="background: rgba(30, 41, 59, 0.4); padding:20px; border-radius:14px; margin-bottom:20px; border: 1px dashed rgba(255,255,255,0.1); text-align:center;">
                <span style="font-size:24px; display:block; margin-bottom:6px;">⏳</span>
                <p style="color:#94a3b8; margin:0; font-size:14px; font-weight:500;">No active position at the moment. Quant bot is scanning BTC candles for high-probability setups...</p>
            </div>
            """

        logs_html = "".join([f"<li class='log-item'>{log}</li>" for log in BOT_STATE["recent_logs"][:8]])
        if not logs_html:
            logs_html = "<li class='log-item' style='color:#64748b;'>Waiting for first scan telemetry...</li>"

        rm = GLOBAL_RM or RiskManager()
        trades = rm.history.get("trades", [])
        trades_rows = ""
        for t in reversed(trades[-10:]):
            pnl_val = t.get("pnl_inr", 0.0)
            res_color = "#10b981" if pnl_val > 0 or t.get("result") == "WIN" else ("#ef4444" if pnl_val < 0 or t.get("result") == "LOSS" else "#38bdf8")
            trades_rows += f"""
            <tr>
                <td style="color:#cbd5e1;">{t.get('date', '').split(' ')[0]}</td>
                <td style="font-weight:700; color:{'#10b981' if t.get('direction') == 'LONG' else '#ef4444'};">{t.get('direction', '')}</td>
                <td>${t.get('entry', 0):,.1f}</td>
                <td><span style="background:{res_color}22; color:{res_color}; padding:3px 10px; border-radius:12px; font-weight:700; font-size:11px; border:1px solid {res_color}44;">{t.get('result', '')}</span></td>
                <td style="font-weight:700; color:{res_color};">Rs {pnl_val:+.2f}</td>
            </tr>
            """
        if not trades_rows:
            trades_rows = "<tr><td colspan='5' style='text-align:center; padding:20px; color:#64748b;'>No trade history yet. System restarted with fresh Rs 5,000 capital.</td></tr>"

        current_balance = config.ACCOUNT_SIZE_INR + BOT_STATE['total_pnl_inr']

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MADE BY ALEX — AI Crypto Terminal</title>
    <meta http-equiv="refresh" content="30">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-dark: #07090e;
            --card-bg: rgba(18, 24, 38, 0.7);
            --card-border: rgba(255, 255, 255, 0.08);
            --primary: #38bdf8;
            --success: #10b981;
            --danger: #ef4444;
            --warning: #f59e0b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: 'Plus Jakarta Sans', sans-serif;
            background-color: var(--bg-dark);
            background-image: 
                radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.08) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(99, 102, 241, 0.08) 0px, transparent 50%);
            color: var(--text-main);
            margin: 0;
            padding: 24px 16px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            text-align: center;
            padding: 24px 20px;
            background: linear-gradient(180deg, rgba(30, 41, 59, 0.5) 0%, rgba(15, 23, 42, 0.3) 100%);
            border: 1px solid var(--card-border);
            border-radius: 18px;
            backdrop-filter: blur(16px);
            margin-bottom: 22px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
        }}
        .logo-title {{
            font-size: 30px;
            font-weight: 800;
            background: linear-gradient(135deg, #38bdf8 0%, #818cf8 50%, #c084fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0;
            letter-spacing: 1.5px;
        }}
        .subtitle {{ color: var(--text-muted); font-size: 13px; margin: 6px 0 16px 0; font-weight: 500; }}
        .badges {{ display: flex; gap: 10px; justify-content: center; flex-wrap: wrap; }}
        .badge {{
            background: rgba(16, 185, 129, 0.12);
            color: #34d399;
            border: 1px solid rgba(52, 211, 153, 0.3);
            padding: 6px 14px;
            border-radius: 9999px;
            font-weight: 700;
            font-size: 11px;
            letter-spacing: 0.5px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .badge-mode {{
            background: rgba(245, 158, 11, 0.12);
            color: #fbbf24;
            border: 1px solid rgba(251, 191, 36, 0.3);
            padding: 6px 14px;
            border-radius: 9999px;
            font-weight: 700;
            font-size: 11px;
            letter-spacing: 0.5px;
        }}
        .grid-4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; margin-bottom: 22px; }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            padding: 20px;
            border-radius: 16px;
            backdrop-filter: blur(12px);
            transition: all 0.25s ease;
        }}
        .card:hover {{
            transform: translateY(-3px);
            border-color: rgba(255, 255, 255, 0.18);
            box-shadow: 0 12px 30px rgba(0,0,0,0.5);
        }}
        .card-label {{ font-size: 11px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }}
        .card-val {{ font-size: 26px; font-weight: 800; margin: 8px 0 4px 0; letter-spacing: -0.5px; }}
        .card-sub {{ font-size: 11px; color: #64748b; font-weight: 500; }}
        .chart-box {{
            height: 440px;
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid var(--card-border);
            margin-bottom: 22px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 700;
            color: #e2e8f0;
            margin: 22px 0 12px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{
            text-align: left;
            color: var(--text-muted);
            font-size: 11px;
            padding: 12px 10px;
            border-bottom: 1px solid var(--card-border);
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }}
        td {{ padding: 14px 10px; border-bottom: 1px solid rgba(255, 255, 255, 0.04); font-size: 13px; }}
        .btn-download {{
            background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%);
            color: #fff;
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 12px;
            font-weight: 700;
            text-decoration: none;
            transition: opacity 0.2s;
            box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
        }}
        .btn-download:hover {{ opacity: 0.9; }}
        .log-item {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            padding: 8px 0;
            color: #cbd5e1;
            border-bottom: 1px solid rgba(255, 255, 255, 0.04);
            list-style: none;
        }}
        .pulse {{
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            animation: pulse 1.8s infinite;
        }}
        @keyframes pulse {{
            0% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
            70% {{ transform: scale(1); box-shadow: 0 0 0 8px rgba(16, 185, 129, 0); }}
            100% {{ transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1 class="logo-title">MADE BY ALEX</h1>
            <p class="subtitle">Institutional AI Crypto Trading Terminal & Quant Risk Engine</p>
            <div class="badges">
                <span class="badge"><span class="pulse"></span> 24/7 CLOUD ACTIVE</span>
                <span class="badge-mode">MODE: {BOT_STATE['mode']}</span>
                <span class="badge" style="background:rgba(56, 189, 248, 0.12); color:#38bdf8; border-color:rgba(56, 189, 248, 0.3);">
                    SCORE: {BOT_STATE['composite_score']:+d} ({BOT_STATE['macd_signal']})
                </span>
            </div>
        </div>

        <!-- 4 Key Capital & Portfolio Cards -->
        <div class="grid-4">
            <div class="card" style="border-top: 3px solid #38bdf8;">
                <div class="card-label">Allocated Capital</div>
                <div class="card-val" style="color: #38bdf8;">Rs {config.ACCOUNT_SIZE_INR:,.2f}</div>
                <div class="card-sub">Base allocated principal</div>
            </div>
            <div class="card" style="border-top: 3px solid #10b981;">
                <div class="card-label">Current Account Balance</div>
                <div class="card-val" style="color: #10b981;">Rs {current_balance:,.2f}</div>
                <div class="card-sub">Capital + Net Realized PnL</div>
            </div>
            <div class="card" style="border-top: 3px solid #f59e0b;">
                <div class="card-label">Max Order Cap (30%)</div>
                <div class="card-val" style="color: #f59e0b;">Rs {config.MAX_ORDER_VALUE_INR:,.0f}</div>
                <div class="card-sub">Strict risk per single trade</div>
            </div>
            <div class="card" style="border-top: 3px solid #a855f7;">
                <div class="card-label">Bitcoin Live Price</div>
                <div class="card-val" style="color: #facc15;">${BOT_STATE['btc_price']:,.2f}</div>
                <div class="card-sub">RSI (14): {BOT_STATE['rsi_14']} • {BOT_STATE['trend']}</div>
            </div>
        </div>

        <!-- Live TradingView Chart -->
        <div class="section-title">📊 Live BTC/USDT Market Chart</div>
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

        <!-- Position & P&L Monitor -->
        <div class="section-title">⚡ Real-time Position & P&L Monitor</div>
        {pos_html}

        <!-- Trade History Table -->
        <div class="card" style="margin-bottom: 22px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;">
                <div class="section-title" style="margin:0;">📜 Trade History & Performance</div>
                <a href="/download/csv" class="btn-download">📥 Download CSV</a>
            </div>
            <div style="overflow-x:auto;">
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
        </div>

        <!-- Real-time Activity Log -->
        <div class="card">
            <div class="section-title" style="margin:0 0 12px 0;">📡 Live Bot Scanner Logs</div>
            <ul style="padding:0; margin:0;">
                {logs_html}
            </ul>
            <p style="font-size:11px; color:#64748b; margin:14px 0 0 0; text-align:right;">
                Auto-refreshes every 30s • Last scan: {BOT_STATE['last_check_time']}
            </p>
        </div>
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
