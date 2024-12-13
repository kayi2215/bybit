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

if __name__ == '__main__':
    unittest.main()
