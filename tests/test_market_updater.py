import unittest
from unittest.mock import Mock, patch, MagicMock
import time
from datetime import datetime
import os

from src.services.market_updater import MarketDataUpdater

class TestMarketDataUpdater(unittest.TestCase):
    def setUp(self):
        """Configure l'environnement de test"""
        # Mock des variables d'environnement
        os.environ['BYBIT_API_KEY'] = 'test_api_key'
        os.environ['BYBIT_API_SECRET'] = 'test_api_secret'
        
        self.symbols = ["BTCUSDT", "ETHUSDT"]
        self.updater = MarketDataUpdater(
            symbols=self.symbols,
            update_interval=1,  # 1 seconde pour les tests
            max_retries=2,
            use_testnet=True  # Utiliser le testnet pour les tests
        )

    def tearDown(self):
        """Nettoyage après chaque test"""
        if hasattr(self, 'updater'):
            self.updater.stop()
            if hasattr(self.updater, 'db'):
                self.updater.db.close()
        # Nettoie les variables d'environnement
        os.environ.pop('BYBIT_API_KEY', None)
        os.environ.pop('BYBIT_API_SECRET', None)

    @patch('src.services.market_updater.MarketDataCollector')
    @patch('src.services.market_updater.MongoDBManager')
    def test_market_data_update(self, mock_db, mock_collector):
        """Teste la mise à jour des données de marché"""
        # Configuration des mocks
        mock_collector_instance = mock_collector.return_value
        mock_collector_instance.get_ticker.return_value = {
            "symbol": "BTCUSDT",
            "last_price": "50000.0",
            "volume_24h": "1000.0"
        }
        mock_collector_instance.get_order_book.return_value = {
            "symbol": "BTCUSDT",
            "bids": [["49999.0", "1.0"]],
            "asks": [["50001.0", "1.0"]]
        }
        mock_collector_instance.get_recent_trades.return_value = [{
            "symbol": "BTCUSDT",
            "price": "50000.0",
            "quantity": "1.0",
            "side": "Buy",
            "time": int(datetime.now().timestamp() * 1000)
        }]
        mock_collector_instance.get_klines.return_value = [{
            "timestamp": int(datetime.now().timestamp() * 1000),
            "open": "49000.0",
            "high": "51000.0",
            "low": "48000.0",
            "close": "50000.0",
            "volume": "100.0"
        }]

        # Mock de l'API monitor
        with patch('src.services.market_updater.APIMonitor') as mock_monitor:
            mock_monitor_instance = mock_monitor.return_value
            mock_monitor_instance.check_api_health.return_value = True
            
            # Création de l'updater avec un intervalle court pour les tests
            self.updater = MarketDataUpdater(
                symbols=self.symbols,
                update_interval=0.1,  # 100ms pour des tests plus rapides
                use_testnet=True
            )
            
            # Démarre le service
            self.updater.start()
            
            # Attend quelques cycles de mise à jour
            time.sleep(0.3)
            
            # Arrête le service
            self.updater.stop()
            
            # Vérifie que les méthodes ont été appelées
            mock_collector_instance.get_ticker.assert_called()
            mock_collector_instance.get_order_book.assert_called()
            mock_collector_instance.get_recent_trades.assert_called()
            mock_db.return_value.store_market_data.assert_called()

            # Vérifie le format des données stockées
            stored_data = mock_db.return_value.store_market_data.call_args[0][1]
            self.assertIn('symbol', stored_data)
            self.assertIn('price', stored_data)
            self.assertIn('volume', stored_data)
            self.assertIn('order_book', stored_data)
            self.assertIn('recent_trades', stored_data)
            self.assertEqual(stored_data['exchange'], 'bybit')
            self.assertEqual(stored_data['network'], 'testnet')

    def test_invalid_api_keys(self):
        """Teste la gestion des clés API invalides"""
        os.environ['BYBIT_API_KEY'] = ''
        os.environ['BYBIT_API_SECRET'] = ''
        
        with self.assertRaises(ValueError):
            MarketDataUpdater(symbols=self.symbols)

    @patch('src.services.market_updater.MarketDataCollector')
    @patch('src.services.market_updater.MongoDBManager')
    def test_get_latest_data(self, mock_db, mock_collector):
        """Teste la récupération des dernières données"""
        # Mock des données de marché
        mock_data = {
            "symbol": "BTCUSDT",
            "timestamp": datetime.now(),
            "price": "50000.0",
            "volume": "100.0"
        }
        self.updater.db.get_latest_market_data = MagicMock(return_value=mock_data)
        
        # Test avec des données valides
        result = self.updater.get_latest_data("BTCUSDT")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertEqual(result["price"], "50000.0")
        self.assertEqual(result["volume"], "100.0")
        
        # Test sans données
        self.updater.db.get_latest_market_data = MagicMock(return_value=None)
        result = self.updater.get_latest_data("BTCUSDT")
        
        self.assertIsNotNone(result)
        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertIsNone(result["price"])
        self.assertIsNone(result["volume"])

    @patch('src.services.market_updater.MarketDataCollector')
    @patch('src.services.market_updater.MongoDBManager')
    def test_calculate_indicators(self, mock_db, mock_collector):
        """Test le calcul des indicateurs techniques"""
        symbol = "BTCUSDT"
        
        # Mock des données historiques
        historical_data = [
            {
                "timestamp": datetime.now(),
                "open": "50000",
                "high": "51000", 
                "low": "49000",
                "close": "50500",
                "volume": "100"
            }
        ]
        
        mock_collector.return_value.get_klines.return_value = historical_data
        
        # Test avec des données valides
        result = self.updater._calculate_indicators(symbol, {})
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result["symbol"], symbol)
        self.assertIn("timestamp", result)
        self.assertIn("calculations", result)
        
        # Test avec aucune donnée historique
        mock_collector.return_value.get_klines.return_value = []
        result = self.updater._calculate_indicators(symbol, {})
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result["symbol"], symbol)
        self.assertIn("timestamp", result)
        self.assertEqual(result["calculations"], {})

if __name__ == '__main__':
    unittest.main()
