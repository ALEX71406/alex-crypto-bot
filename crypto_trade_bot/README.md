# 🤖 Pro AI Crypto Trading System (Trading With Sidhant Model)

Institutional-grade AI crypto trading engine based on **"Trading With Sidhant"** 5 Strict Rules + **Quantitative Filters** (RSI, 20 EMA, 14 ATR).
Optimized for **Rs 1,000** capital on **Delta Exchange India**.

---

## 📁 Project Architecture: `D:\crypto_trade_bot`

```
D:\crypto_trade_bot/
│
├── config.py             # Capital (Rs 1,000), Risk limits (Rs 25), Exchange URLs
├── indicators.py         # Quant engine: RSI, 20 EMA, 50 EMA, 14-day ATR volatility
├── market_data.py        # 50-day candle data fetcher & live indicator calculator
├── risk_manager.py       # Circuit breaker, P&L tracker, Win rate, and CSV logging
├── trade_reviewer.py     # AI trade reviewer (5 rules + Overbought/Oversold filters)
├── order_executor.py     # Delta Exchange India bracket order router (Demo/Live)
├── main.py               # Interactive CLI Dashboard & Autonomous Watcher
├── trade_log.csv         # Excel/Sheets compatible trade journal ledger
├── trade_history.json    # JSON state tracking
├── requirements.txt      # Python dependencies
├── .env.example          # API credentials template
└── README.md             # Complete documentation
```

---

## 🌟 Pro Enhancements Included:

1. **Live Performance Dashboard:**
   - Shows Account Size, Estimated Balance, Total P&L (₹), Win Rate (%), and Streak Losses.
2. **Quant Multi-Indicator Confirmation:**
   - **RSI (14):** Prevents buying the top (Overbought > 75) or shorting the bottom (Oversold < 25).
   - **20-Day EMA:** Confirms prevailing market momentum.
   - **14-Day ATR (Average True Range):** Mathematically dynamic stop-loss buffer instead of a naive static percentage.
3. **Interactive Menu (4 Modes):**
   - `[1]` Instant Market Scan & Trade Check
   - `[2]` Review Custom Trade Idea (Enter manual LONG/SHORT idea)
   - `[3]` Performance Journal & Ledger
   - `[4]` Continuous Background Watcher (Monitors market every X minutes)
4. **Auto Journaling:**
   - Har trade `trade_log.csv` file mein automatically save hoti hai jise direct Excel mein open kar sakte hain.

---

## 🚀 Kaise Run Karein?

Terminal / Command Prompt khol kar:
```powershell
cd /d D:\crypto_trade_bot
python main.py
```
