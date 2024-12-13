import unittest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from src.database.mongodb_manager import MongoDBManager
import time
from datetime import timezone as tz

class TestMongoDBManager(unittest.TestCase):
    def setUp(self):
        """Configuration initiale pour chaque test"""
        self.mongodb_manager = MongoDBManager()
        # Nettoyage des collections avant chaque test
        self.mongodb_manager.market_data.delete_many({})
        self.mongodb_manager.indicators.delete_many({})
        self.mongodb_manager.trades.delete_many({})
        self.mongodb_manager.monitoring.delete_many({})
        self.mongodb_manager.api_metrics.delete_many({})
        self.mongodb_manager.strategy_config.delete_many({})
        
    def tearDown(self):
        """Nettoie après les tests"""
        if hasattr(self.mongodb_manager, 'client'):
            self.mongodb_manager.client.close()

    def test_store_and_retrieve_market_data(self):
        """Teste le stockage et la récupération des données de marché"""
        symbol = "BTCUSDT"
        data = {
            "symbol": symbol,
            "timestamp": datetime.now(tz.utc),
            "data": {
                "ticker": {
                    "price": 50000.0
                }
            }
        }
        
        # Stockage des données
        self.mongodb_manager.store_market_data(data)
        
        # Récupération et vérification
        retrieved_data = self.mongodb_manager.get_latest_market_data(symbol)
        self.assertIsNotNone(retrieved_data)
        self.assertEqual(retrieved_data['symbol'], symbol)
        self.assertEqual(retrieved_data['price'], 50000.0)

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
        retrieved_indicators = self.mongodb_manager.get_latest_indicators(symbol, limit=1)
        
        # Vérifications
        self.assertIsNotNone(retrieved_indicators)
        self.assertEqual(len(retrieved_indicators), 1)
        self.assertEqual(retrieved_indicators[0]["symbol"], symbol)
        self.assertEqual(retrieved_indicators[0]["indicators"], test_indicators)

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
        start_time = datetime.now(tz.utc) - timedelta(minutes=1)
        trades = self.mongodb_manager.get_trades_by_timeframe(start_time)
        
        # Vérifications
        self.assertEqual(len(trades), 1)
        retrieved_trade = trades[0]
        self.assertEqual(retrieved_trade["symbol"], trade_data["symbol"])
        self.assertEqual(retrieved_trade["side"], trade_data["side"])
        self.assertEqual(retrieved_trade["price"], trade_data["price"])
        self.assertEqual(retrieved_trade["quantity"], trade_data["quantity"])

    def test_store_and_retrieve_monitoring_data(self):
        """Teste le stockage et la récupération des données de monitoring"""
        # Stockage des données
        test_data = {
            "endpoint": "test",
            "status": "success",
            "response_time": 0.1
        }
        self.mongodb_manager.store_monitoring_data(test_data)
        
        # Attendre un peu pour s'assurer que les données sont stockées
        time.sleep(0.1)
        
        # Définir une plage de temps qui inclut certainement nos données
        end_time = datetime.now(tz.utc)
        start_time = end_time - timedelta(minutes=1)
        
        # Récupération et vérification
        result = self.mongodb_manager.get_monitoring_data(start_time, end_time)
        
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0]["endpoint"], "test")
        self.assertEqual(result[0]["status"], "success")

    def test_store_and_retrieve_api_metrics(self):
        """Teste le stockage et la récupération des métriques d'API"""
        # Données de test
        metric_data = {
            "endpoint": "/api/v1/trades",
            "metric_type": "latency",
            "value": 0.2
        }
        
        # Stockage des métriques
        self.mongodb_manager.store_api_metric(metric_data)
        
        # Récupération des métriques
        retrieved_metrics = self.mongodb_manager.get_api_metrics(
            endpoint=metric_data["endpoint"],
            metric_type=metric_data["metric_type"]
        )
        
        # Vérifications
        self.assertEqual(len(retrieved_metrics), 1)
        self.assertEqual(retrieved_metrics[0]["endpoint"], metric_data["endpoint"])
        self.assertEqual(retrieved_metrics[0]["metric_type"], metric_data["metric_type"])
        self.assertEqual(retrieved_metrics[0]["value"], metric_data["value"])

    def test_store_and_retrieve_strategy_config(self):
        """Teste le stockage et la récupération de la configuration de stratégie"""
        # Données de test
        strategy_name = "RSI_Strategy"
        config_data = {
            "rsi_period": 14,
            "overbought": 70,
            "oversold": 30
        }
        
        # Stockage de la configuration
        self.mongodb_manager.store_strategy_config(strategy_name, config_data)
        
        # Récupération de la configuration
        retrieved_config = self.mongodb_manager.get_strategy_config(strategy_name)
        
        # Vérifications
        self.assertIsNotNone(retrieved_config)
        self.assertEqual(retrieved_config["strategy_name"], strategy_name)
        self.assertEqual(retrieved_config["config"], config_data)

    def test_bulk_operations(self):
        """Teste les opérations en masse"""
        data = {
            "symbol": "BTCUSDT",
            "timestamp": datetime.now(tz.utc),
            "data": {
                "ticker": {
                    "price": 50000.0
                }
            }
        }
        
        # Test d'insertion
        self.mongodb_manager.store_market_data(data)
        
        # Vérification
        retrieved_data = self.mongodb_manager.get_latest_market_data(data["symbol"])
        self.assertIsNotNone(retrieved_data)
        self.assertEqual(retrieved_data['symbol'], data['symbol'])
        self.assertEqual(retrieved_data['price'], 50000.0)

        # Données de test pour les indicateurs
        indicators_list = [
            {
                "symbol": "BTCUSDT",
                "indicators": {"rsi": 65.5, "macd": 100.0}
            },
            {
                "symbol": "ETHUSDT",
                "indicators": {"rsi": 45.5, "macd": -50.0}
            }
        ]
        
        # Test du stockage en masse des indicateurs
        self.mongodb_manager.store_indicators_bulk(indicators_list)
        
        # Vérification des données stockées
        for data in indicators_list:
            retrieved_data = self.mongodb_manager.get_latest_indicators(data["symbol"], limit=1)
            self.assertEqual(len(retrieved_data), 1)
            self.assertEqual(retrieved_data[0]["indicators"], data["indicators"])

    def test_cleanup_old_data(self):
        """Teste le nettoyage des anciennes données"""
        symbol = "BTCUSDT"
        # Insérer des données
        data = {
            "symbol": symbol,
            "timestamp": datetime.now(tz.utc),
            "data": {
                "ticker": {
                    "price": 50000.0
                }
            }
        }
        self.mongodb_manager.store_market_data(data)
        
        # Vérifier avant nettoyage
        retrieved_market_data = self.mongodb_manager.get_latest_market_data(symbol)
        self.assertIsNotNone(retrieved_market_data)
        self.assertEqual(retrieved_market_data['symbol'], symbol)
        
        # Nettoyage des données
        self.mongodb_manager.cleanup_old_data(days_to_keep=0)
        
        # Attendre un peu pour s'assurer que les données sont supprimées
        time.sleep(0.5)
        
        # Vérification que les données ont été supprimées
        retrieved_market_data = self.mongodb_manager.get_latest_market_data(symbol)
        self.assertIsNone(retrieved_market_data)
        
        start_time = datetime.now(tz.utc) - timedelta(minutes=1)
        retrieved_monitoring = self.mongodb_manager.get_monitoring_data(start_time)
        self.assertEqual(len(retrieved_monitoring), 0)
        
        retrieved_metrics = self.mongodb_manager.get_api_metrics(endpoint="test")
        self.assertEqual(len(retrieved_metrics), 0)

    def test_get_latest_market_data(self):
        """Test de récupération des dernières données de marché"""
        # Préparation des données
        symbol = "BTCUSDT"
        data = {
            "symbol": symbol,
            "timestamp": datetime.now(tz.utc),
            "data": {
                "ticker": {
                    "price": 50000.0
                }
            }
        }
        self.mongodb_manager.store_market_data(data)
        
        # Test
        result = self.mongodb_manager.get_latest_market_data(symbol)
        
        # Vérifications
        self.assertIsInstance(result, dict)
        self.assertEqual(result['symbol'], symbol)
        self.assertEqual(result['price'], 50000.0)
        self.assertIn('timestamp', result)

    def test_get_latest_indicators(self):
        """Test de récupération des derniers indicateurs"""
        symbol = "BTCUSDT"
        test_data = {
            "symbol": symbol,
            "timestamp": datetime.now(tz.utc),
            "rsi": 65.5
        }
        self.mongodb_manager.indicators.insert_one(test_data)
        
        result = self.mongodb_manager.get_latest_indicators(symbol)
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["symbol"], symbol)
        self.assertEqual(result[0]["rsi"], 65.5)

    def test_get_trades_by_timeframe(self):
        """Test de récupération des transactions par période"""
        start_time = datetime.now(tz.utc) - timedelta(hours=1)
        end_time = datetime.now(tz.utc)
        test_trade = {
            "symbol": "BTCUSDT",
            "timestamp": datetime.now(tz.utc) - timedelta(minutes=30),
            "price": 50000.0,
            "quantity": 1.0
        }
        self.mongodb_manager.trades.insert_one(test_trade)
        
        result = self.mongodb_manager.get_trades_by_timeframe(start_time, end_time)
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0]["symbol"], "BTCUSDT")

    def test_store_and_get_monitoring_data(self):
        """Test de stockage et récupération des données de monitoring"""
        test_data = {
            "event_type": "API_CALL",
            "endpoint": "/api/v3/ticker",
            "response_time": 150
        }
        self.mongodb_manager.store_monitoring_data(test_data)
        
        start_time = datetime.now(tz.utc) - timedelta(minutes=5)
        end_time = datetime.now(tz.utc)
        result = self.mongodb_manager.get_monitoring_data(start_time, end_time)
        
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0]["event_type"], "API_CALL")
        self.assertEqual(result[0]["endpoint"], "/api/v3/ticker")

    def test_store_and_get_api_metrics(self):
        """Test de stockage et récupération des métriques d'API"""
        test_metric = {
            "endpoint": "/api/v3/klines",
            "metric_type": "response_time",
            "value": 200
        }
        self.mongodb_manager.store_api_metric(test_metric)
        
        result = self.mongodb_manager.get_api_metrics(
            endpoint="/api/v3/klines",
            metric_type="response_time"
        )
        
        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0]["endpoint"], "/api/v3/klines")
        self.assertEqual(result[0]["metric_type"], "response_time")
        self.assertEqual(result[0]["value"], 200)

if __name__ == '__main__':
    unittest.main()