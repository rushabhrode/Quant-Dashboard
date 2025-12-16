import sqlite3
import logging
from contextlib import contextmanager
from typing import List, Tuple, Dict, Any
from datetime import datetime

class DatabaseHandler:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Ticks table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ticks (
                    symbol TEXT,
                    timestamp TEXT,
                    price REAL,
                    size REAL,
                    PRIMARY KEY (symbol, timestamp)
                )
            ''')

            # Generic OHLCV table creator
            for tf in ['1s', '1m', '5m']:
                cursor.execute(f'''
                    CREATE TABLE IF NOT EXISTS bars_{tf} (
                        symbol TEXT,
                        timestamp TEXT,
                        open REAL,
                        high REAL,
                        low REAL,
                        close REAL,
                        volume REAL,
                        PRIMARY KEY (symbol, timestamp)
                    )
                ''')
            
            # Indexing for performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_ticks_ts ON ticks(timestamp)')
            conn.commit()

    def insert_tick(self, symbol: str, timestamp: str, price: float, size: float):
        with self.get_connection() as conn:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO ticks (symbol, timestamp, price, size) VALUES (?, ?, ?, ?)",
                    (symbol, timestamp, price, size)
                )
                conn.commit()
            except Exception as e:
                logging.error(f"DB Error inserting tick: {e}")

    def insert_bar(self, timeframe: str, bar_data: Dict[str, Any]):
        """
        bar_data expected keys: symbol, timestamp, open, high, low, close, volume
        """
        table_name = f"bars_{timeframe}"
        with self.get_connection() as conn:
            try:
                conn.execute(
                    f"INSERT OR REPLACE INTO {table_name} (symbol, timestamp, open, high, low, close, volume) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (bar_data['symbol'], bar_data['timestamp'], bar_data['open'], bar_data['high'], bar_data['low'], bar_data['close'], bar_data['volume'])
                )
                conn.commit()
            except Exception as e:
                logging.error(f"DB Error inserting bar: {e}")

    def get_recent_ticks(self, symbol: str, limit: int = 1000) -> List[Tuple]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT symbol, timestamp, price, size FROM ticks WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                (symbol, limit)
            )
            return cursor.fetchall()

    def get_bars(self, timeframe: str, symbol: str, limit: int = 200) -> List[Tuple]:
        table_name = f"bars_{timeframe}"
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {table_name} WHERE symbol = ? ORDER BY timestamp DESC LIMIT ?",
                (symbol, limit)
            )
            rows = cursor.fetchall()
            # Return ordered by time asc for plotting
            return rows[::-1]
