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
        
        if not api_key or not api_secret:
            raise ValueError("Les clés API sont requises")
            
        self.logger = logging.getLogger(__name__)
        self._setup_logging()
        
        # Initialize Bybit client
        self.client = HTTP(
            testnet=use_testnet,
            api_key=api_key,
            api_secret=api_secret
        )
        
        # Test de connexion
        try:
            self.test_connection()
            self.logger.info("Connexion à l'API Bybit établie avec succès")
        except Exception as e:
            self.logger.error(f"Échec de la connexion à l'API Bybit: {str(e)}")
            raise
            
        if use_testnet:
            self.logger.info("Using Bybit Testnet")
            
        self.technical_analyzer = TechnicalAnalysis()

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    def test_connection(self):
        """Test la connexion à l'API en récupérant le temps serveur"""
        try:
            self.client.get_server_time()
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors du test de connexion: {str(e)}")
            raise

    def get_current_price(self, symbol: str) -> Dict[str, float]:
        """
        Récupère le prix actuel d'un symbole, essaie d'abord en spot puis en linear si nécessaire
        """
        try:
            # Essayer d'abord en spot
            try:
                self.logger.info(f"Tentative de récupération du prix spot pour {symbol}")
                response = self.client.get_tickers(
                    category="spot",
                    symbol=symbol
                )
                self.logger.info(f"Réponse brute de l'API spot: {response}")
                
                if not response.get('result') or not response['result'].get('list'):
                    self.logger.warning(f"Pas de données dans la réponse spot pour {symbol}")
                    raise ValueError("Pas de données dans la réponse de l'API spot")
                
                price = float(response['result']['list'][0]['lastPrice'])
                self.logger.info(f"Prix spot trouvé pour {symbol}: {price}")
                return {
                    'symbol': symbol,
                    'price': price,
                    'timestamp': datetime.now().timestamp(),
                    'category': 'spot'
                }
            except Exception as spot_error:
                self.logger.warning(f"Erreur lors de la récupération du prix spot pour {symbol}: {str(spot_error)}")
                
                # Essayer en linear (perpetual futures)
                self.logger.info(f"Tentative de récupération du prix linear pour {symbol}")
                response = self.client.get_tickers(
                    category="linear",
                    symbol=symbol
                )
                self.logger.info(f"Réponse brute de l'API linear: {response}")
                
                if not response.get('result') or not response['result'].get('list'):
                    self.logger.warning(f"Pas de données dans la réponse linear pour {symbol}")
                    raise ValueError("Pas de données dans la réponse de l'API linear")
                
                price = float(response['result']['list'][0]['lastPrice'])
                self.logger.info(f"Prix linear trouvé pour {symbol}: {price}")
                return {
                    'symbol': symbol,
                    'price': price,
                    'timestamp': datetime.now().timestamp(),
                    'category': 'linear'
                }
        except Exception as e:
            self.logger.error(f"Échec de la récupération du prix pour {symbol} (spot et linear): {str(e)}")
            self.logger.error(f"Détails de la configuration - Testnet: {self.client.testnet}")
            raise

    def get_klines(self, symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
        try:
            # Convert interval to Bybit format
            interval_map = {
                '1m': '1', '3m': '3', '5m': '5', '15m': '15',
                '30m': '30', '1h': '60', '2h': '120', '4h': '240',
                '6h': '360', '12h': '720', '1d': 'D', '1w': 'W'
            }
            bybit_interval = interval_map.get(interval)
            if bybit_interval is None:
                raise ValueError(f"Interval non supporté: {interval}")
            
            klines = self.client.get_kline(
                category="spot",
                symbol=symbol,
                interval=bybit_interval,
                limit=limit
            )
            
            if 'result' not in klines or 'list' not in klines['result']:
                raise ValueError(f"Format de réponse invalide pour {symbol}")
            
            # Transform data to match Binance format exactly
            data = []
            for kline in reversed(klines['result']['list']):
                # Bybit kline format: [timestamp, open, high, low, close, volume, turnover]
                data.append([
                    int(kline[0]),                    # timestamp
                    float(kline[1]),                  # open
                    float(kline[2]),                  # high
                    float(kline[3]),                  # low
                    float(kline[4]),                  # close
                    float(kline[5]),                  # volume
                    int(kline[0]) + interval_to_milliseconds(interval), # close_time
                    float(kline[6]),                  # quote_asset_volume (turnover in Bybit)
                    0,                                # number_of_trades (not provided by Bybit)
                    0.0,                              # taker_buy_base_asset_volume (not provided)
                    0.0,                              # taker_buy_quote_asset_volume (not provided)
                    0                                 # ignore
                ])
            
            df = pd.DataFrame(data, columns=[
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
        """
        Récupère le carnet d'ordres pour un symbole
        :param symbol: Symbole de la paire de trading (ex: 'BTCUSDT')
        :param limit: Profondeur du carnet d'ordres
        :return: Carnet d'ordres
        """
        try:
            depth = self.client.get_orderbook(
                category="spot",
                symbol=symbol,
                limit=limit
            )
            
            # Transformer au format Binance
            return {
                'lastUpdateId': depth['result']['ts'],
                'bids': [[price, qty] for price, qty in depth['result']['b']],
                'asks': [[price, qty] for price, qty in depth['result']['a']]
            }
        except Exception as e:
            self.logger.error(f"Error fetching order book for {symbol}: {str(e)}")
            raise

    def get_public_trade_history(self, symbol: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère les transactions récentes pour un symbole
        :param symbol: Symbole de la paire de trading (ex: 'BTCUSDT')
        :param limit: Nombre de transactions à récupérer
        :return: Liste des transactions récentes
        """
        try:
            trades = self.client.get_public_trade_history(
                category="spot",
                symbol=symbol,
                limit=limit
            )
            
            # Transformer au format Binance
            formatted_trades = []
            for trade in trades['result']['list']:
                formatted_trades.append({
                    'id': trade['execId'],
                    'price': float(trade['price']),
                    'qty': float(trade['size']),
                    'time': int(trade['time']),
                    'isBuyerMaker': trade['side'].lower() == 'sell',
                    'isBestMatch': True  # Bybit n'a pas cet équivalent
                })
            
            self.logger.info(f"Retrieved {len(formatted_trades)} recent trades for {symbol}")
            return formatted_trades
        except Exception as e:
            self.logger.error(f"Error fetching recent trades for {symbol}: {str(e)}")
            raise

    def get_technical_analysis(self, symbol: str, interval: str = '1h', limit: int = 100) -> Dict[str, Any]:
        try:
            df = self.get_klines(symbol, interval, limit)
            analysis = self.technical_analyzer.get_summary(df)
            
            return analysis
            
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

    def get_ticker(self, symbol: str) -> Dict[str, Any]:
        """
        Récupère les données du ticker pour un symbole
        
        Args:
            symbol: Le symbole (ex: BTCUSDT)
            
        Returns:
            Dict contenant les données du ticker
        """
        try:
            response = self.client.get_tickers(
                category="spot",
                symbol=symbol
            )
            
            if response['retCode'] == 0 and response['result']['list']:
                ticker_data = response['result']['list'][0]
                return {
                    'symbol': symbol,
                    'price': float(ticker_data['lastPrice']),
                    'volume': float(ticker_data['volume24h']),
                    'timestamp': datetime.now().timestamp()
                }
            else:
                self.logger.error(f"Erreur lors de la récupération du ticker pour {symbol}: {response}")
                return None
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération du ticker pour {symbol}: {str(e)}")
            return None
