import unittest
from unittest.mock import Mock, patch
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
        """Nettoie après les tests"""
        if self.updater.is_running:
            self.updater.stop()
        # Nettoie les variables d'environnement
        os.environ.pop('BYBIT_API_KEY', None)
        os.environ.pop('BYBIT_API_SECRET', None)

    @patch('src.services.market_updater.MarketDataCollector')
    @patch('src.services.market_updater.MongoDBManager')
    def test_market_data_update(self, mock_db, mock_collector):
        """Teste la mise à jour des données de marché"""
        # Configuration des mocks pour Bybit
        mock_collector_instance = mock_collector.return_value
        mock_collector_instance.get_ticker.return_value = {
            "symbol": "BTCUSDT",
            "lastPrice": "50000.0",
            "volume24h": "1000.0",
            "turnover24h": "50000000.0"
        }
        mock_collector_instance.get_order_book.return_value = {
            "s": "BTCUSDT",
            "b": [["49999.0", "1.0"]],  # bids
            "a": [["50001.0", "1.0"]]   # asks
        }
        mock_collector_instance.get_recent_trades.return_value = [{
            "symbol": "BTCUSDT",
            "price": "50000.0",
            "size": "1.0",
            "side": "Buy",
            "time": datetime.now().timestamp() * 1000
        }]
        mock_collector_instance.get_funding_rate.return_value = {
            "symbol": "BTCUSDT",
            "fundingRate": "0.0001",
            "fundingRateTimestamp": str(int(datetime.now().timestamp() * 1000))
        }
        mock_collector_instance.get_klines.return_value = [{
            "timestamp": str(int(datetime.now().timestamp() * 1000)),
            "open": "49000.0",
            "high": "51000.0",
            "low": "48000.0",
            "close": "50000.0",
            "volume": "100.0"
        }]

        # Mock the API monitor
        with patch('src.services.market_updater.APIMonitor') as mock_monitor:
            mock_monitor_instance = mock_monitor.return_value
            mock_monitor_instance.check_api_health.return_value = True
            
            # Create updater with shorter interval for testing
            self.updater = MarketDataUpdater(
                symbols=self.symbols,
                update_interval=0.1,  # 100ms for faster testing
                use_testnet=True
            )
            
            # Démarre le service
            self.updater.start()
            
            # Attend quelques cycles de mise à jour
            time.sleep(0.5)  # Should allow for multiple updates
            
            # Arrête le service
            self.updater.stop()
            
            # Vérifie que les méthodes Bybit ont été appelées
            mock_collector_instance.get_ticker.assert_called()
            mock_collector_instance.get_order_book.assert_called()
            mock_collector_instance.get_recent_trades.assert_called()
            mock_collector_instance.get_funding_rate.assert_called()
            mock_db.return_value.store_market_data.assert_called()

            # Vérifie le format des données stockées
            stored_data = mock_db.return_value.store_market_data.call_args[0][1]
            self.assertIn('ticker', stored_data)
            self.assertIn('order_book', stored_data)
            self.assertIn('recent_trades', stored_data)
            self.assertIn('funding_rate', stored_data)
            self.assertEqual(stored_data['source'], 'bybit')
            self.assertEqual(stored_data['network'], 'testnet')

    @patch('src.services.market_updater.APIMonitor')
    def test_api_availability_check(self, mock_monitor):
        """Teste la vérification de la disponibilité de l'API"""
        # Configure le mock pour simuler une API indisponible
        mock_monitor_instance = mock_monitor.return_value
        mock_monitor_instance.check_api_health.return_value = False
        
        # Create updater with shorter interval for testing
        self.updater = MarketDataUpdater(
            symbols=self.symbols,
            update_interval=0.1,  # 100ms for faster testing
            use_testnet=True
        )
        
        # Démarre le service
        self.updater.start()
        
        # Attend quelques cycles
        time.sleep(0.3)  # Should allow for multiple checks
        
        # Arrête le service
        self.updater.stop()
        
        # Vérifie que la vérification a été effectuée avec le bon endpoint
        mock_monitor_instance.check_api_health.assert_called_with("/v5/market/tickers")

    def test_service_control(self):
        """Teste le contrôle du service (démarrage/arrêt)"""
        # Vérifie l'état initial
        self.assertFalse(self.updater.is_running)
        
        # Démarre le service
        self.updater.start()
        self.assertTrue(self.updater.is_running)
        
        # Arrête le service
        self.updater.stop()
        self.assertFalse(self.updater.is_running)

    @patch('src.services.market_updater.load_dotenv')
    def test_missing_api_keys(self, mock_load_dotenv):
        """Teste la gestion des clés API manquantes"""
        # Supprime les variables d'environnement et arrête l'updater existant
        if self.updater.is_running:
            self.updater.stop()
            
        # Sauvegarde et supprime les variables d'environnement
        api_key = os.environ.pop('BYBIT_API_KEY', None)
        api_secret = os.environ.pop('BYBIT_API_SECRET', None)
        
        try:
            # Vérifie que l'initialisation échoue sans les clés API
            with self.assertRaises(ValueError) as context:
                MarketDataUpdater(
                    symbols=["BTCUSDT"],
                    update_interval=1,
                    use_testnet=True
                )
            
            self.assertIn("Les clés API Bybit sont requises", str(context.exception))
            mock_load_dotenv.assert_called_once()
            
        finally:
            # Restaure les variables d'environnement pour les autres tests
            if api_key:
                os.environ['BYBIT_API_KEY'] = api_key
            if api_secret:
                os.environ['BYBIT_API_SECRET'] = api_secret

if __name__ == '__main__':
    unittest.main()
