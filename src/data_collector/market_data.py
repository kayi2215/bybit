import logging
from pybit.unified_trading import HTTP
import pandas as pd
from datetime import datetime
import time
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
from .technical_indicators import TechnicalAnalysis

def interval_to_milliseconds(interval: str) -> int:
    """Convert interval string to milliseconds"""
    if interval.endswith('m'):
        return int(interval[:-1]) * 60 * 1000
    elif interval.endswith('h'):
        return int(interval[:-1]) * 60 * 60 * 1000
    elif interval == 'D':
        return 24 * 60 * 60 * 1000
    elif interval == 'W':
        return 7 * 24 * 60 * 60 * 1000
    return 0

class MarketDataCollector:
    def __init__(self, api_key: str, api_secret: str, use_testnet: bool = False):
        """
        Initialise le collecteur de données de marché
        
        Args:
            api_key: Clé API Bybit
            api_secret: Secret API Bybit
            use_testnet: Si True, utilise le testnet Bybit
        """
        load_dotenv()
        
        # Initialize Bybit client
        self.client = HTTP(
            testnet=use_testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        if use_testnet:
            self.logger.info("Using Bybit Testnet")
            
        self.technical_analyzer = TechnicalAnalysis()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def get_current_price(self, symbol: str) -> Dict[str, float]:
        try:
            ticker = self.client.get_tickers(
                category="spot",
                symbol=symbol
            )
            price = float(ticker['result']['list'][0]['lastPrice'])
            self.logger.info(f"Retrieved price for {symbol}: {price}")
            return {
                'symbol': symbol,
                'price': price,
                'timestamp': datetime.now().timestamp()
            }
        except Exception as e:
            self.logger.error(f"Error fetching price for {symbol}: {str(e)}")
            raise

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        try:
            # Convert interval to Bybit format
            interval_map = {
                '1m': '1', '3m': '3', '5m': '5', '15m': '15',
                '30m': '30', '1h': '60', '2h': '120', '4h': '240',
                '6h': '360', '12h': '720', '1d': 'D', '1w': 'W'
            }
            bybit_interval = interval_map.get(interval, '60')
            
            klines = self.client.get_kline(
                category="spot",
                symbol=symbol,
                interval=bybit_interval,
                limit=limit
            )
            
            # Transform to match Binance format
            formatted_klines = []
            for kline in klines['result']['list']:
                timestamp = int(kline[0])
                formatted_kline = [
                    timestamp,                    # timestamp
                    float(kline[1]),             # open
                    float(kline[2]),             # high
                    float(kline[3]),             # low
                    float(kline[4]),             # close
                    float(kline[5]),             # volume
                    timestamp + interval_to_milliseconds(bybit_interval),  # close_time
                    float(kline[6]),             # quote_asset_volume (turnover)
                    int(kline[7]) if len(kline) > 7 else 0,  # number_of_trades
                    0.0,                         # taker_buy_base_asset_volume
                    0.0,                         # taker_buy_quote_asset_volume
                    0                            # ignore
                ]
                formatted_klines.append(formatted_kline)
            
            df = pd.DataFrame(formatted_klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'close_time', 'quote_asset_volume',
                'number_of_trades', 'taker_buy_base_asset_volume',
                'taker_buy_quote_asset_volume', 'ignore'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
        except Exception as e:
            self.logger.error(f"Error fetching klines for {symbol}: {str(e)}")
            raise

    def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        try:
            depth = self.client.get_orderbook(
                category="spot",
                symbol=symbol,
                limit=limit
            )
            # Transform to match Binance format
            return {
                'lastUpdateId': depth['result']['u'],  # Update ID
                'bids': [[float(item[0]), float(item[1])] for item in depth['result']['b']],  # Bids
                'asks': [[float(item[0]), float(item[1])] for item in depth['result']['a']]   # Asks
            }
        except Exception as e:
            self.logger.error(f"Error fetching order book for {symbol}: {str(e)}")
            raise

    def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            trades = self.client.get_public_trade_history(
                category="spot",
                symbol=symbol,
                limit=limit
            )
            # Transform to match Binance format
            formatted_trades = []
            for trade in trades['result']['list']:
                formatted_trade = {
                    'id': int(str(trade['execId']).replace('.', '')),  # Convertir en int après avoir retiré le point
                    'price': float(trade['price']),
                    'qty': float(trade['size']),
                    'time': int(trade['time']),
                    'isBuyerMaker': trade['side'].lower() == 'sell',
                    'isBestMatch': True
                }
                formatted_trades.append(formatted_trade)
            
            self.logger.info(f"Retrieved {len(formatted_trades)} recent trades for {symbol}")
            return formatted_trades
        except Exception as e:
            self.logger.error(f"Error fetching recent trades for {symbol}: {str(e)}")
            raise

    def get_technical_analysis(self, symbol: str, interval: str = '1h', limit: int = 100) -> Dict[str, Any]:
        try:
            df = self.get_klines(symbol, interval, limit)
            indicators = self.technical_analyzer.calculate_all(df)
            signals = self.technical_analyzer.get_signals(df)
            summary = self.technical_analyzer.get_summary(df)
            
            return {
                'indicators': indicators,
                'signals': signals,
                'summary': summary
            }
        except Exception as e:
            self.logger.error(f"Error performing technical analysis for {symbol}: {str(e)}")
            raise

    def get_market_analysis(self, symbol: str) -> Dict[str, Any]:
        try:
            current_price = self.get_current_price(symbol)
            technical_analysis = self.get_technical_analysis(symbol)
            order_book = self.get_order_book(symbol)
            
            return {
                'current_price': current_price,
                'technical_analysis': technical_analysis,
                'order_book': order_book
            }
        except Exception as e:
            self.logger.error(f"Error performing market analysis for {symbol}: {str(e)}")
            raise
