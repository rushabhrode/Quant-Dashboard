import asyncio
import websockets
import logging
import json
from .config import WEBSOCKET_URL

class BinanceClient:
    def __init__(self, symbols: list, callback):
        """
        callback: async function(msg)
        """
        self.symbols = [s.lower() for s in symbols]
        self.callback = callback
        self.running = False

    async def start(self):
        self.running = True
        # Construct stream URL
        # Format: /ws/btcusdt@trade/ethusdt@trade
        streams = "/".join([f"{s}@trade" for s in self.symbols])
        url = f"{WEBSOCKET_URL}/{streams}"

        logging.info(f"Connecting to {url}")
        
        while self.running:
            try:
                async with websockets.connect(url) as ws:
                    logging.info("Connected to Binance")
                    while self.running:
                        msg = await ws.recv()
                        await self.callback(msg)
            except Exception as e:
                logging.error(f"Websocket error: {e}")
                await asyncio.sleep(5) # Reconnect delay

    def stop(self):
        self.running = False
