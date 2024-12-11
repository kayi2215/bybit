import threading
import time
from typing import Optional
from src.data_collector.market_data import MarketDataCollector
from src.monitoring.api_monitor import APIMonitor
from src.monitoring.run_monitoring import MonitoringService
from config.config import BINANCE_API_KEY, BINANCE_API_SECRET
import logging
from datetime import datetime

class TradingBot:
    def __init__(self):
        # Configuration du logging
        self.setup_logging()
        
        # Initialisation des composants
        self.market_data = MarketDataCollector(BINANCE_API_KEY, BINANCE_API_SECRET)
        self.monitoring_service = MonitoringService(check_interval=60)
        
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
        self.monitoring_thread.daemon = True  # Le thread s'arrêtera quand le programme principal s'arrête
        self.monitoring_thread.start()

    def trading_loop(self):
        """Boucle principale de trading"""
        while self.is_running:
            try:
                # Récupération des données de marché
                market_analysis = self.market_data.get_market_analysis('BTCUSDT')
                
                # Log des informations importantes
                self.logger.info(f"Prix actuel: {market_analysis['current_price']['price']} USDT")
                self.logger.info(f"Analyse technique: {market_analysis['technical_analysis']['summary']}")
                
                # Vérification de la santé de l'API via le monitoring
                monitoring_metrics = self.monitoring_service.monitor.get_metrics_summary()
                if monitoring_metrics.get('error_rate', 0) > 0.1:  # Plus de 10% d'erreurs
                    self.logger.warning("Taux d'erreur API élevé, trading en pause")
                    time.sleep(60)  # Attendre 1 minute avant de réessayer
                    continue
                
                # Logique de trading ici...
                # TODO: Implémenter votre stratégie de trading
                
                # Petite pause pour éviter de surcharger l'API
                time.sleep(10)
                
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle de trading: {str(e)}")
                time.sleep(30)  # Attendre avant de réessayer

    def start_trading(self):
        """Démarre la boucle de trading dans un thread séparé"""
        def run_trading():
            self.logger.info("Boucle de trading démarrée")
            self.trading_loop()
        
        self.trading_thread = threading.Thread(target=run_trading)
        self.trading_thread.daemon = True
        self.trading_thread.start()

    def start(self):
        """Démarre le bot (monitoring + trading)"""
        self.logger.info("Démarrage du bot...")
        self.is_running = True
        
        # Démarrer le monitoring
        self.start_monitoring()
        
        # Démarrer le trading
        self.start_trading()
        
        self.logger.info("Bot démarré avec succès")
        
        try:
            # Maintenir le programme en vie
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        """Arrête le bot proprement"""
        self.logger.info("Arrêt du bot...")
        self.is_running = False
        
        # Arrêter le service de monitoring
        self.monitoring_service.running = False
        
        # Attendre que les threads se terminent
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        if self.trading_thread:
            self.trading_thread.join(timeout=5)
        
        self.logger.info("Bot arrêté")

if __name__ == "__main__":
    # Créer et démarrer le bot
    bot = TradingBot()
    bot.start()
