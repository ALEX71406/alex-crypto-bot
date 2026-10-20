"""
Real Paper Trading Simulation Engine for DEMO Mode
Tracks active simulated positions, monitors live price against SL and TP,
calculates simulated trading fees, computes realized/unrealized P&L,
and reports to RiskManager upon position closure.
"""
import os
import json
import time
from datetime import datetime

PAPER_FILE = os.path.join(os.path.dirname(__file__), "paper_positions.json")
# Standard crypto taker fee rate (0.05% per side = 0.1% round-trip)
SIMULATED_FEE_RATE = 0.0005


class PaperTradingEngine:
    def __init__(self, risk_manager=None):
        self.risk_manager = risk_manager
        self.state = self._load_state()

    def _load_state(self):
        if os.path.exists(PAPER_FILE):
            try:
                with open(PAPER_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "active_position": None,
            "closed_trades": []
        }

    def _save_state(self):
        with open(PAPER_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=4)

    def get_active_position(self):
        return self.state.get("active_position")

    def has_active_position(self):
        return self.state.get("active_position") is not None

    def has_active_losing_position(self, current_price=None):
        """Rule 3 Check: Returns True if there is an active trade currently in negative PnL"""
        pos = self.get_active_position()
        if not pos:
            return False
        if current_price is None:
            return pos.get("unrealized_pnl_inr", 0.0) < 0.0

        pnl = self.calculate_unrealized_pnl(pos, current_price)
        return pnl < 0.0

    def calculate_unrealized_pnl(self, pos, current_price):
        entry = pos["entry_price"]
        position_size = pos["position_size_inr"]
        direction = pos["direction"]

        if direction == "LONG":
            pct = (current_price - entry) / entry
        else: # SHORT
            pct = (entry - current_price) / entry

        return round(pct * position_size, 2)

    def open_position(self, direction, entry_price, stop_price, target_price, risk_inr, position_inr, reward_to_risk):
        """Opens a simulated paper trading position with strict SL and TP"""
        if self.has_active_position():
            return {
                "success": False,
                "reason": "Active simulated position already open. Single market rule enforces max 1 trade at a time."
            }

        order_id = f"sim_{int(time.time())}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Simulated entry fee (0.05% of position value)
        entry_fee = round(position_inr * SIMULATED_FEE_RATE, 2)

        position = {
            "order_id": order_id,
            "symbol": "BTCUSD",
            "direction": direction.upper(),
            "entry_price": float(entry_price),
            "stop_loss": float(stop_price),
            "take_profit": float(target_price),
            "risk_amount_inr": float(risk_inr),
            "position_size_inr": float(position_inr),
            "reward_to_risk": str(reward_to_risk),
            "opened_at": now_str,
            "entry_fee_inr": entry_fee,
            "total_fees_inr": entry_fee,
            "status": "OPEN",
            "unrealized_pnl_inr": 0.0
        }

        self.state["active_position"] = position
        self._save_state()

        return {
            "success": True,
            "mode": "DEMO",
            "order_id": order_id,
            "position": position
        }

    def update_price(self, current_price):
        """
        Evaluates active position against current price for Stop Loss, Take Profit, or Holding.
        Returns:
            dict: {
                "has_active": bool,
                "event": "NONE" | "HOLDING" | "STOP_LOSS_HIT" | "TAKE_PROFIT_HIT",
                "details": dict
            }
        """
        pos = self.get_active_position()
        if not pos:
            return {"has_active": False, "event": "NONE", "details": None}

        current_price = float(current_price)
        direction = pos["direction"]
        entry = pos["entry_price"]
        sl = pos["stop_loss"]
        tp = pos["take_profit"]
        risk_inr = pos["risk_amount_inr"]
        position_inr = pos["position_size_inr"]

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        exit_fee = round(position_inr * SIMULATED_FEE_RATE, 2)
        total_fees = round(pos.get("entry_fee_inr", 0.0) + exit_fee, 2)

        sl_hit = False
        tp_hit = False

        if direction == "LONG":
            if current_price <= sl:
                sl_hit = True
            elif current_price >= tp:
                tp_hit = True
        else: # SHORT
            if current_price >= sl:
                sl_hit = True
            elif current_price <= tp:
                tp_hit = True

        if sl_hit:
            # Stopped out: loss equals capped risk + trading fees
            raw_loss = -risk_inr
            net_pnl = round(raw_loss - total_fees, 2)

            closed_record = {
                **pos,
                "closed_at": now_str,
                "exit_price": current_price,
                "exit_reason": "STOP_LOSS_HIT",
                "result": "LOSS",
                "raw_pnl_inr": raw_loss,
                "total_fees_inr": total_fees,
                "net_pnl_inr": net_pnl,
                "status": "CLOSED"
            }

            self.state["closed_trades"].append(closed_record)
            self.state["active_position"] = None
            self._save_state()

            if self.risk_manager:
                self.risk_manager.record_trade_result("LOSS", net_pnl, notes=f"DEMO SL Hit at ${current_price:,.2f}")

            return {
                "has_active": False,
                "event": "STOP_LOSS_HIT",
                "details": closed_record
            }

        elif tp_hit:
            # Target reached: reward = risk * R:R ratio - fees
            rr_val = 1.5
            try:
                rr_str = str(pos.get("reward_to_risk", "1.5")).split(":")[0].strip()
                rr_val = float(rr_str)
            except Exception:
                pass

            raw_gain = round(risk_inr * rr_val, 2)
            net_pnl = round(raw_gain - total_fees, 2)

            closed_record = {
                **pos,
                "closed_at": now_str,
                "exit_price": current_price,
                "exit_reason": "TAKE_PROFIT_HIT",
                "result": "WIN",
                "raw_pnl_inr": raw_gain,
                "total_fees_inr": total_fees,
                "net_pnl_inr": net_pnl,
                "status": "CLOSED"
            }

            self.state["closed_trades"].append(closed_record)
            self.state["active_position"] = None
            self._save_state()

            if self.risk_manager:
                self.risk_manager.record_trade_result("WIN", net_pnl, notes=f"DEMO TP Hit at ${current_price:,.2f}")

            return {
                "has_active": False,
                "event": "TAKE_PROFIT_HIT",
                "details": closed_record
            }

        else:
            # Position still active: update unrealized PnL
            unrealized = self.calculate_unrealized_pnl(pos, current_price)
            pos["unrealized_pnl_inr"] = unrealized
            pos["last_price_checked"] = current_price
            pos["last_checked_at"] = now_str
            self._save_state()

            return {
                "has_active": True,
                "event": "HOLDING",
                "details": pos
            }
