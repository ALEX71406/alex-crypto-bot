# MADE BY ALEX - Institutional AI Crypto Trading System

## 1. Project Overview & Meta Information
- **Project Name**: MADE BY ALEX Crypto Trading Bot & Institutional Terminal
- **Created / Upgraded Date**: 05 November 2026
- **Architecture**: 5 Strict Risk Management Rules ('Trading With Sidhant' Model) + Quant Multi-Indicator Composite Score (v2.0)
- **Primary Asset**: Bitcoin (BTCUSD / BTCUSDT)
- **Execution Mode**: DEMO / PAPER TRADING (100% Risk-Free Simulation)
- **Trading Engine**: Delta Exchange India logic + Binance / Coinbase multi-tier data fallback

---

## 2. Live Links & Deployment
- **Live Terminal URL**: https://alex-crypto-bot.onrender.com/
- **GitHub Repository**: https://github.com/ALEX71406/alex-crypto-bot
- **Target Folder**: crypto_trade_bot/
- **Access Authentication**: Configured via GitHub Developer Personal Access Token (classic with repo scope)

---

## 3. Financial & Risk Parameters
| Metric | Value | Description |
|---|---|---|
| **Allocated Principal Capital** | **Rs 5,000.00** | Initial balance allocated for strategy testing |
| **Max Risk Per Trade (2.5%)** | **Rs 125.00** | Strict stop-loss limit to protect principal |
| **Max Order Value Cap (30%)** | **Rs 1,500.00** | Maximum allocation for any single position |
| **Reward-to-Risk Target** | **1.5 : 1** | Target Profit: Rs 187.50+ per trade |
| **Circuit Breaker** | **3 Consecutive Losses** | Auto-lock trading for 3 days cooldown |

---

## 4. Technical Architecture (v2.0 Upgrade)
- **Indicators**: RSI (14), MACD (12, 26, 9), EMA Stack (20, 50, 200), ATR Volatility Buffer, Volume Confirmation, Candle Patterns, Multi-timeframe 4H Analysis.
- **Composite Score Engine**: Aggregates all indicators (-10 to +10) to confirm entry direction.
- **Paper Trading Engine**: Real-time simulated order tracking with dynamic SL/TP execution.
- **UI Terminal**: Apple Warm Cream Frosted Glass theme with 5 real-time responsive cards.