import threading
import time
import os
import fcntl
from typing import Optional
from src.data_collector.market_data import MarketDataCollector
from src.monitoring.api_monitor import APIMonitor
from src.monitoring.run_monitoring import MonitoringService
from src.services.market_updater import MarketUpdater
from src.database.mongodb_manager import MongoDBManager
from config.config import BYBIT_API_KEY, BYBIT_API_SECRET
import logging
from datetime import datetime
import pytz as tz
import atexit
import uuid
import traceback

class TradingBot:
    _instance = None
    _lock = threading.Lock()
    _lock_file = "/tmp/trading_bot.lock"
    _lock_fd = None
    _instance_id = None
    
    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(TradingBot, cls).__new__(cls)
                cls._instance_id = str(uuid.uuid4())[:8]  # Identifiant unique pour chaque instance
                logging.getLogger('trading_bot').info(f"Création d'une nouvelle instance de TradingBot (ID: {cls._instance_id})")
            else:
                logging.getLogger('trading_bot').warning(
                    f"Tentative de création d'une nouvelle instance alors qu'une instance existe déjà (ID existant: {cls._instance_id})\n"
                    f"Stack trace:\n{traceback.format_stack()}"
                )
        return cls._instance

    def __init__(self, symbols=None, db=None):
        with self._lock:
            if hasattr(self, '_initialized') and self._initialized:
                logging.getLogger('trading_bot').debug(f"Réutilisation de l'instance existante (ID: {self._instance_id})")
                return
            
            # Configuration du logging avant tout
            self.setup_logging()
            self.logger.info(f"Initialisation d'une nouvelle instance de TradingBot (ID: {self._instance_id})")
            
            # Vérifier le fichier de verrouillage
            try:
                # Ouvrir le fichier en mode écriture
                self._lock_fd = open(self._lock_file, 'w')
                
                # Tenter d'acquérir le verrou
                fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                
                # Écrire les informations de l'instance dans le fichier
                instance_info = {
                    'pid': os.getpid(),
                    'instance_id': self._instance_id,
                    'start_time': datetime.now().isoformat()
                }
                self._lock_fd.write(str(instance_info))
                self._lock_fd.flush()
                
            except (IOError, OSError):
                if hasattr(self, '_lock_fd') and self._lock_fd:
                    self._lock_fd.close()
                self.logger.error(f"Impossible de créer une nouvelle instance - Une autre instance est déjà en cours d'exécution")
                raise RuntimeError("Une autre instance du bot est déjà en cours d'exécution")
            
            # Enregistrer la fonction de nettoyage
            atexit.register(self._cleanup)
            
            # Initialisation des attributs
            self.symbols = symbols or ["BTCUSDT"]
            self.db = db if db is not None else MongoDBManager()
            self._initialized = True
            
            self.logger.info("Vérification des clés API Bybit...")
            
            # Vérification des clés API
            if not BYBIT_API_KEY or not BYBIT_API_SECRET:
                self.logger.error("Les clés API Bybit ne sont pas configurées dans le fichier .env")
                raise ValueError("Les clés API Bybit sont requises. Veuillez configurer le fichier .env")
            
            self.logger.info("Vérification des clés API Bybit...")
            
            # Initialisation des composants
            self._init_components()
            
            self.logger.info("Bot de trading initialisé")
            
            # État du bot
            self.is_running = False
            self.monitoring_thread: Optional[threading.Thread] = None
            self.trading_thread: Optional[threading.Thread] = None

    def _init_components(self):
        """Initialise les composants du bot"""
        try:
            # Vérifier si les composants sont déjà initialisés
            if hasattr(self, 'market_data') and hasattr(self, 'monitoring_service') and hasattr(self, 'data_updater'):
                self.logger.debug(f"Les composants sont déjà initialisés pour l'instance {self._instance_id}")
                return

            self.logger.debug(f"Initialisation des composants pour l'instance {self._instance_id}")
            
            # Initialiser les composants une seule fois
            self.market_data = MarketDataCollector(BYBIT_API_KEY, BYBIT_API_SECRET)
            self.monitoring_service = MonitoringService(check_interval=60)
            self.data_updater = MarketUpdater(
                symbols=self.symbols,
                db=self.db,
                instance_id=self._instance_id  # Passer l'ID d'instance aux composants
            )
            
            self.logger.debug(f"Composants initialisés avec succès pour l'instance {self._instance_id}")
        except Exception as e:
            self.logger.error(f"Erreur lors de l'initialisation des composants: {str(e)}")
            raise

    def _cleanup(self):
        """Nettoie les ressources lors de la fermeture"""
        if hasattr(self, '_lock_fd') and self._lock_fd:
            try:
                # Vérifier si le fichier est toujours ouvert avant de tenter de le déverrouiller
                if not self._lock_fd.closed:
                    fcntl.flock(self._lock_fd.fileno(), fcntl.LOCK_UN)
                    self._lock_fd.close()
                
                # Supprimer le fichier de verrouillage s'il existe encore
                if os.path.exists(self._lock_file):
                    os.remove(self._lock_file)
            except (IOError, OSError, ValueError):
                pass
            finally:
                self._lock_fd = None
        
        if hasattr(self, 'db') and self.db:
            try:
                self.db.client.close()
            except:
                pass

    def __del__(self):
        """Destructeur de la classe"""
        try:
            self._cleanup()
        except:
            pass

    def setup_logging(self):
        """Configure le système de logging pour le bot"""
        # Créer le logger s'il n'existe pas déjà
        self.logger = logging.getLogger('trading_bot')
        
        # Si le logger a déjà des handlers, ne pas en ajouter d'autres
        if self.logger.handlers:
            return
            
        self.logger.setLevel(logging.INFO)
        
        # Configuration du format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Handler pour la console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        
        # Handler pour le fichier
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(
            os.path.join(log_dir, f"trading_bot_{self._instance_id}.log")
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        
        # Empêcher la propagation aux loggers parents
        self.logger.propagate = False

    def log_trading_decision(self, symbol: str, decision: str, indicators: dict):
        """Log détaillé des décisions de trading avec leur justification"""
        
        # Vérifier si les indicateurs sont dans le nouveau format ou l'ancien format
        if 'indicators' in indicators:
            # Ancien format
            ind = indicators['indicators']
            current_price = indicators.get('current_price')
        else:
            # Nouveau format
            ind = indicators
            current_price = None
        
        # Extraire les indicateurs
        rsi = ind.get('RSI')
        macd = ind.get('MACD')
        macd_signal = ind.get('Signal') or ind.get('MACD_Signal')
        bb_upper = ind.get('BB_Upper')
        bb_lower = ind.get('BB_Lower')
        
        # Construire le message de log
        message = f"\nDécision de Trading pour {symbol}:\n"
        message += f"{'='*50}\n"
        
        if current_price:
            message += f"Prix actuel: {current_price:.2f}\n"
        
        # Ajouter les indicateurs disponibles
        if rsi is not None:
            message += f"RSI: {rsi:.2f}"
            if rsi > 70:
                message += " (zone de surachat)"
            elif rsi < 30:
                message += " (zone de survente)"
            message += "\n"
            
        if macd is not None:
            message += f"MACD: {macd:.2f}\n"
        if macd_signal is not None:
            message += f"Signal MACD: {macd_signal:.2f}\n"
            
        if bb_upper is not None and bb_lower is not None:
            message += f"Bandes de Bollinger: {bb_lower:.2f} - {bb_upper:.2f}\n"
            
        message += f"\nDécision Finale: {decision}\n"
        message += "="*50
        
        # Logger le message
        self.logger.info(message)

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
                                        # Convert Unix timestamp to timezone-aware datetime if needed
                                        timestamp = current_data.get('timestamp')
                                        if isinstance(timestamp, (int, float)):
                                            timestamp = datetime.fromtimestamp(timestamp, tz=tz.UTC)
                                        else:
                                            timestamp = datetime.now(tz=tz.UTC)
                                            
                                        market_data = {
                                            'symbol': symbol,
                                            'data': current_data,
                                            'timestamp': timestamp
                                        }
                                        self.db.store_market_data(market_data)
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

    def _process_symbol(self, symbol: str):
        """Traite les données de marché pour un symbole donné"""
        try:
            # Récupérer les dernières données
            if hasattr(self, 'data_updater'):
                # Vérifier si une mise à jour est nécessaire
                current_time = time.time()
                last_update = self.data_updater.last_update.get(symbol, 0)
                
                if current_time - last_update >= self.data_updater.update_interval:
                    success = self.data_updater.update_market_data(symbol)
                    if success:
                        self.logger.debug(f"Données mises à jour pour {symbol}")
                    else:
                        self.logger.warning(f"Échec de la mise à jour des données pour {symbol}")
                else:
                    self.logger.debug(f"Mise à jour différée pour {symbol} - dernière mise à jour trop récente")
            else:
                self.logger.warning(f"data_updater non initialisé pour {symbol}")
        except Exception as e:
            self.logger.error(f"Erreur lors du traitement des données pour {symbol}: {str(e)}")
            raise

    def start(self):
        """Démarre le bot (monitoring + trading + mise à jour des données)"""
        if self.is_running:
            self.logger.warning(f"Le bot (ID: {self._instance_id}) est déjà en cours d'exécution")
            return

        self.logger.info(f"Démarrage du bot (ID: {self._instance_id})...")
        self.is_running = True

        try:
            # Vérifier la connexion à MongoDB
            try:
                self.db.client.admin.command('ping')
            except Exception as e:
                self.logger.error(f"Impossible de se connecter à MongoDB: {str(e)}")
                self.is_running = False
                return
            
            # Démarrer le service de mise à jour des données
            if hasattr(self, 'data_updater'):
                self.data_updater.start()

            # Démarrer le service de monitoring
            if hasattr(self, 'monitoring_service'):
                self.monitoring_service.start()

            # Démarrer la récupération des données
            for symbol in self.symbols:
                self.logger.info(f"Tentative de récupération des données pour {symbol}")
                self._process_symbol(symbol)

        except Exception as e:
            self.logger.error(f"Erreur lors du démarrage du bot (ID: {self._instance_id}): {str(e)}")
            self.stop()
            raise

    def stop(self):
        """Arrête le bot et ses services"""
        if not self.is_running:
            self.logger.warning(f"Le bot (ID: {self._instance_id}) n'est pas en cours d'exécution")
            return

        self.logger.info(f"Arrêt du bot (ID: {self._instance_id})...")
        
        try:
            # Arrêter les services dans l'ordre inverse du démarrage
            if hasattr(self, 'monitoring_service'):
                self.monitoring_service.stop()
            
            if hasattr(self, 'data_updater'):
                self.data_updater.stop()

            self.is_running = False
            self.logger.info(f"Bot (ID: {self._instance_id}) arrêté avec succès")
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'arrêt du bot (ID: {self._instance_id}): {str(e)}")
            raise

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
