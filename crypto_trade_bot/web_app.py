"""
Institutional-Grade AI Crypto Trading Terminal & Live Web Server
Theme: Apple VisionOS / macOS Liquid Glass Light Mode
Features:
- Premium Frosted Glassmorphism (Liquid Glass)
- Ambient Mesh Gradients
- Real-time PnL & Position Tracking
- Live TradingView Chart
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
            color = "#059669" if unrealized >= 0 else "#dc2626"
            direction_color = "#059669" if pos['direction'] == 'LONG' else "#e11d48"
            pos_html = f"""
            <div class="liquid-card active-pos-card" style="border-left: 6px solid {direction_color};">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-size:11px; text-transform:uppercase; letter-spacing:1px; color:#64748b; font-weight:700;">Active Position</span>
                        <h3 style="margin:2px 0 0 0; font-size:20px; color:{direction_color}; font-weight:800;">{pos['direction']} BITCOIN</h3>
                    </div>
                    <span class="badge" style="background:{direction_color}18; color:{direction_color}; border-color:{direction_color}44;">● LIVE ORDER</span>
                </div>
                <div class="pos-grid">
                    <div><span class="sub-label">Entry Price</span> <b class="val-text">${pos['entry_price']:,.2f}</b></div>
                    <div><span class="sub-label">Purchase Size</span> <b class="val-text" style="color:#d97706;">Rs {pos.get('position_inr', config.MAX_ORDER_VALUE_INR):,.2f}</b></div>
                    <div><span class="sub-label">Stop Loss</span> <b class="val-text" style="color:#dc2626;">${pos['stop_loss']:,.2f}</b></div>
                    <div><span class="sub-label">Take Profit</span> <b class="val-text" style="color:#059669;">${pos['take_profit']:,.2f}</b></div>
                </div>
                <div style="margin-top:16px; padding-top:14px; border-top:1px solid rgba(0,0,0,0.06); display:flex; justify-content:space-between; align-items:center;">
                    <span style="color:#475569; font-size:13px; font-weight:600;">Unrealized P&L:</span>
                    <span style="color:{color}; font-size:26px; font-weight:800;">Rs {unrealized:+.2f}</span>
                </div>
            </div>
            """
        else:
            pos_html = """
            <div class="liquid-card" style="text-align:center; padding:28px 20px; margin-bottom:22px;">
                <span style="font-size:28px; display:inline-block; margin-bottom:8px;">⏳</span>
                <p style="color:#475569; margin:0; font-size:14px; font-weight:600;">No active trade right now. Scanning live BTC candles for high-probability setups...</p>
            </div>
            """

        logs_html = "".join([f"<li class='log-item'>{log}</li>" for log in BOT_STATE["recent_logs"][:8]])
        if not logs_html:
            logs_html = "<li class='log-item' style='color:#94a3b8;'>Waiting for telemetry data...</li>"

        rm = GLOBAL_RM or RiskManager()
        trades = rm.history.get("trades", [])
        trades_rows = ""
        for t in reversed(trades[-10:]):
            pnl_val = t.get("pnl_inr", 0.0)
            res_color = "#059669" if pnl_val > 0 or t.get("result") == "WIN" else ("#dc2626" if pnl_val < 0 or t.get("result") == "LOSS" else "#0284c7")
            trades_rows += f"""
            <tr>
                <td style="color:#475569; font-weight:600;">{t.get('date', '').split(' ')[0]}</td>
                <td style="font-weight:700; color:{'#059669' if t.get('direction') == 'LONG' else '#dc2626'};">{t.get('direction', '')}</td>
                <td style="font-weight:600;">${t.get('entry', 0):,.1f}</td>
                <td><span style="background:{res_color}14; color:{res_color}; padding:4px 10px; border-radius:12px; font-weight:700; font-size:11px; border:1px solid {res_color}33;">{t.get('result', '')}</span></td>
                <td style="font-weight:700; color:{res_color};">Rs {pnl_val:+.2f}</td>
            </tr>
            """
        if not trades_rows:
            trades_rows = "<tr><td colspan='5' style='text-align:center; padding:24px; color:#64748b; font-weight:500;'>No trade history yet. System restarted with fresh Rs 5,000 capital.</td></tr>"

        current_balance = config.ACCOUNT_SIZE_INR + BOT_STATE['total_pnl_inr']

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MADE BY ALEX — Apple Liquid Glass Terminal</title>
    <meta http-equiv="refresh" content="30">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=SF+Pro+Display:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --liquid-bg: rgba(255, 255, 255, 0.65);
            --liquid-border: rgba(255, 255, 255, 0.85);
            --liquid-inner-shadow: inset 0 1px 1px 0 rgba(255, 255, 255, 0.9), 0 10px 30px rgba(0, 0, 0, 0.05);
            --text-heading: #0f172a;
            --text-body: #334155;
            --text-muted: #64748b;
            --accent-blue: #0284c7;
            --accent-green: #059669;
            --accent-purple: #7c3aed;
            --accent-amber: #d97706;
        }}
        * {{ box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Plus Jakarta Sans', sans-serif;
            background: linear-gradient(135deg, #f0f4f8 0%, #e2e8f0 50%, #dbeafe 100%);
            background-attachment: fixed;
            color: var(--text-heading);
            margin: 0;
            padding: 24px 16px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1180px; margin: 0 auto; }}

        /* Apple Liquid Glass Container */
        .liquid-card {{
            background: var(--liquid-bg);
            border: 1px solid var(--liquid-border);
            border-radius: 24px;
            backdrop-filter: blur(24px) saturate(180%);
            -webkit-backdrop-filter: blur(24px) saturate(180%);
            box-shadow: var(--liquid-inner-shadow);
            padding: 22px;
            margin-bottom: 22px;
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }}
        .liquid-card:hover {{
            transform: translateY(-2px);
            box-shadow: inset 0 1px 1px 0 rgba(255, 255, 255, 1), 0 16px 36px rgba(0, 0, 0, 0.08);
        }}

        .header {{
            text-align: center;
            padding: 28px 20px;
        }}
        .logo-title {{
            font-size: 32px;
            font-weight: 800;
            letter-spacing: -0.5px;
            background: linear-gradient(135deg, #0284c7 0%, #4f46e5 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin: 0;
        }}
        .subtitle {{
            color: var(--text-muted);
            font-size: 13px;
            margin: 6px 0 16px 0;
            font-weight: 600;
        }}
        .badges {{
            display: flex;
            gap: 10px;
            justify-content: center;
            flex-wrap: wrap;
        }}
        .badge {{
            background: rgba(255, 255, 255, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.9);
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
            color: #047857;
            padding: 6px 14px;
            border-radius: 9999px;
            font-weight: 700;
            font-size: 11px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        .badge-mode {{
            background: rgba(255, 255, 255, 0.8);
            border: 1px solid rgba(255, 255, 255, 0.9);
            color: #b45309;
            padding: 6px 14px;
            border-radius: 9999px;
            font-weight: 700;
            font-size: 11px;
        }}

        .grid-4 {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: 16px;
            margin-bottom: 22px;
        }}
        .card-label {{
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.8px;
        }}
        .card-val {{
            font-size: 26px;
            font-weight: 800;
            margin: 8px 0 4px 0;
            letter-spacing: -0.5px;
        }}
        .card-sub {{
            font-size: 11px;
            color: var(--text-muted);
            font-weight: 500;
        }}

        .chart-box {{
            height: 440px;
            border-radius: 24px;
            overflow: hidden;
            background: rgba(255, 255, 255, 0.7);
            border: 1px solid var(--liquid-border);
            box-shadow: var(--liquid-inner-shadow);
            margin-bottom: 22px;
        }}
        .section-title {{
            font-size: 16px;
            font-weight: 800;
            color: var(--text-heading);
            margin: 24px 0 12px 0;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .pos-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 12px;
            margin-top: 14px;
            background: rgba(255, 255, 255, 0.5);
            padding: 14px;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.8);
        }}
        .sub-label {{ color: var(--text-muted); font-size: 11px; display: block; font-weight: 600; }}
        .val-text {{ font-size: 15px; color: var(--text-heading); font-weight: 700; }}

        table {{ width: 100%; border-collapse: collapse; }}
        th {{
            text-align: left;
            color: var(--text-muted);
            font-size: 11px;
            padding: 12px 10px;
            border-bottom: 1px solid rgba(0, 0, 0, 0.08);
            text-transform: uppercase;
            letter-spacing: 0.6px;
            font-weight: 700;
        }}
        td {{
            padding: 14px 10px;
            border-bottom: 1px solid rgba(0, 0, 0, 0.04);
            font-size: 13px;
            color: var(--text-body);
        }}
        .btn-download {{
            background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%);
            color: #fff;
            padding: 7px 16px;
            border-radius: 12px;
            font-size: 12px;
            font-weight: 700;
            text-decoration: none;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.25);
            transition: opacity 0.2s;
        }}
        .btn-download:hover {{ opacity: 0.9; }}

        .log-item {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 12px;
            padding: 9px 0;
            color: #334155;
            border-bottom: 1px solid rgba(0, 0, 0, 0.04);
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
        <!-- Header in Apple Liquid Glass -->
        <div class="liquid-card header">
            <h1 class="logo-title">MADE BY ALEX</h1>
            <p class="subtitle">Institutional AI Crypto Terminal & Quant Engine</p>
            <div class="badges">
                <span class="badge"><span class="pulse"></span> 24/7 ACTIVE CLOUD</span>
                <span class="badge-mode">MODE: {BOT_STATE['mode']}</span>
                <span class="badge" style="color:#0284c7;">
                    SCORE: {BOT_STATE['composite_score']:+d} ({BOT_STATE['macd_signal']})
                </span>
            </div>
        </div>

        <!-- 4 Capital & Portfolio Cards -->
        <div class="grid-4">
            <div class="liquid-card">
                <div class="card-label">Allocated Capital</div>
                <div class="card-val" style="color: #0284c7;">Rs {config.ACCOUNT_SIZE_INR:,.2f}</div>
                <div class="card-sub">Base allocated principal</div>
            </div>
            <div class="liquid-card">
                <div class="card-label">Current Account Balance</div>
                <div class="card-val" style="color: #059669;">Rs {current_balance:,.2f}</div>
                <div class="card-sub">Capital + Net Realized PnL</div>
            </div>
            <div class="liquid-card">
                <div class="card-label">Max Order Cap (30%)</div>
                <div class="card-val" style="color: #d97706;">Rs {config.MAX_ORDER_VALUE_INR:,.0f}</div>
                <div class="card-sub">Risk budget per trade</div>
            </div>
            <div class="liquid-card">
                <div class="card-label">Bitcoin Live Price</div>
                <div class="card-val" style="color: #4f46e5;">${BOT_STATE['btc_price']:,.2f}</div>
                <div class="card-sub">RSI (14): {BOT_STATE['rsi_14']} • {BOT_STATE['trend']}</div>
            </div>
        </div>

        <!-- TradingView Chart -->
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
                "theme": "light",
                "style": "1",
                "locale": "en",
                "toolbar_bg": "#f0f4f8",
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
        <div class="liquid-card" style="margin-bottom: 22px;">
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
        <div class="liquid-card">
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
