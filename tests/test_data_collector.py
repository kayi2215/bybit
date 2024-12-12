import unittest
from src.data_collector.market_data import MarketDataCollector
from config.config import BYBIT_API_KEY, BYBIT_API_SECRET
import pandas as pd
from datetime import datetime
import numpy as np

class TestMarketDataCollector(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Initialisation avant tous les tests"""
        cls.collector = MarketDataCollector(BYBIT_API_KEY, BYBIT_API_SECRET)
        cls.symbol = 'BTCUSDT'  # Bybit utilise le même format de symbole que Binance

    def test_get_current_price(self):
        """Test de la récupération du prix actuel"""
        price_data = self.collector.get_current_price(self.symbol)
        
        self.assertIsInstance(price_data, dict)
        self.assertIn('symbol', price_data)
        self.assertIn('price', price_data)
        self.assertIn('timestamp', price_data)
        self.assertIsInstance(price_data['price'], float)
        self.assertGreater(price_data['price'], 0)
        self.assertEqual(price_data['symbol'], self.symbol)
        self.assertIsInstance(price_data['timestamp'], float)

    def test_get_klines(self):
        """Test de la récupération des données historiques"""
        interval = '1h'
        limit = 5
        klines = self.collector.get_klines(self.symbol, interval, limit=limit)
        
        # Test de base
        self.assertIsInstance(klines, pd.DataFrame)
        self.assertEqual(len(klines), limit)
        
        # Vérifier toutes les colonnes requises
        required_columns = [
            'timestamp', 'open', 'high', 'low', 'close',
            'volume', 'close_time', 'quote_asset_volume',
            'number_of_trades', 'taker_buy_base_asset_volume',
            'taker_buy_quote_asset_volume', 'ignore'
        ]
        for column in required_columns:
            self.assertIn(column, klines.columns)
        
        # Vérifier les types de données
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(klines['timestamp']))
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(klines['close_time']))
        
        numeric_columns = [
            'open', 'high', 'low', 'close', 'volume',
            'quote_asset_volume', 'taker_buy_base_asset_volume',
            'taker_buy_quote_asset_volume'
        ]
        for column in numeric_columns:
            self.assertTrue(pd.api.types.is_float_dtype(klines[column]),
                          f"La colonne {column} devrait être de type float")
        
        self.assertTrue(pd.api.types.is_integer_dtype(klines['number_of_trades']),
                       "La colonne number_of_trades devrait être de type integer")
        
        # Vérifier la cohérence des données
        self.assertTrue(all(klines['high'] >= klines['low']))
        self.assertTrue(all(klines['high'] >= klines['open']))
        self.assertTrue(all(klines['high'] >= klines['close']))
        self.assertTrue(all(klines['volume'] >= 0))
        self.assertTrue(all(klines['number_of_trades'] >= 0))
        
        # Vérifier que les timestamps sont ordonnés
        self.assertTrue(klines['timestamp'].is_monotonic_increasing)
        self.assertTrue(klines['close_time'].is_monotonic_increasing)

    def test_interval_conversion(self):
        """Test des différents intervalles de temps"""
        intervals = ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '12h', '1d', '1w']
        for interval in intervals:
            klines = self.collector.get_klines(self.symbol, interval, limit=2)
            self.assertIsInstance(klines, pd.DataFrame)
            self.assertGreater(len(klines), 0)
            
    def test_error_handling(self):
        """Test de la gestion des erreurs"""
        with self.assertRaises(Exception):
            self.collector.get_klines('INVALID_SYMBOL', '1h')
            
        with self.assertRaises(Exception):
            self.collector.get_klines(self.symbol, 'INVALID_INTERVAL')

    def test_get_order_book(self):
        """Test de la récupération du carnet d'ordres"""
        order_book = self.collector.get_order_book(self.symbol, limit=5)
        
        self.assertIsInstance(order_book, dict)
        self.assertIn('lastUpdateId', order_book)
        self.assertIn('bids', order_book)
        self.assertIn('asks', order_book)
        
        # Vérifier la structure des bids et asks
        self.assertLessEqual(len(order_book['bids']), 5)
        self.assertLessEqual(len(order_book['asks']), 5)
        
        if len(order_book['bids']) > 0:
            bid = order_book['bids'][0]
            self.assertEqual(len(bid), 2)
            self.assertIsInstance(bid[0], float)  # price
            self.assertIsInstance(bid[1], float)  # quantity

    def test_get_recent_trades(self):
        """Test de la récupération des trades récents"""
        trades = self.collector.get_recent_trades(self.symbol, limit=5)
        
        self.assertIsInstance(trades, list)
        self.assertLessEqual(len(trades), 5)
        
        if len(trades) > 0:
            trade = trades[0]
            required_fields = ['id', 'price', 'qty', 'time', 'isBuyerMaker', 'isBestMatch']
            for field in required_fields:
                self.assertIn(field, trade)
            
            self.assertIsInstance(trade['id'], int)
            self.assertIsInstance(trade['price'], float)
            self.assertIsInstance(trade['qty'], float)
            self.assertIsInstance(trade['time'], int)
            self.assertIsInstance(trade['isBuyerMaker'], bool)

    def test_get_technical_analysis(self):
        """Test de l'analyse technique"""
        technical_analysis = self.collector.get_technical_analysis(self.symbol)
        
        self.assertIsInstance(technical_analysis, dict)
        self.assertIn('indicators', technical_analysis)
        self.assertIn('signals', technical_analysis)
        self.assertIn('summary', technical_analysis)

        # Vérifier la présence des indicateurs requis
        if 'indicators' in technical_analysis:
            indicators = technical_analysis['indicators']
            required_indicators = ['RSI', 'MACD', 'BB_Upper', 'BB_Lower', 'SMA_20', 'EMA_20']
            for indicator in required_indicators:
                self.assertIn(indicator, indicators)

        # Vérifier la présence des signaux requis
        if 'signals' in technical_analysis:
            signals = technical_analysis['signals']
            required_signals = ['RSI', 'MACD', 'BB']
            for signal in required_signals:
                self.assertIn(signal, signals)

    def test_get_market_analysis(self):
        """Test de l'analyse complète du marché"""
        market_analysis = self.collector.get_market_analysis(self.symbol)
        
        self.assertIsInstance(market_analysis, dict)
        self.assertIn('current_price', market_analysis)
        self.assertIn('technical_analysis', market_analysis)
        self.assertIn('order_book', market_analysis)

        # Vérifier la structure du prix actuel
        current_price = market_analysis['current_price']
        self.assertIsInstance(current_price, dict)
        self.assertIn('price', current_price)
        self.assertIn('symbol', current_price)
        self.assertIn('timestamp', current_price)

        # Vérifier la structure de l'analyse technique
        technical_analysis = market_analysis['technical_analysis']
        self.assertIsInstance(technical_analysis, dict)
        self.assertIn('indicators', technical_analysis)
        self.assertIn('signals', technical_analysis)
        self.assertIn('summary', technical_analysis)

        # Vérifier la structure du carnet d'ordres
        order_book = market_analysis['order_book']
        self.assertIsInstance(order_book, dict)
        self.assertIn('lastUpdateId', order_book)
        self.assertIn('bids', order_book)
        self.assertIn('asks', order_book)

if __name__ == '__main__':
    unittest.main()
