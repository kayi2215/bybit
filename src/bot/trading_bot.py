import threading
import time
from typing import Optional
from src.data_collector.market_data import MarketDataCollector
from src.monitoring.api_monitor import APIMonitor
from src.monitoring.run_monitoring import MonitoringService
from src.services.market_updater import MarketDataUpdater
from src.database.mongodb_manager import MongoDBManager
from config.config import BINANCE_API_KEY, BINANCE_API_SECRET
import logging
from datetime import datetime

class TradingBot:
    def __init__(self, symbols=None):
        # Configuration du logging
        self.setup_logging()
        
        # Liste des symboles à trader
        self.symbols = symbols or ["BTCUSDT"]
        
        # Initialisation des composants
        self.market_data = MarketDataCollector(BINANCE_API_KEY, BINANCE_API_SECRET)
        self.monitoring_service = MonitoringService(check_interval=60)
        self.data_updater = MarketDataUpdater(
            symbols=self.symbols,
            update_interval=60  # Mise à jour toutes les 60 secondes
        )
        self.db = MongoDBManager()
        
        # État du bot
        self.is_running = False
        self.monitoring_thread: Optional[threading.Thread] = None
        self.trading_thread: Optional[threading.Thread] = None
        
        self.logger.info("Bot de trading initialisé")

    def setup_logging(self):
        """Configure le système de logging pour le bot"""
        self.logger = logging.getLogger('trading_bot')
        self.logger.setLevel(logging.INFO)
        
        # Handler pour le fichier
        fh = logging.FileHandler('logs/trading_bot.log')
        fh.setLevel(logging.INFO)
        
        # Handler pour la console
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def start_monitoring(self):
        """Démarre le service de monitoring dans un thread séparé"""
        def run_monitoring():
            self.logger.info("Service de monitoring démarré")
            self.monitoring_service.run()
        
        self.monitoring_thread = threading.Thread(target=run_monitoring)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()

    def trading_loop(self):
        """Boucle principale de trading"""
        while self.is_running:
            try:
                for symbol in self.symbols:
                    # Récupération des dernières données depuis MongoDB
                    market_data = self.db.get_latest_market_data(symbol)
                    if not market_data:
                        self.logger.warning(f"Pas de données récentes pour {symbol}")
                        continue

                    # Récupération des derniers indicateurs
                    indicators = self.db.get_latest_indicators(symbol)
                    
                    # Log des informations importantes
                    self.logger.info(f"Symbole: {symbol}")
                    self.logger.info(f"Prix actuel: {market_data['data']['price']} USDT")
                    if indicators:
                        self.logger.info(f"Indicateurs: {indicators['indicators']}")
                
                    # Vérification de la santé de l'API via le monitoring
                    monitoring_metrics = self.monitoring_service.monitor.get_metrics_summary()
                    if monitoring_metrics.get('error_rate', 0) > 0.1:  # Plus de 10% d'erreurs
                        self.logger.warning("Taux d'erreur API élevé, trading en pause")
                        time.sleep(60)
                        break
                    
                    # TODO: Implémenter la logique de trading basée sur les données et indicateurs
                
                # Petite pause entre les cycles
                time.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle de trading: {str(e)}")
                time.sleep(30)

    def start_trading(self):
        """Démarre la boucle de trading dans un thread séparé"""
        def run_trading():
            self.logger.info("Boucle de trading démarrée")
            self.trading_loop()
        
        self.trading_thread = threading.Thread(target=run_trading)
        self.trading_thread.daemon = True
        self.trading_thread.start()

    def start(self):
        """Démarre le bot (monitoring + trading + mise à jour des données)"""
        self.logger.info("Démarrage du bot...")
        self.is_running = True
        
        # Démarrer le service de mise à jour des données
        self.data_updater.start()
        self.logger.info("Service de mise à jour des données démarré")
        
        # Démarrer le monitoring
        self.start_monitoring()
        self.logger.info("Service de monitoring démarré")
        
        # Démarrer le trading
        self.start_trading()
        self.logger.info("Service de trading démarré")

    def stop(self):
        """Arrête tous les services du bot"""
        self.logger.info("Arrêt du bot...")
        self.is_running = False
        
        # Arrêt du service de mise à jour des données
        self.data_updater.stop()
        
        # Attendre que les threads se terminent
        if self.monitoring_thread:
            self.monitoring_thread.join()
        if self.trading_thread:
            self.trading_thread.join()
            
        self.logger.info("Bot arrêté avec succès")

if __name__ == "__main__":
    # Créer et démarrer le bot
    bot = TradingBot(symbols=["BTCUSDT", "ETHUSDT"])
    try:
        bot.start()
        # Maintenir le programme en vie
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        bot.stop()
