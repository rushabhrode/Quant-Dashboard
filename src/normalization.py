from dataclasses import dataclass
from datetime import datetime
import json
from typing import Optional

@dataclass
class Tick:
    symbol: str
    timestamp: str  # ISO-8601
    price: float
    size: float

    @staticmethod
    def from_binance_msg(msg: str) -> Optional['Tick']:
        """
        Parses Binance AggTrade or Trade stream message.
        See: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-data/aggregate-trade-streams
        Looking for 'p' (price), 'q' (quantity), 'T' (trade time), 's' (symbol)
        Or 'p', 'q', 'E' (event time) if using raw trade stream.
        """
        try:
            data = json.loads(msg)
            # Handle standard trade or aggTrade
            # e: event type, E: event time, s: symbol, p: price, q: quantity
            if 'e' in data and data['e'] == 'aggTrade':
                 ts_ms = data['T']
            elif 'T' in data: # Trade stream
                 ts_ms = data['T']
            else:
                return None 
            
            # Convert ms timestamp to ISO
            iso_ts = datetime.fromtimestamp(ts_ms / 1000.0).isoformat()
            
            return Tick(
                symbol=data['s'].lower(),
                timestamp=iso_ts,
                price=float(data['p']),
                size=float(data['q'])
            )
        except Exception:
            return None
