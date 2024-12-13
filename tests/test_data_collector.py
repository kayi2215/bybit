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
        cls.symbol = 'BTCUSDT'

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
        self.assertLessEqual(len(klines), limit)
        
        # Vérifier les colonnes requises
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
        
        numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'quote_asset_volume']
        for column in numeric_columns:
            self.assertTrue(pd.api.types.is_float_dtype(klines[column]),
                          f"La colonne {column} devrait être de type float")
        
        # Vérifier la cohérence des données
        self.assertTrue(all(klines['high'] >= klines['low']))
        self.assertTrue(all(klines['volume'] >= 0))
        
        # Vérifier que les timestamps sont ordonnés (en utilisant index car les données sont inversées)
        self.assertTrue(klines.index.is_monotonic_increasing)

    def test_interval_conversion(self):
        """Test des différents intervalles de temps"""
        intervals = ['1h', '4h', '1d']  # Intervalles supportés par Bybit
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
            self.assertIsInstance(float(bid[0]), float)  # price
            self.assertIsInstance(float(bid[1]), float)  # quantity

    def test_get_public_trade_history(self):
        """Test de la récupération des trades récents"""
        trades = self.collector.get_public_trade_history(self.symbol, limit=5)
        
        # Vérifier le nombre de trades
        self.assertEqual(len(trades), 5)
        
        # Vérifier la structure des trades
        for trade in trades:
            self.assertIsInstance(trade, dict)
            self.assertIn('id', trade)
            self.assertIn('price', trade)
            self.assertIn('qty', trade)
            self.assertIn('time', trade)
            self.assertIn('isBuyerMaker', trade)
            self.assertIn('isBestMatch', trade)
            
            # Vérifier les types de données
            self.assertIsInstance(trade['price'], float)
            self.assertIsInstance(trade['qty'], float)
            self.assertIsInstance(trade['time'], int)

    def test_get_market_analysis(self):
        """Test de l'analyse de marché"""
        analysis = self.collector.get_market_analysis(self.symbol)
        
        self.assertIsInstance(analysis, dict)
        self.assertIn('current_price', analysis)
        self.assertIn('technical_analysis', analysis)
        self.assertIn('order_book', analysis)
        
        # Vérifier la structure du prix actuel
        self.assertIsInstance(analysis['current_price'], dict)
        self.assertIn('price', analysis['current_price'])
        self.assertIsInstance(analysis['current_price']['price'], float)
        
        # Vérifier la structure de l'analyse technique
        self.assertIsInstance(analysis['technical_analysis'], dict)
        self.assertIn('indicators', analysis['technical_analysis'])
        
        # Vérifier la structure du carnet d'ordres
        self.assertIsInstance(analysis['order_book'], dict)
        self.assertIn('bids', analysis['order_book'])
        self.assertIn('asks', analysis['order_book'])

if __name__ == '__main__':
    unittest.main()
