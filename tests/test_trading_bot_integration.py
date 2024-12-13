import unittest
from unittest.mock import MagicMock, patch
from src.bot.trading_bot import TradingBot
from src.database.mongodb_manager import MongoDBManager
from datetime import datetime
import pytz as tz
import pytest
import os
import logging
import mongomock
import time
import pandas as pd

class TestTradingBotIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Configuration initiale pour tous les tests"""
        # Supprimer le fichier de lock s'il existe
        if os.path.exists("/tmp/trading_bot.lock"):
            os.remove("/tmp/trading_bot.lock")
        
        # Réinitialiser le singleton
        TradingBot._instance = None
        if hasattr(TradingBot, '_lock_fd') and TradingBot._lock_fd:
            TradingBot._lock_fd.close()
            TradingBot._lock_fd = None
        
        # Nettoyer les handlers de logging
        logger = logging.getLogger('trading_bot')
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            if isinstance(handler, logging.FileHandler):
                handler.close()

    def setUp(self):
        """Configuration avant chaque test"""
        # Réinitialiser le singleton et le verrou
        TradingBot._instance = None
        
        # S'assurer que le fichier de verrouillage est supprimé
        try:
            if os.path.exists("/tmp/trading_bot.lock"):
                os.remove("/tmp/trading_bot.lock")
        except OSError:
            pass
            
        # Nettoyer les handlers de logging
        logger = logging.getLogger('trading_bot')
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            if isinstance(handler, logging.FileHandler):
                handler.close()
        
        # Mock MongoDB avec mongomock
        self.mock_client = mongomock.MongoClient()
        self.db = MongoDBManager()
        self.db.client = self.mock_client
        self.db.db = self.mock_client.db
        
        # Créer le bot avec la base mockée
        self.bot = TradingBot(symbols=["BTCUSDT"], db=self.db)

    def tearDown(self):
        """Nettoyage après chaque test"""
        # Arrêter et nettoyer le bot
        if hasattr(self, 'bot'):
            try:
                self.bot.stop()
            except:
                pass
            try:
                self.bot._cleanup()
            except:
                pass
            
        # Fermer la connexion MongoDB mockée
        if hasattr(self, 'mock_client'):
            try:
                self.mock_client.close()
            except:
                pass
            
        # Nettoyer le fichier de verrouillage
        try:
            if os.path.exists("/tmp/trading_bot.lock"):
                os.remove("/tmp/trading_bot.lock")
        except OSError:
            pass
            
        # Réinitialiser le singleton
        TradingBot._instance = None

    def test_singleton_pattern(self):
        """Test que le TradingBot utilise bien le pattern singleton"""
        # Réinitialiser le singleton
        TradingBot._instance = None
        if os.path.exists("/tmp/trading_bot.lock"):
            os.remove("/tmp/trading_bot.lock")
        
        # Créer deux instances
        bot1 = TradingBot(symbols=["BTCUSDT"], db=self.db)
        bot2 = TradingBot(symbols=["ETHUSDT"], db=self.db)
        
        # Vérifier que c'est la même instance
        self.assertIs(bot1, bot2)
        # Vérifier que les symboles sont ceux de la première instance
        self.assertEqual(bot1.symbols, ["BTCUSDT"])
        self.assertEqual(bot2.symbols, ["BTCUSDT"])
        
        # Nettoyer
        bot1._cleanup()

    def test_lock_file(self):
        """Test que le mécanisme de verrouillage fonctionne"""
        # S'assurer que le fichier de lock n'existe pas
        if os.path.exists("/tmp/trading_bot.lock"):
            os.remove("/tmp/trading_bot.lock")
            
        # Réinitialiser le singleton
        TradingBot._instance = None
        
        # Créer une première instance
        bot1 = TradingBot(db=self.db)
        
        # Réinitialiser le singleton pour forcer une nouvelle instance
        TradingBot._instance = None
        
        # Tenter de créer une deuxième instance devrait lever une exception
        with self.assertRaises(RuntimeError) as context:
            bot2 = TradingBot(db=self.db)
        
        self.assertIn("Une autre instance du bot est déjà en cours d'exécution", str(context.exception))
        
        # Nettoyer
        bot1._cleanup()

    def test_logging_setup(self):
        """Test de la configuration des logs"""
        # S'assurer que le singleton est réinitialisé
        TradingBot._instance = None
        
        # S'assurer que le fichier de verrouillage est supprimé
        if os.path.exists("/tmp/trading_bot.lock"):
            os.remove("/tmp/trading_bot.lock")
            
        # Nettoyer les handlers de logging
        logger = logging.getLogger('trading_bot')
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            if isinstance(handler, logging.FileHandler):
                handler.close()

        # Créer une instance du bot
        bot = TradingBot(db=self.db)
        self.bot = bot  # Pour le nettoyage dans tearDown
        
        # Vérifier que le logger est configuré correctement
        logger = logging.getLogger('trading_bot')
        self.assertTrue(logger.handlers)
        self.assertTrue(any(isinstance(h, logging.FileHandler) for h in logger.handlers))

    @patch('src.services.market_updater.MarketUpdater.update_market_data')
    def test_market_data_updates(self, mock_update):
        """Teste les mises à jour des données de marché"""
        mock_update.return_value = True
        
        # Configurer le mock pour simuler des données valides
        self.db.get_latest_market_data = MagicMock(return_value={
            'symbol': 'BTCUSDT',
            'timestamp': datetime.now(tz=tz.UTC),
            'data': {'ticker': {'last_price': '50000'}}
        })
        
        # Démarrer le bot
        self.bot.start()
        time.sleep(1)  # Attendre que le thread démarre
        
        # Vérifier que la mise à jour a été appelée
        self.assertTrue(self.bot.is_running)
        mock_update.assert_called()
        
        # Arrêter le bot
        self.bot.stop()

    def test_trading_decision_logging(self):
        """Test des logs détaillés des décisions de trading"""
        # S'assurer que le singleton est réinitialisé
        TradingBot._instance = None
        
        # S'assurer que le fichier de verrouillage est supprimé
        try:
            if os.path.exists("/tmp/trading_bot.lock"):
                os.remove("/tmp/trading_bot.lock")
        except OSError:
            pass
            
        # Nettoyer les handlers de logging
        logger = logging.getLogger('trading_bot')
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            if isinstance(handler, logging.FileHandler):
                handler.close()

        # Créer une instance du bot
        bot = TradingBot(db=self.db)
        self.bot = bot  # Pour le nettoyage dans tearDown
        
        # Test avec le nouveau format d'indicateurs
        with self.assertLogs(logger='trading_bot', level='INFO') as cm:
            bot.log_trading_decision(
                symbol="BTCUSDT",
                decision="BUY",
                indicators={
                    "RSI": 30.5,
                    "MACD": 0.5,
                    "Signal": 0.3
                }
            )
            
            # Vérifier le contenu des logs
            log_output = '\n'.join(cm.output)
            self.assertIn("BTCUSDT", log_output)
            self.assertIn("BUY", log_output)
            self.assertIn("RSI: 30.50", log_output)
            self.assertIn("MACD: 0.50", log_output)
            self.assertIn("Signal MACD: 0.30", log_output)
            
        # Test avec l'ancien format d'indicateurs
        with self.assertLogs(logger='trading_bot', level='INFO') as cm:
            bot.log_trading_decision(
                symbol="BTCUSDT",
                decision="SELL",
                indicators={
                    'indicators': {
                        'RSI': 75.5,
                        'MACD': -2.5,
                        'MACD_Signal': 1.2,
                        'BB_Upper': 50000.0,
                        'BB_Lower': 48000.0
                    },
                    'current_price': 49500.0
                }
            )
            
            # Vérifier le contenu des logs
            log_output = '\n'.join(cm.output)
            self.assertIn("BTCUSDT", log_output)
            self.assertIn("SELL", log_output)
            self.assertIn("RSI: 75.50", log_output)
            self.assertIn("MACD: -2.50", log_output)
            self.assertIn("Prix actuel: 49500.00", log_output)
            self.assertIn("Bandes de Bollinger: 48000.00 - 50000.00", log_output)

    @patch('src.data_collector.technical_indicators.TechnicalAnalysis.calculate_all')
    @patch('src.data_collector.advanced_technical_indicators.AdvancedTechnicalAnalysis.calculate_all_advanced')
    def test_technical_analysis_integration(self, mock_advanced, mock_basic):
        """Test l'intégration des analyses techniques basiques et avancées"""
        # Configurer les mocks
        mock_basic.return_value = {
            'RSI': 45,
            'MACD': 0.5,
            'MACD_Signal': 0.3,
            'BB_Upper': 52000,
            'BB_Lower': 48000
        }
        
        mock_advanced.return_value = {
            'ADX': 30,
            '+DI': 25,
            '-DI': 15,
            'Tenkan_sen': 51000,
            'Kijun_sen': 50000,
            '%K': 65,
            '%D': 60,
            'MFI': 55
        }
        
        # Simuler des données de marché
        market_data = {
            'symbol': 'BTCUSDT',
            'timestamp': datetime.now(tz=tz.UTC),
            'data': {'ticker': {'last_price': '50000'}}
        }
        self.bot._get_market_data = MagicMock(return_value=market_data)
        
        # Exécuter l'analyse
        df = self.bot._prepare_market_data(market_data)
        decision = self.bot._analyze_trading_signals('BTCUSDT', 
            {**mock_basic.return_value, 'current_price': 50000}, 
            {'trend': 'bullish'})
        
        # Vérifications
        self.assertIsNotNone(decision)
        self.assertIn('action', decision)
        self.assertIn('confidence', decision)
        self.assertIn('reason', decision)
        self.assertIn('timestamp', decision)

    @patch('src.monitoring.api_monitor.APIMonitor.get_metrics_summary')
    def test_monitoring_integration(self, mock_metrics):
        """Test l'intégration du système de monitoring"""
        # Configurer le mock des métriques
        mock_metrics.return_value = {
            'error_rate': 0.05,
            'average_latency': 500,
            'success_rate': 0.95,
            'total_requests': 100
        }
        
        # Démarrer le bot
        self.bot.start()
        time.sleep(1)  # Attendre le démarrage des services
        
        # Vérifier que le monitoring est actif
        self.assertTrue(hasattr(self.bot, 'monitoring_service'))
        self.assertTrue(self.bot.is_running)
        
        # Vérifier l'adaptation à la latence
        metrics = mock_metrics.return_value
        self.assertEqual(metrics['average_latency'], 500)
        
        # Arrêter le bot
        self.bot.stop()
        time.sleep(1)  # Attendre l'arrêt des services

    def test_mongodb_integration(self):
        """Test l'intégration avec MongoDB pour le stockage des indicateurs"""
        # Préparer des données de test
        test_indicators = {
            'basic_indicators': {
                'RSI': 45,
                'MACD': 0.5
            },
            'advanced_indicators': {
                'ADX': 30,
                'MFI': 55
            },
            'timestamp': datetime.now(tz=tz.UTC),
            'symbol': 'BTCUSDT'  # Ajout du symbole requis
        }
        
        # Créer la collection si elle n'existe pas
        if 'indicators' not in self.db.db.list_collection_names():
            self.db.db.create_collection('indicators')
        
        # Stocker les indicateurs
        self.db.db.indicators.insert_one(test_indicators)
        
        # Récupérer et vérifier les données
        stored_data = self.db.db.indicators.find_one({'symbol': 'BTCUSDT'})
        self.assertIsNotNone(stored_data)
        self.assertEqual(stored_data['basic_indicators']['RSI'], 45)
        self.assertEqual(stored_data['advanced_indicators']['ADX'], 30)

    @patch('src.services.market_updater.MarketUpdater.update_market_data')
    @patch('src.monitoring.api_monitor.APIMonitor.get_metrics_summary')
    def test_adaptive_sleep_behavior(self, mock_metrics, mock_update):
        """Test le comportement adaptatif du sleep basé sur la latence"""
        # Configurer les mocks
        mock_metrics.return_value = {'average_latency': 2000}  # 2 secondes de latence
        mock_update.return_value = True
        
        # Démarrer le bot
        self.bot.start()
        time.sleep(1)  # Attendre le démarrage des services
        
        # Vérifier que le sleep time est ajusté
        metrics = mock_metrics.return_value
        sleep_time = min(max(metrics['average_latency'] / 1000, 1), 10)
        self.assertEqual(sleep_time, 2)  # Devrait être 2 secondes
        
        # Arrêter le bot
        self.bot.stop()
        time.sleep(1)  # Attendre l'arrêt des services

    @patch('src.data_collector.technical_indicators.TechnicalAnalysis.calculate_all')
    def test_error_handling_and_recovery(self, mock_calculate):
        """Test la gestion des erreurs et la récupération"""
        # Simuler une série d'erreurs
        mock_calculate.side_effect = [Exception("Test error"), {'RSI': 45, 'MACD': 0.5}]
        
        # Configurer le mock pour les données de marché
        self.bot._get_market_data = MagicMock(return_value={
            'symbol': 'BTCUSDT',
            'timestamp': datetime.now(tz=tz.UTC),
            'data': {'ticker': {'last_price': '50000'}}
        })
        
        # Démarrer le bot
        self.bot.start()
        time.sleep(1)  # Attendre le démarrage des services
        
        # Vérifier que le bot continue de fonctionner
        self.assertTrue(self.bot.is_running)
        
        # Arrêter le bot
        self.bot.stop()
        time.sleep(1)  # Attendre l'arrêt des services

    @patch('src.data_collector.market_data.MarketDataCollector.get_klines')
    def test_data_processing_pipeline(self, mock_klines):
        """Test l'intégration complète du pipeline de traitement des données"""
        # Simuler des données de marché
        mock_klines.return_value = {
            'list': [
                [1640995200000, "47000.5", "47100.0", "46800.0", "47050.0", "100.5"],
                [1640995300000, "47050.0", "47200.0", "47000.0", "47150.0", "98.3"]
            ]
        }
        
        # Configurer le mock pour les données de marché
        self.bot._get_market_data = MagicMock(return_value={
            'symbol': 'BTCUSDT',
            'timestamp': datetime.now(tz=tz.UTC),
            'data': {'klines': mock_klines.return_value}
        })
        
        # Démarrer le bot
        self.bot.start()
        time.sleep(1)
        
        # Vérifier le pipeline complet
        df = self.bot._prepare_market_data(self.bot._get_market_data('BTCUSDT'))
        self.assertIsNotNone(df)
        self.assertFalse(df.empty)
        self.assertTrue('open' in df.columns)
        self.assertTrue('close' in df.columns)
        
        self.bot.stop()
        time.sleep(1)

    @patch('src.monitoring.api_monitor.APIMonitor.get_metrics_summary')
    @patch('src.data_collector.technical_indicators.TechnicalAnalysis.calculate_all')
    @patch('src.data_collector.advanced_technical_indicators.AdvancedTechnicalAnalysis.calculate_all_advanced')
    def test_decision_making_pipeline(self, mock_advanced, mock_basic, mock_metrics):
        """Test l'intégration du pipeline de prise de décision"""
        # Configurer les mocks
        mock_basic.return_value = {
            'RSI': 25,  # Condition de survente forte
            'MACD': 0.5,
            'MACD_Signal': 0.3,
            'BB_Upper': 52000,
            'BB_Lower': 48000
        }
        
        mock_advanced.return_value = {
            'ADX': 35,  # Tendance forte
            '+DI': 30,
            '-DI': 15,
            'Tenkan_sen': 51000,
            'Kijun_sen': 50000,
            '%K': 15,  # Condition de survente forte
            '%D': 20,
            'MFI': 20  # Condition de survente forte
        }
        
        mock_metrics.return_value = {
            'error_rate': 0.01,
            'average_latency': 100
        }
        
        # Configurer le mock pour les données de marché avec un prix bas
        market_data = {
            'symbol': 'BTCUSDT',
            'timestamp': datetime.now(tz=tz.UTC),
            'data': {
                'ticker': {'last_price': '47500'},  # Prix sous BB_Lower
                'klines': {
                    'list': [
                        [int(time.time()*1000), "47500", "47600", "47400", "47500", "100"]
                    ]
                }
            }
        }
        
        # Mock des méthodes du bot
        self.bot._get_market_data = MagicMock(return_value=market_data)
        self.bot._prepare_market_data = MagicMock(return_value=pd.DataFrame({
            'timestamp': [datetime.now(tz=tz.UTC)],
            'open': [47500],
            'high': [47600],
            'low': [47400],
            'close': [47500],
            'volume': [100]
        }))
        
        # Démarrer le bot
        self.bot.start()
        time.sleep(1)
        
        # Tester la prise de décision
        decision = self.bot._analyze_trading_signals(
            'BTCUSDT',
            {**mock_basic.return_value, 'current_price': 47500},
            {'trend': 'bullish'}
        )
        
        # Vérifications détaillées
        self.assertEqual(decision['action'], 'buy', "L'action devrait être 'buy' avec ces conditions")
        self.assertGreater(decision['confidence'], 0.6, "La confiance devrait être élevée")
        
        # Vérifier les raisons de la décision
        reasons = decision['reason']
        self.assertTrue(any('RSI' in reason and 'survente' in reason.lower() for reason in reasons),
                       "La décision devrait mentionner la survente du RSI")
        self.assertTrue(any('MACD' in reason and 'haussier' in reason.lower() for reason in reasons),
                       "La décision devrait mentionner le signal MACD haussier")
        
        # Arrêter le bot
        self.bot.stop()
        time.sleep(1)

    def test_component_lifecycle(self):
        """Test le cycle de vie complet des composants du bot"""
        # Vérifier l'état initial
        self.assertFalse(self.bot.is_running)
        self.assertIsNone(getattr(self.bot, 'trading_thread', None))
        
        # Démarrer le bot
        self.bot.start()
        time.sleep(1)
        
        # Vérifier le démarrage des composants
        self.assertTrue(self.bot.is_running)
        self.assertIsNotNone(self.bot.trading_thread)
        self.assertTrue(self.bot.trading_thread.is_alive())
        self.assertTrue(hasattr(self.bot, 'monitoring_service'))
        self.assertTrue(hasattr(self.bot, 'data_updater'))
        
        # Arrêter le bot
        self.bot.stop()
        time.sleep(1)
        
        # Vérifier l'arrêt des composants
        self.assertFalse(self.bot.is_running)
        self.assertFalse(self.bot.trading_thread.is_alive())

if __name__ == '__main__':
    unittest.main()
