import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from src.database.mongodb_manager import MongoDBManager
import time

class TestMongoDBManager(unittest.TestCase):
    def setUp(self):
        """Configure le gestionnaire MongoDB pour les tests"""
        self.mongodb_manager = MongoDBManager()
        
    def tearDown(self):
        """Nettoie après les tests"""
        self.mongodb_manager.close()

    def test_store_and_retrieve_market_data(self):
        """Teste le stockage et la récupération des données de marché"""
        # Données de test
        symbol = "BTCUSDT"
        test_data = {
            "price": 50000.0,
            "volume": 100.0
        }
        
        # Stockage des données
        self.mongodb_manager.store_market_data(symbol, test_data)
        
        # Récupération des données
        retrieved_data = self.mongodb_manager.get_latest_market_data(symbol)
        
        # Vérifications
        self.assertIsNotNone(retrieved_data)
        self.assertEqual(retrieved_data["symbol"], symbol)
        self.assertEqual(retrieved_data["data"], test_data)

    def test_store_and_retrieve_indicators(self):
        """Teste le stockage et la récupération des indicateurs"""
        # Données de test
        symbol = "BTCUSDT"
        test_indicators = {
            "rsi": 65.5,
            "macd": {"value": 100.0, "signal": 95.0}
        }
        
        # Stockage des indicateurs
        self.mongodb_manager.store_indicators(symbol, test_indicators)
        
        # Récupération des indicateurs
        retrieved_indicators = self.mongodb_manager.get_latest_indicators(symbol)
        
        # Vérifications
        self.assertIsNotNone(retrieved_indicators)
        self.assertEqual(retrieved_indicators["symbol"], symbol)
        self.assertEqual(retrieved_indicators["indicators"], test_indicators)

    def test_store_and_retrieve_trades(self):
        """Teste le stockage et la récupération des transactions"""
        # Données de test
        trade_data = {
            "symbol": "BTCUSDT",
            "side": "BUY",
            "price": 50000.0,
            "quantity": 1.0
        }
        
        # Stockage de la transaction
        self.mongodb_manager.store_trade(trade_data)
        
        # Récupération des transactions
        trades = self.mongodb_manager.get_trades_history("BTCUSDT", limit=1)
        
        # Vérifications
        self.assertEqual(len(trades), 1)
        retrieved_trade = trades[0]
        self.assertEqual(retrieved_trade["symbol"], trade_data["symbol"])
        self.assertEqual(retrieved_trade["side"], trade_data["side"])
        self.assertEqual(retrieved_trade["price"], trade_data["price"])
        self.assertEqual(retrieved_trade["quantity"], trade_data["quantity"])

    def test_historical_data_retrieval(self):
        """Teste la récupération des données historiques"""
        symbol = "BTCUSDT"
        start_time = datetime.now() - timedelta(days=1)
        end_time = datetime.now()
        
        # Stockage de quelques données historiques
        test_data = {"price": 50000.0, "volume": 100.0}
        self.mongodb_manager.store_market_data(symbol, test_data)
        
        # Récupération des données historiques
        historical_data = self.mongodb_manager.get_historical_data(symbol, start_time, end_time)
        
        # Vérifications
        self.assertGreater(len(historical_data), 0)
        self.assertEqual(historical_data[0]["symbol"], symbol)

    def test_cleanup_old_data(self):
        """Teste le nettoyage des anciennes données"""
        # Stockage de données anciennes
        symbol = "BTCUSDT"
        old_data = {"price": 45000.0, "volume": 90.0}
        self.mongodb_manager.store_market_data(symbol, old_data)
        
        # Attendre un peu pour s'assurer que les données sont stockées
        time.sleep(0.5)
        
        # Nettoyage des données
        self.mongodb_manager.cleanup_old_data(days_to_keep=0)
        
        # Attendre un peu pour s'assurer que les données sont supprimées
        time.sleep(0.5)
        
        # Vérification que les données ont été supprimées
        retrieved_data = self.mongodb_manager.get_latest_market_data(symbol)
        self.assertIsNone(retrieved_data)

if __name__ == '__main__':
    unittest.main()
