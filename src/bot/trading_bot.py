import threading
import time
import os
import fcntl
from typing import Optional
from src.data_collector.market_data import MarketDataCollector
from src.data_collector.technical_indicators import TechnicalAnalysis
from src.data_collector.advanced_technical_indicators import AdvancedTechnicalAnalysis
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
import pandas as pd

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
            if hasattr(self, 'market_data') and hasattr(self, 'monitoring_service') and hasattr(self, 'data_updater'):
                self.logger.debug(f"Les composants sont déjà initialisés pour l'instance {self._instance_id}")
                return

            self.logger.debug(f"Initialisation des composants pour l'instance {self._instance_id}")
            
            # Initialiser les composants une seule fois
            self.market_data = MarketDataCollector(BYBIT_API_KEY, BYBIT_API_SECRET)
            self.monitoring_service = MonitoringService(check_interval=10)  # Réduit à 10 secondes
            self.data_updater = MarketUpdater(
                symbols=self.symbols,
                db=self.db,
                instance_id=self._instance_id
            )
            
            # Initialisation des analyseurs techniques
            self.technical_analyzer = TechnicalAnalysis()
            self.advanced_analyzer = AdvancedTechnicalAnalysis()
            
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

                # Vérification de la latence API
                if monitoring_metrics.get('average_latency', 0) > 1000:  # Plus de 1 seconde
                    self.logger.warning("Latence API élevée, ajustement des intervalles")
                    time.sleep(30)
                    continue

                for symbol in self.symbols:
                    try:
                        # Vérifier si une mise à jour est nécessaire via le MarketUpdater
                        self.data_updater.update_market_data(symbol)
                        
                        # Récupérer les données mises à jour
                        market_data = self._get_market_data(symbol)
                        if not market_data:
                            continue

                        # Préparation et validation des données
                        df = self._prepare_market_data(market_data)
                        if df is None or df.empty:
                            self.logger.warning(f"Données insuffisantes pour l'analyse de {symbol}")
                            continue
                            
                        # Calcul des indicateurs avec gestion des erreurs
                        try:
                            indicators = self.technical_analyzer.calculate_all(df)
                            signals = self.technical_analyzer.get_signals(df)
                            
                            advanced_indicators = self.advanced_analyzer.calculate_all_advanced(df)
                            advanced_signals = self.advanced_analyzer.get_advanced_signals(df)
                            
                            # Stocker les indicateurs dans MongoDB
                            self.db.store_indicators(symbol, {
                                'basic_indicators': indicators,
                                'advanced_indicators': advanced_indicators,
                                'timestamp': datetime.now(tz=tz.UTC)
                            })
                            
                        except Exception as e:
                            self.logger.error(f"Erreur lors du calcul des indicateurs pour {symbol}: {str(e)}")
                            continue
                            
                        # Analyse et prise de décision
                        decision = self._analyze_trading_signals(
                            symbol,
                            {**indicators, 'current_price': self._get_current_price(market_data)},
                            signals
                        )
                        
                        # Log détaillé de l'analyse
                        self.log_trading_decision(symbol, str(decision), {
                            'basic_indicators': indicators,
                            'advanced_indicators': advanced_indicators,
                            'basic_signals': signals,
                            'advanced_signals': advanced_signals,
                            'monitoring_metrics': monitoring_metrics,
                            'current_price': self._get_current_price(market_data)
                        })
                        
                        # Pause adaptative basée sur la latence API
                        sleep_time = min(
                            max(monitoring_metrics.get('average_latency', 100) / 1000, 1),
                            10
                        )
                        time.sleep(sleep_time)
                        
                    except Exception as symbol_error:
                        self.logger.error(f"Erreur lors du traitement de {symbol}: {str(symbol_error)}")
                        continue

                consecutive_errors = 0
                
            except Exception as e:
                consecutive_errors += 1
                self.logger.error(f"Erreur dans la boucle de trading: {str(e)}")
                wait_time = min(30 * (2 ** consecutive_errors), 300)
                self.logger.warning(f"Attente de {wait_time} secondes avant la prochaine tentative")
                
                if consecutive_errors >= max_consecutive_errors:
                    self.logger.critical(f"Arrêt du trading après {consecutive_errors} erreurs consécutives")
                    self.is_running = False
                    break
                
                time.sleep(wait_time)

    def _get_market_data(self, symbol: str) -> dict:
        """Récupère et valide les données de marché pour un symbole"""
        try:
            market_data = self.db.get_latest_market_data(symbol)
            
            if not market_data:
                self.logger.info(f"Pas de données en base pour {symbol}, récupération via API")
                current_data = self.market_data.get_current_price(symbol)
                if not current_data or 'price' not in current_data:
                    self.logger.warning(f"Données non disponibles pour {symbol}")
                    return None
                
                market_data = {
                    'symbol': symbol,
                    'data': current_data,
                    'timestamp': datetime.now(tz=tz.UTC)
                }
                self.db.store_market_data(market_data)
            
            return market_data
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des données pour {symbol}: {str(e)}")
            return None

    def _prepare_market_data(self, market_data: dict) -> pd.DataFrame:
        """Prépare les données de marché pour l'analyse technique"""
        try:
            if 'data' in market_data:
                data = market_data['data']
                if isinstance(data, dict):
                    # Créer un DataFrame avec les données minimales requises
                    df = pd.DataFrame([{
                        'timestamp': market_data.get('timestamp', datetime.now(tz=tz.UTC)),
                        'open': float(data.get('open', data.get('price', 0))),
                        'high': float(data.get('high', data.get('price', 0))),
                        'low': float(data.get('low', data.get('price', 0))),
                        'close': float(data.get('price', 0)),
                        'volume': float(data.get('volume', 0))
                    }])
                    return df
            return None
        except Exception as e:
            self.logger.error(f"Erreur lors de la préparation des données: {str(e)}")
            return None

    def _analyze_trading_signals(self, symbol: str, indicators: dict, signals: dict) -> dict:
        """Analyse les signaux de trading et prend une décision"""
        decision = {
            'action': 'hold',
            'reason': [],
            'confidence': 0.0,
            'timestamp': datetime.now(tz=tz.UTC)
        }

        # Analyse des indicateurs de base
        self._analyze_basic_indicators(decision, indicators)
        
        # Analyse des indicateurs avancés
        df = self._prepare_market_data(self._get_market_data(symbol))
        if df is not None and not df.empty:
            advanced_indicators = self.advanced_analyzer.calculate_all_advanced(df)
            advanced_signals = self.advanced_analyzer.get_advanced_signals(df)
            self._analyze_advanced_indicators(decision, advanced_indicators, advanced_signals)
            
            # Ajouter les indicateurs avancés au log
            self.logger.info(f"Indicateurs avancés pour {symbol}: {advanced_indicators}")
            self.logger.info(f"Signaux avancés pour {symbol}: {advanced_signals}")

        # Prise de décision finale avec pondération
        self._make_final_decision(decision)
        
        return decision

    def _analyze_basic_indicators(self, decision: dict, indicators: dict):
        """Analyse les indicateurs techniques de base"""
        # Analyse RSI
        rsi = indicators.get('RSI', 50)
        if rsi < 30:
            decision['reason'].append(f"RSI en survente ({rsi:.2f})")
            decision['confidence'] += 0.2
        elif rsi > 70:
            decision['reason'].append(f"RSI en surachat ({rsi:.2f})")
            decision['confidence'] += 0.2

        # Analyse MACD
        macd = indicators.get('MACD', 0)
        macd_signal = indicators.get('MACD_Signal', 0)
        if macd > macd_signal:
            decision['reason'].append("Signal MACD haussier")
            decision['confidence'] += 0.2
        elif macd < macd_signal:
            decision['reason'].append("Signal MACD baissier")
            decision['confidence'] += 0.2

        # Bandes de Bollinger
        bb_lower = indicators.get('BB_Lower', 0)
        bb_upper = indicators.get('BB_Upper', 0)
        current_price = indicators.get('current_price', 0)
        
        if current_price:
            if current_price < bb_lower:
                decision['reason'].append("Prix sous la bande inférieure de Bollinger")
                decision['confidence'] += 0.2
            elif current_price > bb_upper:
                decision['reason'].append("Prix au-dessus de la bande supérieure de Bollinger")
                decision['confidence'] += 0.2

    def _analyze_advanced_indicators(self, decision: dict, advanced_indicators: dict, advanced_signals: dict):
        """Analyse les indicateurs techniques avancés"""
        # Analyse ADX
        adx = advanced_indicators.get('ADX', 0)
        di_plus = advanced_indicators.get('+DI', 0)
        di_minus = advanced_indicators.get('-DI', 0)
        
        if adx > 25:  # Tendance forte
            if di_plus > di_minus:
                decision['reason'].append(f"ADX indique une forte tendance haussière (ADX: {adx:.2f})")
                decision['confidence'] += 0.3
            else:
                decision['reason'].append(f"ADX indique une forte tendance baissière (ADX: {adx:.2f})")
                decision['confidence'] += 0.3

        # Analyse Ichimoku
        tenkan = advanced_indicators.get('Tenkan_sen')
        kijun = advanced_indicators.get('Kijun_sen')
        if tenkan and kijun:
            if tenkan > kijun:
                decision['reason'].append("Signal Ichimoku haussier")
                decision['confidence'] += 0.2
            elif tenkan < kijun:
                decision['reason'].append("Signal Ichimoku baissier")
                decision['confidence'] += 0.2

        # Analyse Stochastique
        stoch_k = advanced_indicators.get('%K')
        stoch_d = advanced_indicators.get('%D')
        if stoch_k and stoch_d:
            if stoch_k < 20 and stoch_d < 20:
                decision['reason'].append("Stochastique indique une survente")
                decision['confidence'] += 0.2
            elif stoch_k > 80 and stoch_d > 80:
                decision['reason'].append("Stochastique indique un surachat")
                decision['confidence'] += 0.2

        # Money Flow Index
        mfi = advanced_indicators.get('MFI')
        if mfi:
            if mfi < 20:
                decision['reason'].append(f"MFI indique une survente ({mfi:.2f})")
                decision['confidence'] += 0.2
            elif mfi > 80:
                decision['reason'].append(f"MFI indique un surachat ({mfi:.2f})")
                decision['confidence'] += 0.2

    def _make_final_decision(self, decision: dict):
        """Prend la décision finale basée sur tous les signaux"""
        # Normaliser la confiance entre 0 et 1
        decision['confidence'] = min(decision['confidence'], 1.0)
        
        # Analyser les raisons pour déterminer la direction
        bullish_signals = sum(1 for reason in decision['reason'] if any(word in reason.lower() for word in ['haussier', 'survente', 'sous la bande']))
        bearish_signals = sum(1 for reason in decision['reason'] if any(word in reason.lower() for word in ['baissier', 'surachat', 'au-dessus de la bande']))
        
        # Prendre une décision si la confiance est suffisante
        if decision['confidence'] >= 0.6:
            if bullish_signals > bearish_signals:
                decision['action'] = 'buy'
            elif bearish_signals > bullish_signals:
                decision['action'] = 'sell'
            # En cas d'égalité, maintenir la position actuelle (hold)

    def _get_current_price(self, market_data: dict) -> Optional[float]:
        """Extrait le prix actuel des données de marché"""
        try:
            if market_data and 'data' in market_data:
                data = market_data['data']
                if isinstance(data, dict):
                    return float(data.get('price', 0))
            return None
        except Exception as e:
            self.logger.error(f"Erreur lors de l'extraction du prix: {str(e)}")
            return None

    def start_trading(self):
        """Démarre la boucle de trading dans un thread séparé"""
        def run_trading():
            self.logger.info("Boucle de trading démarrée")
            self.trading_loop()
        
        self.trading_thread = threading.Thread(target=run_trading)
        self.trading_thread.daemon = True
        self.trading_thread.start()

    def _process_symbol(self, symbol: str):
        """Traite un symbole spécifique pour le trading"""
        try:
            # Récupérer les données
            market_data = self._get_market_data(symbol)
            if not market_data:
                self.logger.warning(f"Pas de données disponibles pour {symbol}")
                return

            # Préparer les données
            df = self._prepare_market_data(market_data)
            if df is None or df.empty:
                self.logger.warning(f"Données insuffisantes pour l'analyse de {symbol}")
                return

            # Calculer les indicateurs
            indicators = self.technical_analyzer.calculate_all(df)
            signals = self.technical_analyzer.get_signals(df)
            
            advanced_indicators = self.advanced_analyzer.calculate_all_advanced(df)
            advanced_signals = self.advanced_analyzer.get_advanced_signals(df)

            # Stocker les indicateurs
            self.db.store_indicators(symbol, {
                'basic_indicators': indicators,
                'advanced_indicators': advanced_indicators,
                'timestamp': datetime.now(tz=tz.UTC)
            })

            # Analyser et prendre une décision
            decision = self._analyze_trading_signals(
                symbol,
                {**indicators, 'current_price': self._get_current_price(market_data)},
                signals
            )

            # Logger la décision
            self.log_trading_decision(symbol, str(decision), {
                'basic_indicators': indicators,
                'advanced_indicators': advanced_indicators,
                'basic_signals': signals,
                'advanced_signals': advanced_signals,
                'current_price': self._get_current_price(market_data)
            })

        except Exception as e:
            self.logger.error(f"Erreur lors du traitement de {symbol}: {str(e)}")
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

            # Démarrer la boucle de trading dans un thread séparé
            self.trading_thread = threading.Thread(target=self.trading_loop)
            self.trading_thread.daemon = True
            self.trading_thread.start()

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
