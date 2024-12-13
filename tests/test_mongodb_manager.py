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
        self.assertEqual(retrieved_data['data']['ticker']['price'], 50000.0)

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
        self.assertEqual(retrieved_data['data']['ticker']['price'], 50000.0)

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
        self.assertEqual(result['data']['ticker']['price'], 50000.0)
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

    def test_cache_retention(self):
        """Teste la rétention du cache des indicateurs avancés"""
        # Configuration
        symbol = "BTCUSDT"
        current_time = datetime.now(tz.utc)
        old_time = current_time - timedelta(hours=25)  # Plus ancien que la rétention par défaut

        # Créer d'abord les données de marché
        market_data = {
            "symbol": symbol,
            "timestamp": old_time,
            "data": {"price": 45000.0}
        }
        result = self.mongodb_manager.market_data.insert_one(market_data)
        market_data_id = result.inserted_id

        # Données de test au format correct
        test_indicators = {
            "symbol": symbol,
            "timestamp": old_time,
            "type": "technical",
            "data": {
                "advanced_rsi": 70.5,
                "advanced_macd": {"value": 150.0, "signal": 145.0}
            }
        }

        # Création d'entrées de cache anciennes et récentes
        self.mongodb_manager.save_advanced_indicators(market_data_id, test_indicators)
        
        # Déclencher le nettoyage du cache
        self.mongodb_manager.cleanup_cache()
        
        # Vérifier que seules les entrées récentes sont conservées
        cached_data = list(self.mongodb_manager.indicators.find({"symbol": symbol}))
        self.assertEqual(len(cached_data), 1)
        self.assertEqual(cached_data[0]["indicators"]["advanced_rsi"], 70.5)

    def test_cleanup_old_data(self):
        """Teste le nettoyage des anciennes données de marché"""
        symbol = "BTCUSDT"
        current_time = datetime.now(tz.utc)
        old_time = current_time - timedelta(days=31)  # Plus ancien que la période de rétention
        
        # Création de données anciennes et récentes
        old_data = {
            "symbol": symbol,
            "timestamp": old_time,
            "data": {"price": 45000.0}
        }
        new_data = {
            "symbol": symbol,
            "timestamp": current_time,
            "data": {"price": 50000.0}
        }
        
        # Stockage des données
        self.mongodb_manager.store_market_data(old_data)
        self.mongodb_manager.store_market_data(new_data)
        
        # Nettoyage des anciennes données
        self.mongodb_manager.cleanup_old_data()
        
        # Vérification que seules les données récentes sont conservées
        market_data = list(self.mongodb_manager.market_data.find({"symbol": symbol}))
        self.assertEqual(len(market_data), 1)
        self.assertEqual(market_data[0]["data"]["price"], 50000.0)

    def test_cache_initialization(self):
        """Teste l'initialisation du cache avec une durée de rétention personnalisée"""
        custom_retention = 12  # 12 heures
        mongodb_manager = MongoDBManager(cache_retention_hours=custom_retention)
        
        # Vérification de la configuration du cache
        self.assertEqual(mongodb_manager.cache_retention_hours, custom_retention)
        
        # Nettoyage
        if hasattr(mongodb_manager, 'client'):
            mongodb_manager.client.close()

    def test_save_and_retrieve_advanced_indicators(self):
        """Teste le stockage et la récupération des indicateurs avancés"""
        symbol = "BTCUSDT"
        timestamp = datetime.now(tz.utc)
        
        # Créer d'abord les données de marché
        market_data = {
            "symbol": symbol,
            "timestamp": timestamp,
            "data": {"price": 45000.0}
        }
        result = self.mongodb_manager.market_data.insert_one(market_data)
        market_data_id = result.inserted_id
        
        advanced_indicators = {
            "symbol": symbol,
            "timestamp": timestamp,
            "type": "technical",
            "data": {
                "supertrend": {
                    "trend": "UP",
                    "value": 45000.0,
                    "upper_band": 46000.0,
                    "lower_band": 44000.0
                },
                "fibonacci_retracement": {
                    "levels": {
                        "0.236": 44500.0,
                        "0.382": 44000.0,
                        "0.618": 43000.0
                    }
                },
                "ichimoku": {
                    "tenkan_sen": 45200.0,
                    "kijun_sen": 44800.0,
                    "senkou_span_a": 45500.0,
                    "senkou_span_b": 44200.0,
                    "chikou_span": 45100.0
                }
            }
        }
        
        # Test du stockage
        self.mongodb_manager.save_advanced_indicators(market_data_id, advanced_indicators)
        
        # Test de la récupération
        retrieved_data = self.mongodb_manager.get_market_data_with_indicators(symbol, include_advanced=True)
        
        self.assertIsNotNone(retrieved_data)
        self.assertIn('indicators', retrieved_data)
        self.assertIn('supertrend', retrieved_data['indicators'])
        self.assertEqual(retrieved_data['indicators']['supertrend']['trend'], "UP")
        self.assertEqual(retrieved_data['indicators']['fibonacci_retracement']['levels']['0.236'], 44500.0)
        self.assertEqual(retrieved_data['indicators']['ichimoku']['tenkan_sen'], 45200.0)

    def test_advanced_indicators_history(self):
        """Teste la récupération de l'historique des indicateurs avancés"""
        symbol = "BTCUSDT"
        base_time = datetime.now(tz.utc)
        
        # Création de plusieurs entrées d'indicateurs
        indicators_history = []
        for i in range(3):
            timestamp = base_time - timedelta(hours=i)
            
            # Créer les données de marché
            market_data = {
                "symbol": symbol,
                "timestamp": timestamp,
                "data": {"price": 45000.0 + (i * 100)}
            }
            result = self.mongodb_manager.market_data.insert_one(market_data)
            market_data_id = result.inserted_id
            
            # Créer les indicateurs
            indicators = {
                "symbol": symbol,
                "timestamp": timestamp,
                "type": "technical",
                "data": {
                    "supertrend": {
                        "trend": "UP" if i % 2 == 0 else "DOWN",
                        "value": 45000.0 + (i * 100)
                    },
                    "pivot_points": {
                        "r1": 46000.0 + (i * 100),
                        "s1": 44000.0 - (i * 100)
                    }
                }
            }
            self.mongodb_manager.save_advanced_indicators(market_data_id, indicators)
            indicators_history.append((timestamp, indicators))
        
        # Test de la récupération avec limite
        recent_indicators = self.mongodb_manager.get_latest_indicators(symbol, limit=2)
        
        self.assertEqual(len(recent_indicators), 2)
        self.assertEqual(recent_indicators[0]["indicators"]["supertrend"]["trend"], "UP")

    def test_advanced_indicators_aggregation(self):
        """Teste l'agrégation des indicateurs avancés"""
        symbol = "BTCUSDT"
        base_time = datetime.now(tz.utc)
        
        # Création de données pour l'agrégation
        for i in range(24):  # 24 heures de données
            timestamp = base_time - timedelta(hours=i)
            
            # Créer les données de marché
            market_data = {
                "symbol": symbol,
                "timestamp": timestamp,
                "data": {"price": 45000.0 + (i * 10)}
            }
            result = self.mongodb_manager.market_data.insert_one(market_data)
            market_data_id = result.inserted_id
            
            # Créer les indicateurs
            indicators = {
                "symbol": symbol,
                "timestamp": timestamp,
                "type": "technical",
                "data": {
                    "supertrend": {
                        "trend": "UP" if i % 3 == 0 else "DOWN",
                        "value": 45000.0 + (i * 10)
                    },
                    "volume_profile": {
                        "value": 1000.0 + (i * 100),
                        "poc": 45500.0
                    }
                }
            }
            self.mongodb_manager.save_advanced_indicators(market_data_id, indicators)
        
        # Test de l'agrégation par période
        hourly_data = self.mongodb_manager.get_aggregated_indicators(
            symbol,
            "1h",
            start_time=base_time - timedelta(hours=24)
        )
        
        self.assertTrue(len(hourly_data) > 0)
        for entry in hourly_data:
            self.assertIn("timestamp", entry)
            self.assertIn("indicators", entry)
            self.assertIn("supertrend", entry["indicators"])
            self.assertIn("volume_profile", entry["indicators"])

