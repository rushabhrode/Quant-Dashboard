import asyncio
import threading
import logging
import collections
import pandas as pd
from typing import Dict, List, Deque
from .config import DB_PATH, DEFAULT_SYMBOLS, DEFAULT_ROLLING_WINDOW
from .database import DatabaseHandler
from .ingestion import BinanceClient
from .normalization import Tick
from .resampling import Resampler
from .analytics import FinancialMetrics

class StreamManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(StreamManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        
        logging.basicConfig(level=logging.INFO)
        self.db = DatabaseHandler(DB_PATH)
        self.resampler = Resampler()
        self.symbols = DEFAULT_SYMBOLS
        
        # State Buffers (In-Memory for UI)
        # { 'btcusdt': deque([Tick, ...], maxlen=2000) }
        self.tick_buffer: Dict[str, Deque[Tick]] = {s: collections.deque(maxlen=2000) for s in self.symbols}
        
        # { '1m': { 'btcusdt': DataFrame } } - Actually, simpler to just store lists of dicts
        self.bar_buffer: Dict[str, Dict[str, Deque[dict]]] = {
            '1s': {s: collections.deque(maxlen=3600) for s in self.symbols},
            '1m': {s: collections.deque(maxlen=1440) for s in self.symbols},
            '5m': {s: collections.deque(maxlen=288) for s in self.symbols}
        }

        self.client = BinanceClient(self.symbols, self._process_msg)
        self.thread = None
        self.loop = None
        self._initialized = True

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def _run_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.client.start())

    async def _process_msg(self, msg: str):
        tick = Tick.from_binance_msg(msg)
        if not tick:
            return

        # 1. Update Tick Buffer
        self.tick_buffer[tick.symbol].append(tick)
        
        # 2. Persist Tick
        self.db.insert_tick(tick.symbol, tick.timestamp, tick.price, tick.size)

        # 3. Resample
        new_bars = self.resampler.process_tick(tick)
        
        # 4. Handle Completed Bars
        if new_bars:
            for tf, bar in new_bars:
                # Update Bar Buffer
                self.bar_buffer[tf][bar['symbol']].append(bar)
                # Persist Bar
                self.db.insert_bar(tf, bar)

    # --- Accessors for Frontend ---

    def get_latest_price(self, symbol: str) -> float:
        if self.tick_buffer[symbol]:
            return self.tick_buffer[symbol][-1].price
        return 0.0

    def get_tick_df(self, symbol: str) -> pd.DataFrame:
        data = list(self.tick_buffer[symbol])
        if not data:
            return pd.DataFrame()
        return pd.DataFrame([vars(t) for t in data])

    def get_bars_df(self, timeframe: str, symbol: str) -> pd.DataFrame:
        data = list(self.bar_buffer[timeframe][symbol])
        if not data:
             # Try loading from DB if memory is empty (initial load)
            db_data = self.db.get_bars(timeframe, symbol, limit=200)
            if db_data:
                # Convert tuple from DB to dict/df
                # DB cols: symbol, timestamp, open, high, low, close, volume
                # We need to map this carefully
                return pd.DataFrame(db_data, columns=['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume'])
            return pd.DataFrame()
        
        return pd.DataFrame(data)

    def calculate_metrics(self, s1: str, s2: str, window: int = 20, hedge_ratio: float = 1.0):
        """
        Computes Z-score and Spread on the fly using latest 1s bars for responsiveness, 
        or ticks if preferred. Using 1s bars is cleaner for 'real-time' without too much noise.
        """
        df1 = self.get_bars_df('1s', s1)
        df2 = self.get_bars_df('1s', s2)

        if df1.empty or df2.empty:
            return None

        # Align
        df1 = df1.set_index('timestamp').sort_index()
        df2 = df2.set_index('timestamp').sort_index()
        
        # Join
        combined = df1[['close']].join(df2[['close']], lsuffix='_1', rsuffix='_2', how='inner')
        if len(combined) < window:
            return None

        spread = FinancialMetrics.calculate_spread(combined['close_1'], combined['close_2'], hedge_ratio)
        zscore = FinancialMetrics.calculate_zscore(spread, window)
        
        return {
            'spread': spread,
            'zscore': zscore,
            'latest_z': zscore.iloc[-1] if not zscore.empty else 0,
            'latest_spread': spread.iloc[-1] if not spread.empty else 0
        }
