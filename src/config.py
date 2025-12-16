import os

# Database
DB_NAME = "market_data.db"
DB_PATH = os.path.join(os.getcwd(), DB_NAME)

# Ingestion
DEFAULT_SYMBOLS = ["btcusdt", "ethusdt", "solusdt", "bnbusdt", "xrpusdt"]
WEBSOCKET_URL = "wss://fstream.binance.com/ws"

# Analytics - Defaults
DEFAULT_ROLLING_WINDOW = 20
DEFAULT_HEDGE_RATIO = 1.0
DEFAULT_Z_THRESHOLD = 2.0

# Timeframes
TIMEFRAME_1S = "1S"
TIMEFRAME_1M = "1Min"
TIMEFRAME_5M = "5Min"
