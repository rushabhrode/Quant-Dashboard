from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, Optional, Any
import logging
from .normalization import Tick

class Resampler:
    def __init__(self):
        # State for current bars: { '1s': {'btcusdt': BarData}, '1m': ... }
        self.current_bars: Dict[str, Dict[str, Dict[str, Any]]] = {
            '1s': {},
            '1m': {},
            '5m': {}
        }
    
    def _get_interval_seconds(self, timeframe: str) -> int:
        if timeframe == '1s': return 1
        if timeframe == '1m': return 60
        if timeframe == '5m': return 300
        return 60

    def _align_time(self, ts: datetime, timeframe: str) -> datetime:
        """
        Floors timestamp to the nearest interval boundary.
        """
        seconds = self._get_interval_seconds(timeframe)
        timestamp = ts.replace(microsecond=0)
        
        # Calculate seconds since epoch part to floor correctly
        # Easier strategy: timestamp is already ISO from Tick. 
        # But we need datetime obj.
        
        # Floor logic
        total_seconds = int(timestamp.timestamp())
        floored_seconds = total_seconds - (total_seconds % seconds)
        return datetime.fromtimestamp(floored_seconds)

    def process_tick(self, tick: Tick) -> list[tuple[str, dict]]:
        """
        Ingests a tick and returns a list of COMPLETED bars to save.
        Returns: [('1m', bar_dict), ('5m', bar_dict), ...]
        """
        completed_bars = []
        
        try:
            ts_dt = datetime.fromisoformat(tick.timestamp)
        except ValueError:
            return []

        for tf in ['1s', '1m', '5m']:
            aligned_ts = self._align_time(ts_dt, tf)
            aligned_ts_str = aligned_ts.isoformat()
            
            # Check if we have an existing bar for this symbol
            if tick.symbol in self.current_bars[tf]:
                current_bar = self.current_bars[tf][tick.symbol]
                
                # If the new tick belongs to a NEW period (aligned_ts > current_bar_ts)
                # Then the old bar is officially closed.
                if aligned_ts_str != current_bar['timestamp']:
                     completed_bars.append((tf, current_bar))
                     # Start new bar
                     self.current_bars[tf][tick.symbol] = self._new_bar(tick, aligned_ts_str)
                else:
                    # Update existing bar
                    self._update_bar(current_bar, tick)
            else:
                # First bar ever
                self.current_bars[tf][tick.symbol] = self._new_bar(tick, aligned_ts_str)

        return completed_bars

    def _new_bar(self, tick: Tick, timestamp: str) -> Dict[str, Any]:
        return {
            'symbol': tick.symbol,
            'timestamp': timestamp,
            'open': tick.price,
            'high': tick.price,
            'low': tick.price,
            'close': tick.price,
            'volume': tick.size
        }

    def _update_bar(self, bar: Dict[str, Any], tick: Tick):
        bar['high'] = max(bar['high'], tick.price)
        bar['low'] = min(bar['low'], tick.price)
        bar['close'] = tick.price
        bar['volume'] += tick.size
