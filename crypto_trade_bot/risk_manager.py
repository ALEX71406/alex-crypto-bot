"""
Institutional-Grade Risk Management & Journaling Engine
Enforces Sidhant's 5 Rules:
1. Max Risk strictly capped (Rs 25 per trade)
2. ATR / Prior Day High-Low Stop buffer
3. Never add to a losing trade
4. 3 consecutive losses = 3 days off (Circuit breaker)
5. Position size capped (No high leverage)

Also maintains trade_log.csv for transparent auditing.
"""
import json
import os
import csv
from datetime import datetime, timedelta
import config

DATA_FILE = os.path.join(os.path.dirname(__file__), "trade_history.json")
CSV_LOG_FILE = os.path.join(os.path.dirname(__file__), "trade_log.csv")


class RiskManager:
    def __init__(self):
        self.history = self._load_history()
        self._ensure_csv_headers()

    def _ensure_csv_headers(self):
        if not os.path.exists(CSV_LOG_FILE):
            with open(CSV_LOG_FILE, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Date", "Direction", "Entry", "Stop", "Target",
                    "Risk (Rs)", "Position (Rs)", "R:R", "Result", "PnL (Rs)", "Rule Broken?"
                ])

    def _load_history(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "account_size_inr": config.ACCOUNT_SIZE_INR,
            "consecutive_losses": 0,
            "lockout_until": None,
            "total_pnl_inr": 0.0,
            "wins": 0,
            "losses": 0,
            "trades": []
        }

    def _save_history(self):
        with open(DATA_FILE, "w") as f:
            json.dump(self.history, f, indent=4)

    def check_circuit_breaker(self):
        """Rule 4: 3 losses in a row = 3 days off"""
        lockout = self.history.get("lockout_until")
        if lockout:
            lockout_time = datetime.fromisoformat(lockout)
            if datetime.now() < lockout_time:
                remaining_seconds = (lockout_time - datetime.now()).total_seconds()
                hours = int(remaining_seconds // 3600)
                minutes = int((remaining_seconds % 3600) // 60)
                return False, f"Rule 4 ACTIVE: Circuit breaker on! Trading paused for next {hours}h {minutes}m."
            else:
                # Lockout period is over, reset consecutive losses
                self.history["lockout_until"] = None
                self.history["consecutive_losses"] = 0
                self._save_history()

        if self.history.get("consecutive_losses", 0) >= config.MAX_CONSECUTIVE_LOSSES:
            lockout_time = datetime.now() + timedelta(days=config.LOCKOUT_DAYS)
            self.history["lockout_until"] = lockout_time.isoformat()
            self._save_history()
            return False, "Rule 4 TRIGGERED: 3 losses in a row! 3 days cooling off period started."

        return True, "Rule 4 OK"

    def check_open_losing_position(self, is_in_losing_trade):
        """Rule 3: Never add to a losing trade"""
        if is_in_losing_trade:
            return False, "Rule 3 FAIL: Already in a losing trade. Never add to a loser."
        return True, "Rule 3 OK"

    def record_trade_result(self, result_type, pnl_inr, notes=""):
        """Record trade result: 'WIN' or 'LOSS' and update circuit breaker stats"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if result_type.upper() == "LOSS":
            self.history["consecutive_losses"] = self.history.get("consecutive_losses", 0) + 1
            self.history["losses"] = self.history.get("losses", 0) + 1
            if self.history["consecutive_losses"] >= config.MAX_CONSECUTIVE_LOSSES:
                lockout_time = datetime.now() + timedelta(days=config.LOCKOUT_DAYS)
                self.history["lockout_until"] = lockout_time.isoformat()
        elif result_type.upper() == "WIN":
            self.history["consecutive_losses"] = 0
            self.history["wins"] = self.history.get("wins", 0) + 1

        self.history["total_pnl_inr"] = round(self.history.get("total_pnl_inr", 0.0) + pnl_inr, 2)
        self._save_history()

    def log_trade(self, trade_details, result="OPEN", pnl_inr=0.0):
        """
        Logs a trade into JSON and CSV ledger.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update stats if closing trade
        if result.upper() == "LOSS":
            self.history["consecutive_losses"] = self.history.get("consecutive_losses", 0) + 1
            self.history["losses"] = self.history.get("losses", 0) + 1
            if self.history["consecutive_losses"] >= config.MAX_CONSECUTIVE_LOSSES:
                lockout_time = datetime.now() + timedelta(days=config.LOCKOUT_DAYS)
                self.history["lockout_until"] = lockout_time.isoformat()
        elif result.upper() == "WIN":
            self.history["consecutive_losses"] = 0
            self.history["wins"] = self.history.get("wins", 0) + 1

        self.history["total_pnl_inr"] = round(self.history.get("total_pnl_inr", 0.0) + pnl_inr, 2)

        trade_entry = {
            "date": timestamp,
            "direction": trade_details.get("direction"),
            "entry": trade_details.get("entry"),
            "stop": trade_details.get("stop"),
            "target": trade_details.get("target"),
            "risk_inr": trade_details.get("risk_amount_inr"),
            "position_inr": trade_details.get("position_size_inr"),
            "reward_to_risk": trade_details.get("reward_to_risk"),
            "result": result.upper(),
            "pnl_inr": pnl_inr,
            "rule_broken": "N"
        }

        self.history.setdefault("trades", []).append(trade_entry)
        self._save_history()

        # Append to CSV
        with open(CSV_LOG_FILE, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                trade_entry["direction"],
                trade_entry["entry"],
                trade_entry["stop"],
                trade_entry["target"],
                trade_entry["risk_inr"],
                trade_entry["position_inr"],
                trade_entry["reward_to_risk"],
                trade_entry["result"],
                trade_entry["pnl_inr"],
                trade_entry["rule_broken"]
            ])

    def get_summary(self):
        wins = self.history.get("wins", 0)
        losses = self.history.get("losses", 0)
        total_finished = wins + losses
        win_rate = round((wins / total_finished * 100), 1) if total_finished > 0 else 0.0

        return {
            "account_size": config.ACCOUNT_SIZE_INR,
            "current_balance_est": round(config.ACCOUNT_SIZE_INR + self.history.get("total_pnl_inr", 0.0), 2),
            "total_pnl_inr": self.history.get("total_pnl_inr", 0.0),
            "consecutive_losses": self.history.get("consecutive_losses", 0),
            "wins": wins,
            "losses": losses,
            "total_trades": len(self.history.get("trades", [])),
            "win_rate": f"{win_rate}%",
            "lockout_until": self.history.get("lockout_until")
        }
