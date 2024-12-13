import unittest
from unittest.mock import Mock, patch, create_autospec
import time
from datetime import datetime
import os
import pandas as pd

from src.services.market_updater import MarketUpdater
from src.database.mongodb_manager import MongoDBManager
from src.data_collector.market_data import MarketDataCollector
from src.monitoring.api_monitor import APIMonitor

class TestMarketUpdater(unittest.TestCase):
    def setUp(self):
        """Configuration initiale des tests"""
        # Create mocks
        self.mock_db = Mock(spec=MongoDBManager)
        self.mock_collector = Mock(spec=MarketDataCollector)
        self.mock_monitor = Mock(spec=APIMonitor)
        
        # Configure default API monitor response
        self.mock_monitor.check_api_health.return_value = {"status": "OK"}
        
        # Create MarketUpdater instance with mocks
        self.market_updater = MarketUpdater(['BTCUSDT'], db=self.mock_db)  # Pass mock_db directly
        self.market_updater.collector = self.mock_collector
        self.market_updater.api_monitor = self.mock_monitor
        
        # Reduce intervals for faster tests
        self.market_updater.update_interval = 0.1  # 100ms instead of 10s
        self.market_updater.shutdown_timeout = 1  # 1s instead of 10s

    def tearDown(self):
        """Nettoyage après chaque test"""
        self.market_updater.stop()
        # Wait for shutdown with shorter timeout
        self.market_updater.shutdown_complete.wait(timeout=1)
        # Clear any remaining events
        self.market_updater.stop_event.clear()
        self.market_updater.shutdown_complete.clear()

    def test_init(self):
        """Test de l'initialisation du MarketUpdater"""
        self.assertEqual(self.market_updater.symbols, ['BTCUSDT'])
        self.assertEqual(self.market_updater.db, self.mock_db)
        self.assertEqual(self.market_updater.error_counts, {'BTCUSDT': 0})

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
        self.mock_collector.get_public_trade_history.return_value = [{
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
        self.mock_collector.get_public_trade_history.assert_called_once_with(symbol, limit=50)
        
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
        for symbol in ['BTCUSDT']:
            self.mock_collector.get_ticker.return_value = {
                'symbol': symbol,
                'last_price': 50000.0,
                'volume_24h': 1000.0,
                'timestamp': timestamp.timestamp()
            }
            
            self.mock_collector.get_klines.return_value = pd.DataFrame({
                'timestamp': [timestamp] * 100,
                'open': ['49000'] * 100,
                'high': ['51000'] * 100,
                'low': ['48000'] * 100,
                'close': ['50000'] * 100,
                'volume': ['100'] * 100
            })
            
            self.mock_collector.get_order_book.return_value = {
                'lastUpdateId': 1234567,
                'bids': [['49999', '1.0']],
                'asks': [['50001', '1.0']]
            }
            
            self.mock_collector.get_public_trade_history.return_value = [{
                'id': 12345,
                'price': '50000',
                'qty': '1.0',
                'time': int(timestamp.timestamp() * 1000),
                'isBuyerMaker': True
            }]
        
        # Démarrage du service
        self.market_updater.start()
        
        # Attente pour quelques cycles de mise à jour (réduit à 0.5 secondes)
        time.sleep(0.5)
        
        # Arrêt du service
        self.market_updater.stop()
        
        # Vérifications
        self.mock_db.store_market_data.assert_called()
        self.mock_db.store_indicators.assert_called()
        self.assertTrue(self.market_updater.stop_event.is_set())

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

    def test_technical_indicators_update_success(self):
        """Test de la mise à jour réussie des indicateurs techniques"""
        symbol = 'BTCUSDT'
        timestamp = datetime.now()
        
        # Configuration des mocks avec des données valides
        self.mock_collector.get_ticker.return_value = {
            'symbol': symbol,
            'last_price': 50000.0,
            'volume_24h': 1000.0,
            'timestamp': timestamp.timestamp()
        }
        
        # Création d'un DataFrame avec suffisamment de données pour les indicateurs
        klines_data = pd.DataFrame({
            'timestamp': [timestamp] * 100,
            'open': ['49000'] * 100,
            'high': ['51000'] * 100,
            'low': ['48000'] * 100,
            'close': ['50000'] * 100,
            'volume': ['100'] * 100
        })
        self.mock_collector.get_klines.return_value = klines_data
        
        self.mock_collector.get_order_book.return_value = {
            'lastUpdateId': 1234567,
            'bids': [['49999', '1.0']],
            'asks': [['50001', '1.0']]
        }
        
        self.mock_collector.get_public_trade_history.return_value = [{
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
        self.mock_db.store_indicators.assert_called_once()
        
        # Vérification des indicateurs techniques stockés
        stored_data = self.mock_db.store_indicators.call_args[0][0]
        self.assertEqual(stored_data['symbol'], symbol)
        self.assertIn('timestamp', stored_data)
        self.assertIn('indicators', stored_data)
        self.assertIn('signals', stored_data)
        self.assertIn('summary', stored_data)

    def test_technical_indicators_invalid_data(self):
        """Test de la gestion des données invalides pour les indicateurs techniques"""
        symbol = 'BTCUSDT'
        timestamp = datetime.now()
        
        # Configuration des mocks avec des données valides pour tout sauf klines
        self.mock_collector.get_ticker.return_value = {
            'symbol': symbol,
            'last_price': 50000.0,
            'volume_24h': 1000.0,
            'timestamp': timestamp.timestamp()
        }
        
        # Retourner des données invalides pour klines (pas un DataFrame)
        self.mock_collector.get_klines.return_value = {
            'error': 'Invalid data format'
        }
        
        self.mock_collector.get_order_book.return_value = {
            'lastUpdateId': 1234567,
            'bids': [['49999', '1.0']],
            'asks': [['50001', '1.0']]
        }
        
        self.mock_collector.get_public_trade_history.return_value = [{
            'id': 12345,
            'price': '50000',
            'qty': '1.0',
            'time': int(timestamp.timestamp() * 1000),
            'isBuyerMaker': True
        }]
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertTrue(result)  # La mise à jour doit réussir même si les indicateurs échouent
        self.mock_db.store_market_data.assert_called_once()  # Les données de marché sont toujours stockées
        self.mock_db.store_indicators.assert_not_called()  # Pas de stockage d'indicateurs

if __name__ == '__main__':
    unittest.main()
