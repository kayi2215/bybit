import unittest
from unittest.mock import Mock, patch, create_autospec
import time
from datetime import datetime
import os
import pandas as pd

from src.services.market_updater import MarketUpdater
from src.database.mongodb_manager import MongoDBManager
from src.data_collector.market_data import MarketDataCollector

class TestMarketUpdater(unittest.TestCase):
    def setUp(self):
        """Configuration initiale pour chaque test"""
        self.symbols = ['BTCUSDT', 'ETHUSDT']
        self.mock_db = Mock(spec=MongoDBManager)
        self.api_key = "test_api_key"
        self.api_secret = "test_api_secret"
        
        # Création d'un mock avec les méthodes nécessaires
        self.mock_collector = create_autospec(MarketDataCollector, instance=True)
        self.patcher = patch('src.services.market_updater.MarketDataCollector', return_value=self.mock_collector)
        self.mock_collector_class = self.patcher.start()
        
        # Mock de l'APIMonitor
        self.mock_monitor = Mock()
        self.mock_monitor.check_api_health.return_value = {"status": "OK"}
        self.monitor_patcher = patch('src.services.market_updater.APIMonitor', return_value=self.mock_monitor)
        self.monitor_patcher.start()
        
        # Création de l'instance de test
        self.market_updater = MarketUpdater(
            symbols=self.symbols,
            db=self.mock_db,
            api_key=self.api_key,
            api_secret=self.api_secret,
            use_testnet=True
        )

    def tearDown(self):
        """Nettoyage après chaque test"""
        if hasattr(self, 'market_updater'):
            self.market_updater.stop()
            # Attendre que le service s'arrête complètement
            if hasattr(self.market_updater, 'update_thread') and self.market_updater.update_thread:
                self.market_updater.update_thread.join(timeout=2)
        self.patcher.stop()
        self.monitor_patcher.stop()

    def test_init(self):
        """Test de l'initialisation du MarketUpdater"""
        self.assertEqual(self.market_updater.symbols, self.symbols)
        self.assertEqual(self.market_updater.db, self.mock_db)
        self.mock_collector_class.assert_called_once_with(
            api_key=self.api_key,
            api_secret=self.api_secret,
            use_testnet=True
        )
        self.assertEqual(self.market_updater.error_counts, {symbol: 0 for symbol in self.symbols})

    def test_update_market_data_success(self):
        """Test de la mise à jour réussie des données de marché"""
        symbol = 'BTCUSDT'
        timestamp = datetime.now()
        
        # Configuration des mocks avec le format correct des données
        self.mock_collector.get_ticker.return_value = {
            'symbol': 'BTCUSDT',
            'last_price': 50000.0,
            'volume_24h': 1000.0,
            'timestamp': timestamp.timestamp()
        }
        self.mock_collector.get_klines.return_value = pd.DataFrame({
            'timestamp': [timestamp],
            'open': ['49000'],
            'high': ['51000'],
            'low': ['48000'],
            'close': ['50000'],
            'volume': ['100']
        })
        self.mock_collector.get_order_book.return_value = {
            'lastUpdateId': 1234567,
            'bids': [['49999', '1.0']],
            'asks': [['50001', '1.0']]
        }
        self.mock_collector.get_recent_trades.return_value = [{
            'id': 12345,
            'price': '50000',
            'qty': '1.0',
            'time': int(timestamp.timestamp() * 1000),
            'isBuyerMaker': True
        }]
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertTrue(result)
        self.mock_collector.get_ticker.assert_called_once_with(symbol)
        self.mock_collector.get_klines.assert_called_once_with(symbol, interval='1m', limit=100)
        self.mock_collector.get_order_book.assert_called_once_with(symbol, limit=100)
        self.mock_collector.get_recent_trades.assert_called_once_with(symbol, limit=50)
        
        # Vérification de la sauvegarde des données
        self.mock_db.store_market_data.assert_called_once()
        saved_data = self.mock_db.store_market_data.call_args[0][0]
        self.assertEqual(saved_data['symbol'], symbol)
        self.assertIn('timestamp', saved_data)
        self.assertIn('ticker', saved_data)
        self.assertIn('klines', saved_data)
        self.assertIn('orderbook', saved_data)
        self.assertIn('trades', saved_data)
        self.assertEqual(saved_data['exchange'], 'bybit')
        self.assertEqual(self.market_updater.error_counts[symbol], 0)

    def test_update_market_data_failure(self):
        """Test de la gestion des erreurs lors de la mise à jour"""
        symbol = 'BTCUSDT'
        
        # Configuration du mock pour lever une exception
        self.mock_collector.get_ticker.side_effect = Exception("API Error")
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertFalse(result)
        self.assertEqual(self.market_updater.error_counts[symbol], 1)
        self.mock_db.store_market_data.assert_not_called()

    def test_run_and_stop(self):
        """Test du démarrage et de l'arrêt du service"""
        # Configuration des mocks avec des données valides pour tous les symboles
        timestamp = datetime.now()
        for symbol in self.symbols:
            self.mock_collector.get_ticker.return_value = {
                'symbol': symbol,
                'last_price': 50000.0,
                'volume_24h': 1000.0,
                'timestamp': timestamp.timestamp()
            }
            self.mock_collector.get_klines.return_value = pd.DataFrame({
                'timestamp': [timestamp],
                'open': ['49000'],
                'high': ['51000'],
                'low': ['48000'],
                'close': ['50000'],
                'volume': ['100']
            })
            self.mock_collector.get_order_book.return_value = {
                'lastUpdateId': 1234567,
                'bids': [['49999', '1.0']],
                'asks': [['50001', '1.0']]
            }
            self.mock_collector.get_recent_trades.return_value = [{
                'id': 12345,
                'price': '50000',
                'qty': '1.0',
                'time': int(timestamp.timestamp() * 1000),
                'isBuyerMaker': True
            }]
        
        # Réduction de l'intervalle pour le test
        self.market_updater.update_interval = 0.1
        
        # Démarrage du service dans un thread séparé
        import threading
        update_thread = threading.Thread(target=self.market_updater.run)
        update_thread.daemon = True
        update_thread.start()
        
        # Attente pour quelques cycles de mise à jour
        # Attendre suffisamment longtemps pour que tous les symboles soient traités
        # Temps d'attente = nombre de symboles * intervalle de mise à jour * 2 (pour être sûr)
        wait_time = len(self.symbols) * self.market_updater.update_interval * 2
        time.sleep(wait_time)
        
        # Arrêt du service
        self.market_updater.stop()
        
        # Attente que le thread se termine
        update_thread.join(timeout=2)
        
        # Vérifications
        self.assertTrue(self.mock_collector.get_ticker.called)
        self.assertTrue(self.mock_collector.get_klines.called)
        self.assertTrue(self.mock_collector.get_order_book.called)
        self.assertTrue(self.mock_collector.get_recent_trades.called)
        self.assertTrue(self.mock_db.store_market_data.called)
        self.assertTrue(self.market_updater.stop_event.is_set())
        self.assertTrue(self.market_updater.shutdown_complete.is_set())
        self.assertFalse(update_thread.is_alive())

    def test_api_health_check_failure(self):
        """Test de la gestion d'une API non disponible"""
        symbol = 'BTCUSDT'
        
        # Configuration du mock pour simuler une API non disponible
        self.mock_monitor.check_api_health.return_value = {"status": "ERROR"}
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertFalse(result)
        self.assertEqual(self.market_updater.error_counts[symbol], 1)
        self.mock_collector.get_ticker.assert_not_called()
        self.mock_db.store_market_data.assert_not_called()

if __name__ == '__main__':
    unittest.main()
