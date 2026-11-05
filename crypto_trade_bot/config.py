"""
Trading Configuration based on Sidhant's 5 Strict Risk Rules
Optimized for Rs 5,000 Capital
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Account & Risk Settings
ACCOUNT_SIZE_INR = 5000.0   # Total allocated capital
RISK_AMOUNT_INR = 125.0     # Max risk per trade (2.5% of account to protect balance against fees)
MAX_ORDER_VALUE_INR = 1500.0 # Position size (Rule 5: No high leverage/borrowed money, 30% max position)

# The 5 Rules Parameters
MAX_CONSECUTIVE_LOSSES = 3  # Rule 4: 3 losses in a row
LOCKOUT_DAYS = 3            # Rule 4: 3 days cooldown / circuit breaker
MIN_REWARD_TO_RISK = 1.5    # Minimum reward-to-risk ratio

# Exchange API Credentials
DELTA_API_KEY = os.getenv("DELTA_API_KEY", "")
DELTA_API_SECRET = os.getenv("DELTA_API_SECRET", "")
TRADING_MODE = os.getenv("TRADING_MODE", "DEMO").upper() # 'DEMO' or 'LIVE'

# Symbol
SYMBOL = "BTCUSD"
DELTA_BASE_URL = "https://cdn.india.delta.exchange"
DELTA_API_URL = "https://api.india.delta.exchange"