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
        # Création des mocks
        self.mock_collector = Mock()
        self.mock_db = create_autospec(MongoDBManager)  # Use create_autospec to properly mock MongoDBManager
        self.mock_technical_analysis = Mock()
        
        # Configuration du MarketUpdater avec les mocks
        self.market_updater = MarketUpdater(['BTCUSDT'], db=self.mock_db)  # Pass mock_db directly
        self.market_updater.collector = self.mock_collector
        self.market_updater.technical_analysis = self.mock_technical_analysis
        
        # Configuration du mock de l'API monitor
        self.mock_api_monitor = Mock()
        self.market_updater.api_monitor = self.mock_api_monitor
        self.mock_api_monitor.check_api_health.return_value = {"status": "OK"}
        
        # Reduce intervals for faster tests
        self.market_updater.update_interval = 0.1  # 100ms instead of 10s
        self.market_updater.shutdown_timeout = 1  # 1s instead of 10s

    def tearDown(self):
        """Nettoyage après chaque test"""
        if hasattr(self.market_updater, 'stop'):
            self.market_updater.stop()
        # Close any MongoDB connections if they exist
        if hasattr(self.market_updater.db, 'client'):
            self.market_updater.db.client.close()

    def test_init(self):
        """Test de l'initialisation du MarketUpdater"""
        self.assertEqual(self.market_updater.symbols, ['BTCUSDT'])
        self.assertEqual(self.market_updater.db, self.mock_db)
        self.assertEqual(self.market_updater.error_counts, {'BTCUSDT': 0})

    def test_update_market_data_success(self):
        """Test de la mise à jour réussie des données de marché"""
        symbol = "BTCUSDT"
        
        # Configuration des mocks avec le format correct des données
        self.mock_collector.get_ticker.return_value = {
            'symbol': symbol,
            'last_price': '50000',
            'volume_24h': '1000'
        }
        self.mock_collector.get_klines.return_value = pd.DataFrame({
            'timestamp': [1, 2, 3],
            'open': [100, 101, 102],
            'high': [103, 104, 105],
            'low': [98, 99, 100],
            'close': [101, 102, 103],
            'volume': [1000, 1100, 1200]
        })
        self.mock_collector.get_order_book.return_value = {
            'bids': [['49999', '1.0']],
            'asks': [['50001', '1.0']]
        }
        self.mock_collector.get_public_trade_history.return_value = [{
            'price': '50000',
            'qty': '1.0',
            'time': 1000000
        }]
        
        # Configuration du mock des indicateurs techniques
        self.mock_technical_analysis.get_summary.return_value = {
            'RSI': 65.0,
            'MACD': 0.5,
            'MA20': 102.0
        }
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertTrue(result)
        self.mock_collector.get_ticker.assert_called_once_with(symbol)
        self.mock_collector.get_klines.assert_called_once()
        self.mock_collector.get_order_book.assert_called_once()
        self.mock_collector.get_public_trade_history.assert_called_once()
        
        # Vérification de la sauvegarde des données
        self.mock_db.store_market_data.assert_called_once()
        saved_data = self.mock_db.store_market_data.call_args.kwargs['data']
        self.assertEqual(saved_data['symbol'], symbol)
        self.assertIn('timestamp', saved_data)
        self.assertIn('ticker', saved_data)
        self.assertIn('klines', saved_data)
        self.assertIn('orderbook', saved_data)
        self.assertIn('trades', saved_data)

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
        # Configuration des mocks pour une exécution réussie
        self.mock_collector.get_ticker.return_value = {
            'symbol': 'BTCUSDT',
            'last_price': '50000',
            'volume_24h': '1000'
        }
        self.mock_collector.get_klines.return_value = pd.DataFrame({
            'timestamp': [1, 2, 3],
            'open': [100, 101, 102],
            'high': [103, 104, 105],
            'low': [98, 99, 100],
            'close': [101, 102, 103],
            'volume': [1000, 1100, 1200]
        })
        self.mock_technical_analysis.get_summary.return_value = {
            'RSI': 65.0,
            'MACD': 0.5,
            'MA20': 102.0
        }
        
        # Démarrage du service dans un thread séparé
        self.market_updater.start()
        
        # Attente d'au moins une mise à jour
        time.sleep(0.2)
        
        # Arrêt du service
        self.market_updater.stop()
        
        # Attente de l'arrêt complet
        self.market_updater.shutdown_complete.wait(timeout=1)
        
        # Vérifications
        self.mock_db.store_market_data.assert_called()
        self.mock_db.store_indicators.assert_called()
        self.assertTrue(self.market_updater.stop_event.is_set())

    def test_api_health_check_failure(self):
        """Test de la gestion d'une API non disponible"""
        symbol = 'BTCUSDT'
        
        # Configuration du mock pour simuler une API non disponible
        self.mock_api_monitor.check_api_health.return_value = {"status": "ERROR"}
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertFalse(result)
        self.assertEqual(self.market_updater.error_counts[symbol], 1)
        self.mock_collector.get_ticker.assert_not_called()
        self.mock_db.store_market_data.assert_not_called()

    def test_technical_indicators_update_success(self):
        """Test de la mise à jour réussie des indicateurs techniques"""
        symbol = "BTCUSDT"
        timestamp = int(time.time() * 1000)
        
        # Configuration des mocks
        klines_data = pd.DataFrame({
            'timestamp': [timestamp - 200000, timestamp - 100000, timestamp],
            'open': [100, 101, 102],
            'high': [103, 104, 105],
            'low': [98, 99, 100],
            'close': [101, 102, 103],
            'volume': [1000, 1100, 1200]
        })
        
        technical_indicators = {
            'RSI': 65.0,
            'MACD': 0.5,
            'MA20': 102.0
        }
        
        self.mock_collector.get_klines.return_value = klines_data
        self.mock_technical_analysis.get_summary.return_value = technical_indicators
        
        # Exécution
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertTrue(result)
        self.mock_technical_analysis.get_summary.assert_called_once()
        self.mock_db.store_indicators.assert_called_once()
        
        # Vérification des données stockées
        stored_data = self.mock_db.store_indicators.call_args.kwargs
        self.assertEqual(stored_data['symbol'], symbol)
        self.assertEqual(stored_data['indicators'], technical_indicators)

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
