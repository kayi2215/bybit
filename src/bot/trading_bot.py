import threading
import time
from typing import Optional
from src.data_collector.market_data import MarketDataCollector
from src.monitoring.api_monitor import APIMonitor
from src.monitoring.run_monitoring import MonitoringService
from src.services.market_updater import MarketUpdater
from src.database.mongodb_manager import MongoDBManager
from config.config import BYBIT_API_KEY, BYBIT_API_SECRET
import logging
from datetime import datetime

class TradingBot:
    def __init__(self, symbols=None, db=None):
        # Configuration du logging
        self.setup_logging()
        
        # Vérification des clés API
        if not BYBIT_API_KEY or not BYBIT_API_SECRET:
            self.logger.error("Les clés API Bybit ne sont pas configurées dans le fichier .env")
            raise ValueError("Les clés API Bybit sont requises. Veuillez configurer le fichier .env")
        
        self.logger.info("Vérification des clés API Bybit...")
        
        # Liste des symboles à trader
        self.symbols = symbols or ["BTCUSDT"]
        
        # Initialisation de la base de données
        self.db = db if db is not None else MongoDBManager()
        
        # Initialisation des composants
        self.market_data = MarketDataCollector(BYBIT_API_KEY, BYBIT_API_SECRET)
        self.monitoring_service = MonitoringService(check_interval=60)
        self.data_updater = MarketUpdater(
            symbols=self.symbols,
            db=self.db
        )
        
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
        consecutive_errors = 0
        max_consecutive_errors = 3
        
        while self.is_running:
            try:
                # Vérification de la santé de l'API via le monitoring
                monitoring_metrics = self.monitoring_service.monitor.get_metrics_summary()
                if monitoring_metrics.get('error_rate', 0) > 0.1:  # Plus de 10% d'erreurs
                    self.logger.warning("Taux d'erreur API élevé, trading en pause")
                    time.sleep(60)
                    continue

                for symbol in self.symbols:
                    try:
                        self.logger.info(f"Tentative de récupération des données pour {symbol}")
                        # Récupération des dernières données depuis MongoDB
                        market_data = self.db.get_latest_market_data(symbol)
                        price = None
                        
                        if not market_data:
                            self.logger.info(f"Pas de données en base pour {symbol}, tentative de récupération directe via API")
                            try:
                                current_data = self.market_data.get_current_price(symbol)
                                self.logger.info(f"Données reçues de l'API pour {symbol}: {current_data}")
                                price = current_data.get('price')
                                if price:
                                    self.logger.info(f"Prix récupéré directement de l'API pour {symbol}: {price}")
                                    # Stocker les données dans MongoDB pour les prochaines fois
                                    try:
                                        self.db.store_market_data(symbol, current_data)
                                        self.logger.info(f"Données stockées en base pour {symbol}")
                                    except Exception as db_error:
                                        self.logger.error(f"Erreur lors du stockage des données pour {symbol}: {str(db_error)}")
                                else:
                                    self.logger.warning(f"Prix non disponible pour {symbol} dans la réponse API")
                            except Exception as e:
                                self.logger.error(f"Erreur lors de la récupération du prix pour {symbol}: {str(e)}")
                                self.logger.debug("Détails de l'erreur:", exc_info=True)
                                continue
                        else:
                            self.logger.info(f"Données trouvées en base pour {symbol}")
                            # Extraction du prix depuis les données MongoDB
                            if isinstance(market_data, dict):
                                if 'data' in market_data and isinstance(market_data['data'], dict):
                                    if 'ticker' in market_data['data']:
                                        price = market_data['data']['ticker'].get('price')
                                    else:
                                        price = market_data['data'].get('price')
                                else:
                                    price = market_data.get('price')
                            
                            if price:
                                self.logger.info(f"Prix extrait des données MongoDB: {price}")
                            else:
                                self.logger.warning(f"Structure de données inattendue: {market_data}")
                        
                        if price is None:
                            self.logger.warning(f"Prix non trouvé dans les données pour {symbol}")
                            continue

                        # Récupération des derniers indicateurs
                        indicators = self.db.get_latest_indicators(symbol)
                        
                        # Log des informations importantes
                        self.logger.info(f"Symbole: {symbol}")
                        
                        if price is not None:
                            self.logger.info(f"Prix actuel: {price} USDT")
                        else:
                            self.logger.warning(f"Prix non trouvé dans les données pour {symbol}")
                            continue

                        # Extraction des indicateurs selon le format
                        if indicators:
                            indicator_data = None
                            if isinstance(indicators, dict):
                                if 'indicators' in indicators:
                                    indicator_data = indicators['indicators']
                                else:
                                    indicator_data = {k: v for k, v in indicators.items() 
                                                    if k not in ['_id', 'symbol', 'timestamp']}
                            elif isinstance(indicators, list) and indicators:
                                if 'indicators' in indicators[0]:
                                    indicator_data = indicators[0]['indicators']
                                else:
                                    indicator_data = {k: v for k, v in indicators[0].items() 
                                                    if k not in ['_id', 'symbol', 'timestamp']}
                            
                            if indicator_data:
                                self.logger.info(f"Indicateurs: {indicator_data}")
                            else:
                                self.logger.warning(f"Indicateurs non trouvés pour {symbol}")
                    
                        # TODO: Implémenter la logique de trading basée sur les données et indicateurs
                    
                    except Exception as symbol_error:
                        self.logger.error(f"Erreur lors du traitement de {symbol}: {str(symbol_error)}")
                        continue
                
                # Réinitialiser le compteur d'erreurs après un cycle réussi
                consecutive_errors = 0
                
                # Petite pause entre les cycles
                time.sleep(10)
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"Erreur dans la boucle de trading: {str(e)}")
                
                # Augmenter le temps d'attente exponentiellement avec le nombre d'erreurs
                wait_time = min(30 * (2 ** consecutive_errors), 300)  # Max 5 minutes
                self.logger.warning(f"Attente de {wait_time} secondes avant la prochaine tentative")
                
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.critical(f"Arrêt du trading après {consecutive_errors} erreurs consécutives")
                    self.is_running = False
                    break
                
                time.sleep(wait_time)

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
        try:
            self.logger.info("Démarrage du bot...")
            self.is_running = True
            
            # Vérifier la connexion à MongoDB
            try:
                self.db.client.admin.command('ping')
            except Exception as e:
                self.logger.error(f"Impossible de se connecter à MongoDB: {str(e)}")
                self.is_running = False
                return
            
            # Démarrer le service de mise à jour des données
            self.data_updater_thread = threading.Thread(target=self.data_updater.run)
            self.data_updater_thread.daemon = True
            self.data_updater_thread.start()
            
            # Démarrer le service de monitoring
            self.monitoring_thread = threading.Thread(target=self.monitoring_service.run)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()
            
            # Démarrer le thread de trading
            self.trading_thread = threading.Thread(target=self.trading_loop)
            self.trading_thread.daemon = True
            self.trading_thread.start()
            
        except Exception as e:
            self.logger.error(f"Erreur lors du démarrage du bot: {str(e)}")
            self.is_running = False
            raise

    def stop(self):
        """Arrête le bot et ses services"""
        self.logger.info("Arrêt du bot...")
        self.is_running = False
        
        # Arrêt du thread de trading
        if self.trading_thread and self.trading_thread.is_alive():
            self.trading_thread.join(timeout=30)  # Attendre 30 secondes max
            if self.trading_thread.is_alive():
                self.logger.warning("Le thread de trading ne s'est pas arrêté proprement")
        
        # Arrêt du thread de monitoring
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_service.stop()  # Cette méthode attend maintenant la fin du service
            self.monitoring_thread.join(timeout=30)  # Attendre 30 secondes max
            if self.monitoring_thread.is_alive():
                self.logger.warning("Le thread de monitoring ne s'est pas arrêté proprement")
        
        # Arrêt du thread de mise à jour des données
        if hasattr(self, 'data_updater_thread') and self.data_updater_thread and self.data_updater_thread.is_alive():
            self.data_updater.stop()
            self.data_updater_thread.join(timeout=30)  # Attendre 30 secondes max
            if self.data_updater_thread.is_alive():
                self.logger.warning("Le thread de mise à jour des données ne s'est pas arrêté proprement")
        
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
