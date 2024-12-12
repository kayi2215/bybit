import unittest
import time
from unittest.mock import Mock, patch
from src.bot.trading_bot import TradingBot
from src.database.mongodb_manager import MongoDBManager
from datetime import datetime

class TestTradingBotIntegration(unittest.TestCase):
    def setUp(self):
        """Initialisation avant chaque test"""
        self.symbols = ["BTCUSDT", "ETHUSDT"]
        self.db = MongoDBManager()
        self.bot = TradingBot(symbols=self.symbols, db=self.db)
        
        # Nettoyer les données de test précédentes
        self.cleanup_test_data()

    def tearDown(self):
        """Nettoyage après chaque test"""
        if hasattr(self, 'bot') and self.bot.is_running:
            self.bot.stop()
            time.sleep(1)  # Attendre que les threads se terminent
        self.cleanup_test_data()
        
        # Fermer la connexion MongoDB
        if hasattr(self, 'db'):
            self.db.close()

    def cleanup_test_data(self):
        """Nettoie les données de test dans MongoDB"""
        try:
            # Utiliser les méthodes de nettoyage appropriées
            self.db.market_data.delete_many({"test": True})
            self.db.indicators.delete_many({"test": True})
        except Exception as e:
            print(f"Erreur lors du nettoyage des données: {e}")

    def insert_test_market_data(self):
        """Insère des données de test dans MongoDB"""
        for symbol in self.symbols:
            market_data = {
                "symbol": symbol,
                "data": {
                    "price": 50000.0 if symbol == "BTCUSDT" else 2000.0,
                    "volume": 100.0,
                    "timestamp": datetime.now().timestamp()
                },
                "test": True
            }
            self.db.store_market_data(symbol, market_data)

            indicators = {
                "symbol": symbol,
                "indicators": {
                    "rsi": 65.5,
                    "macd": {
                        "value": 100.0,
                        "signal": 95.0
                    }
                },
                "test": True
            }
            self.db.store_indicators(symbol, indicators)

    def test_bot_initialization(self):
        """Teste l'initialisation correcte du bot"""
        self.assertIsNotNone(self.bot.market_data)
        self.assertIsNotNone(self.bot.monitoring_service)
        self.assertIsNotNone(self.bot.data_updater)
        self.assertIsNotNone(self.bot.db)
        self.assertEqual(self.bot.symbols, self.symbols)

    def test_bot_start_stop(self):
        """Teste le démarrage et l'arrêt du bot"""
        # Démarrer le bot
        self.bot.start()
        self.assertTrue(self.bot.is_running)
        self.assertIsNotNone(self.bot.monitoring_thread)
        self.assertIsNotNone(self.bot.trading_thread)
        
        # Attendre un peu pour que les services démarrent
        time.sleep(2)
        
        # Arrêter le bot
        self.bot.stop()
        self.assertFalse(self.bot.is_running)
        
        # Vérifier que les threads sont terminés
        time.sleep(1)
        self.assertFalse(self.bot.monitoring_thread.is_alive())
        self.assertFalse(self.bot.trading_thread.is_alive())

    def test_data_flow(self):
        """Teste le flux de données à travers le système"""
        # Insérer des données de test
        self.insert_test_market_data()
        
        # Vérifier que les données sont récupérables
        for symbol in self.symbols:
            market_data = self.db.get_latest_market_data(symbol)
            self.assertIsNotNone(market_data)
            if isinstance(market_data, list):
                self.assertTrue(len(market_data) > 0)
                market_data = market_data[0]
            self.assertIn('symbol', market_data)
            self.assertEqual(market_data['symbol'], symbol)
            
            indicators = self.db.get_latest_indicators(symbol)
            self.assertIsNotNone(indicators)
            if isinstance(indicators, list):
                self.assertTrue(len(indicators) > 0)
                indicators = indicators[0]
            self.assertIn('symbol', indicators)
            self.assertEqual(indicators['symbol'], symbol)

    @patch('src.services.market_updater.MarketUpdater.update_market_data')
    def test_market_data_updates(self, mock_update):
        """Teste les mises à jour des données de marché"""
        # Configurer le mock pour retourner True (succès)
        mock_update.return_value = True
        
        # Démarrer le bot
        self.bot.start()
        
        # Attendre que le bot démarre et commence à mettre à jour les données
        time.sleep(2)
        
        # Vérifier que la méthode de mise à jour est appelée au moins une fois
        self.assertTrue(mock_update.called)
        
        # Arrêter le bot
        self.bot.stop()

    def test_error_handling(self):
        """Teste la gestion des erreurs"""
        # Simuler une erreur dans la base de données
        with patch.object(self.db, 'get_latest_market_data', side_effect=Exception("Test error")):
            self.bot.start()
            time.sleep(2)  # Attendre que le bot traite l'erreur
            
            # Le bot devrait continuer à fonctionner malgré l'erreur
            self.assertTrue(self.bot.is_running)
            
            self.bot.stop()

if __name__ == '__main__':
    unittest.main()
