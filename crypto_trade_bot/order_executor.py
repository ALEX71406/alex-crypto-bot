"""
Enhanced Delta Exchange India Order Router & Execution Engine
Includes:
- Strict Hard Safety Guard for DEMO Mode (Zero real order risk)
- Integration with PaperTradingEngine for real lifecycle paper simulation
- LIVE authenticated bracket order execution on Delta Exchange India
- Balance inquiry & position verification
"""
import hmac
import hashlib
import time
import json
import requests
import urllib3.util.connection as urllib_conn
urllib_conn.HAS_IPV6 = False  # Force stable IPv4 connection (49.36.213.180)
import config
from paper_engine import PaperTradingEngine

class OrderExecutor:
    def __init__(self, paper_engine=None):
        self.api_key = config.DELTA_API_KEY
        self.api_secret = config.DELTA_API_SECRET
        self.mode = config.TRADING_MODE
        self.base_url = config.DELTA_API_URL
        self.paper_engine = paper_engine or PaperTradingEngine()

    def _generate_signature(self, method, endpoint, payload=""):
        timestamp = str(int(time.time()))
        message = method + timestamp + endpoint + payload
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        return signature, timestamp

    def get_wallet_balance(self):
        """Fetches INR / USD balance from Delta Exchange India"""
        if not self.api_key or not self.api_secret:
            return {"success": True, "balance_inr": config.ACCOUNT_SIZE_INR, "mode": "DEMO"}

        endpoint = "/v2/wallet/balances"
        signature, timestamp = self._generate_signature("GET", endpoint)

        headers = {
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": signature
        }

        try:
            res = requests.get(self.base_url + endpoint, headers=headers, timeout=10)
            data = res.json()
            if res.status_code == 200 and data.get("success"):
                inr_balance = 0.0
                usd_balance = 0.0
                for item in data.get("result", []):
                    if item.get("asset_symbol") == "INR":
                        inr_balance = float(item.get("available_balance", 0.0))
                    elif item.get("asset_symbol") == "USD":
                        usd_balance = float(item.get("available_balance", 0.0))
                return {
                    "success": True,
                    "balance_inr": inr_balance,
                    "balance_usd": usd_balance,
                    "mode": self.mode
                }
            return {"success": False, "error": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def place_order(self, direction, entry_price, stop_price, target_price, position_inr, reward_to_risk="1.5 : 1"):
        """
        Executes order in DEMO or LIVE mode.
        HARD SAFETY GUARD: Only sends request to exchange if self.mode == 'LIVE'.
        In any other case, executes strictly in PaperTradingEngine.
        """
        if self.mode != "LIVE" or not self.api_key or not self.api_secret:
            sim_res = self.paper_engine.open_position(
                direction=direction,
                entry_price=entry_price,
                stop_price=stop_price,
                target_price=target_price,
                risk_inr=config.RISK_AMOUNT_INR,
                position_inr=position_inr,
                reward_to_risk=reward_to_risk
            )

            print("\n" + "=" * 55)
            print("🟢 [DEMO / PAPER TRADE SIMULATED ORDER]")
            print(f"   • Asset         : {config.SYMBOL} (Bitcoin)")
            print(f"   • Action        : {direction}")
            print(f"   • Limit Entry   : ${entry_price:,.2f}")
            print(f"   • Stop Loss     : ${stop_price:,.2f}")
            print(f"   • Take Profit   : ${target_price:,.2f}")
            print(f"   • Position Cap  : Rs {position_inr:.2f}")
            print(f"   • Paper Engine  : {'ACCEPTED & TRACKED' if sim_res.get('success') else sim_res.get('reason')}")
            print("=" * 55 + "\n")
            return sim_res

        # LIVE MODE: Authenticated bracket order execution on Delta Exchange
        endpoint = "/v2/orders"
        url = self.base_url + endpoint

        payload_data = {
            "product_symbol": config.SYMBOL,
            "order_type": "limit_order",
            "limit_price": str(entry_price),
            "side": "buy" if direction == "LONG" else "sell",
            "stop_loss_order": {
                "stop_price": str(stop_price)
            },
            "take_profit_order": {
                "stop_price": str(target_price)
            }
        }

        payload_str = json.dumps(payload_data)
        signature, timestamp = self._generate_signature("POST", endpoint, payload_str)

        headers = {
            "api-key": self.api_key,
            "timestamp": timestamp,
            "signature": signature,
            "Content-Type": "application/json"
        }

        try:
            res = requests.post(url, headers=headers, data=payload_str, timeout=10)
            res_data = res.json()
            if res.status_code in [200, 201] and res_data.get("success"):
                return {"success": True, "mode": "LIVE", "data": res_data}
            else:
                return {"success": False, "mode": "LIVE", "error": res_data}
        except Exception as e:
            return {"success": False, "mode": "LIVE", "error": str(e)}
