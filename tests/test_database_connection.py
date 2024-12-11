import unittest
from datetime import datetime
from src.database.mongodb_manager import MongoDBManager

class TestDatabaseConnection(unittest.TestCase):
    def setUp(self):
        """Initialise la connexion à la base de données pour les tests"""
        self.db_manager = MongoDBManager()
        self.test_symbol = "BTCUSDT"

    def tearDown(self):
        """Nettoie après les tests"""
        # Supprime les données de test
        self.db_manager.market_data.delete_many({"symbol": self.test_symbol})
        self.db_manager.indicators.delete_many({"symbol": self.test_symbol})
        self.db_manager.trades.delete_many({"symbol": self.test_symbol})
        self.db_manager.close()

    def test_market_data_operations(self):
        """Teste les opérations CRUD sur les données de marché"""
        # Données de test
        test_data = {
            "price": 50000.0,
            "volume": 100.0,
            "trades": 50
        }

        # Test d'insertion
        self.db_manager.store_market_data(self.test_symbol, test_data)

        # Test de récupération
        result = self.db_manager.get_latest_market_data(self.test_symbol)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["symbol"], self.test_symbol)
        self.assertEqual(result["data"], test_data)

    def test_indicators_operations(self):
        """Teste les opérations CRUD sur les indicateurs"""
        # Données de test
        test_indicators = {
            "rsi": 65.5,
            "macd": {
                "value": 100.0,
                "signal": 95.0,
                "histogram": 5.0
            }
        }

        # Test d'insertion
        self.db_manager.store_indicators(self.test_symbol, test_indicators)

        # Test de récupération
        result = self.db_manager.get_latest_indicators(self.test_symbol)
        
        self.assertIsNotNone(result)
        self.assertEqual(result["symbol"], self.test_symbol)
        self.assertEqual(result["indicators"], test_indicators)

    def test_trades_operations(self):
        """Teste les opérations CRUD sur les trades"""
        # Données de test
        test_trade = {
            "symbol": self.test_symbol,
            "side": "BUY",
            "price": 50000.0,
            "quantity": 1.0,
            "status": "COMPLETED"
        }

        # Test d'insertion
        self.db_manager.store_trade(test_trade)

        # Test de récupération
        results = self.db_manager.get_trades_history(self.test_symbol, limit=1)
        
        self.assertEqual(len(results), 1)
        result = results[0]
        self.assertEqual(result["symbol"], self.test_symbol)
        self.assertEqual(result["side"], test_trade["side"])
        self.assertEqual(result["price"], test_trade["price"])
        self.assertEqual(result["quantity"], test_trade["quantity"])

    def test_historical_data_retrieval(self):
        """Teste la récupération des données historiques"""
        # Insertion de plusieurs données
        test_data = {"price": 50000.0, "volume": 100.0}
        self.db_manager.store_market_data(self.test_symbol, test_data)

        # Test de récupération avec période
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = datetime.now()
        results = self.db_manager.get_historical_data(
            self.test_symbol,
            start_time,
            end_time
        )

        self.assertGreater(len(results), 0)
        self.assertEqual(results[0]["symbol"], self.test_symbol)

if __name__ == '__main__':
    unittest.main()