class TestMongoDBManagerDataValidation(unittest.TestCase):
    def setUp(self):
        """Configuration initiale pour chaque test"""
        self.mongodb_manager = MongoDBManager()
        # Nettoyage des collections avant chaque test
        self.mongodb_manager.market_data.delete_many({})
        self.mongodb_manager.indicators.delete_many({})
        
    def test_market_data_validation(self):
        """Test la validation des données de marché"""
        # Test avec des données valides
        valid_data = {
            'symbol': 'BTCUSDT',
            'timestamp': datetime.now(tz.utc),
            'data': {
                'open': 50000.0,
                'high': 51000.0,
                'low': 49000.0,
                'close': 50500.0,
                'volume': 100.0
            }
        }
        self.mongodb_manager.store_market_data(valid_data)
        
        # Test avec des types invalides
        invalid_type_data = {
            'symbol': 123,  # Devrait être une chaîne
            'timestamp': "2024-01-01",  # Devrait être un datetime
            'data': {
                'open': "50000",  # Devrait être un float
                'high': None,
                'low': None,
                'close': None,
                'volume': -1  # Volume ne peut pas être négatif
            }
        }
        with self.assertRaises(ValueError):
            self.mongodb_manager.store_market_data(invalid_type_data)
            
    def test_indicators_validation(self):
        """Test la validation des indicateurs"""
        # Test avec des indicateurs valides
        valid_indicators = {
            'timestamp': datetime.now(tz.utc),
            'symbol': 'BTCUSDT',
            'type': 'technical',
            'data': {
                'rsi': 65.5,
                'macd': {'histogram': 0.5, 'signal': 0.3, 'macd': 0.8}
            }
        }
        self.mongodb_manager.store_indicators(valid_indicators)
        
        # Test avec des valeurs hors limites
        invalid_range_indicators = {
            'timestamp': datetime.now(tz.utc),
            'symbol': 'BTCUSDT',
            'type': 'technical',
            'data': {
                'rsi': 150.0,  # RSI doit être entre 0 et 100
                'macd': {'histogram': None, 'signal': None, 'macd': None}
            }
        }
        with self.assertRaises(ValueError):
            self.mongodb_manager.store_indicators(invalid_range_indicators)
            
    def test_required_fields_validation(self):
        """Test la validation des champs requis"""
        # Test avec des champs manquants
        missing_fields_data = {
            'symbol': 'BTCUSDT',
            # timestamp manquant
            'data': {
                'open': 50000.0,
                # high manquant
                'low': 49000.0,
                'close': 50500.0,
                'volume': 100.0
            }
        }
        with self.assertRaises(ValueError):
            self.mongodb_manager.store_market_data(missing_fields_data)
            
    def test_symbol_validation(self):
        """Test la validation du format des symboles"""
        # Test avec des symboles invalides
        invalid_symbols = ['BTC/USDT', 'btc-usdt', '', ' ', None]
        valid_data_template = {
            'timestamp': datetime.now(tz.utc),
            'data': {
                'open': 50000.0,
                'high': 51000.0,
                'low': 49000.0,
                'close': 50500.0,
                'volume': 100.0
            }
        }
        
        for invalid_symbol in invalid_symbols:
            test_data = valid_data_template.copy()
            test_data['symbol'] = invalid_symbol
            with self.assertRaises(ValueError):
                self.mongodb_manager.store_market_data(test_data)
                
    def test_timestamp_validation(self):
        """Test la validation des timestamps"""
        future_time = datetime.now(tz.utc) + timedelta(days=1)
        too_old_time = datetime.now(tz.utc) - timedelta(days=365*2)
        
        valid_data_template = {
            'symbol': 'BTCUSDT',
            'data': {
                'open': 50000.0,
                'high': 51000.0,
                'low': 49000.0,
                'close': 50500.0,
                'volume': 100.0
            }
        }
        
        # Test avec une date future
        future_data = valid_data_template.copy()
        future_data['timestamp'] = future_time
        with self.assertRaises(ValueError):
            self.mongodb_manager.store_market_data(future_data)
            
        # Test avec une date trop ancienne
        old_data = valid_data_template.copy()
        old_data['timestamp'] = too_old_time
        with self.assertRaises(ValueError):
            self.mongodb_manager.store_market_data(old_data)

if __name__ == '__main__':
    unittest.main()