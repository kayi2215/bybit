import logging
from binance.client import Client
from binance.exceptions import BinanceAPIException
import pandas as pd
from datetime import datetime
import time
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

class MarketDataCollector:
    def __init__(self, api_key: str, api_secret: str):
        load_dotenv()
        use_testnet = os.getenv('USE_TESTNET', 'False').lower() == 'true'
        
        self.client = Client(api_key, api_secret, testnet=use_testnet)
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        if use_testnet:
            self.logger.info("Using Binance Testnet")

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def get_current_price(self, symbol: str) -> Dict[str, float]:
        try:
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            self.logger.info(f"Retrieved price for {symbol}: {ticker['price']}")
            return {
                'symbol': symbol,
                'price': float(ticker['price']),
                'timestamp': datetime.now().timestamp()
            }
        except BinanceAPIException as e:
            self.logger.error(f"Error fetching price for {symbol}: {str(e)}")
            raise

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'close_time', 'quote_asset_volume',
                'number_of_trades', 'taker_buy_base_asset_volume',
                'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except BinanceAPIException as e:
            self.logger.error(f"Error fetching klines for {symbol}: {str(e)}")
            raise

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        try:
            depth = self.client.get_order_book(symbol=symbol, limit=limit)
            return depth
        except BinanceAPIException as e:
            self.logger.error(f"Error fetching order book for {symbol}: {str(e)}")
            raise
