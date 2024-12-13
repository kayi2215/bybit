import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv
import pandas as pd
from queue import Queue, Empty

from src.database.mongodb_manager import MongoDBManager
from src.data_collector.market_data import MarketDataCollector
from src.monitoring.api_monitor import APIMonitor
from src.data_collector.technical_indicators import TechnicalAnalysis
from src.data_collector.advanced_technical_indicators import AdvancedTechnicalAnalysis

class MarketUpdater:
    def __init__(
        self,
        symbols: List[str],
        db: Optional[MongoDBManager] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        use_testnet: bool = False,
        shutdown_timeout: int = 5,
        instance_id: Optional[str] = None,
        cache_retention_hours: int = 24
    ):
        """
        Initialise le service de mise à jour des données de marché
        
        Args:
            symbols: Liste des paires de trading à surveiller
            db: Instance optionnelle de MongoDBManager
            api_key: Clé API Bybit
            api_secret: Secret API Bybit
            use_testnet: Utiliser le testnet Bybit
            shutdown_timeout: Délai d'arrêt en secondes
            instance_id: Identifiant unique de l'instance du bot
            cache_retention_hours: Durée de rétention du cache en heures
        """
        load_dotenv()
        
        self.symbols = symbols
        self.db = db or MongoDBManager(cache_retention_hours=cache_retention_hours)
        self.instance_id = instance_id
        self.stop_event = threading.Event()
        self.shutdown_complete = threading.Event()
        self.shutdown_timeout = shutdown_timeout
        self.shutdown_queue = Queue()
        self.update_thread = None
        self.last_update = {symbol: 0 for symbol in symbols}  # Timestamp de la dernière mise à jour
        
        # Configuration du logging et des paramètres
        self.logger = logging.getLogger(__name__)
        self.update_interval = 10  # Intervalle de mise à jour en secondes
        self.max_retries = 3  # Nombre maximum de tentatives en cas d'erreur
        
        # Configuration des clés API
        self.api_key = api_key or os.getenv('BYBIT_API_KEY')
        self.api_secret = api_secret or os.getenv('BYBIT_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Les clés API Bybit sont requises")
            
        # Initialisation des composants avec l'ID d'instance dans les logs
        self.logger.info(f"Initialisation du MarketUpdater pour l'instance {self.instance_id}")
        
        # Initialisation des composants
        self.collector = MarketDataCollector(
            api_key=self.api_key,
            api_secret=self.api_secret,
            use_testnet=use_testnet
        )
        self.api_monitor = APIMonitor()
        self.technical_analysis = TechnicalAnalysis()
        self.advanced_technical_analysis = AdvancedTechnicalAnalysis()
        
        # Dictionnaire pour suivre les erreurs par symbole
        self.error_counts: Dict[str, int] = {symbol: 0 for symbol in symbols}

    def _update_market_data(self, symbol: str) -> bool:
        """Met à jour les données de marché pour un symbole donné"""
        try:
            current_time = time.time()
            if current_time - self.last_update.get(symbol, 0) < self.update_interval:
                self.logger.debug(f"Mise à jour ignorée pour {symbol} - trop récente")
                return True

            if self.stop_event.is_set():
                return False

            # Vérifier la santé de l'API
            health_status = self.api_monitor.check_api_health()
            if not health_status or health_status.get('status') != 'OK':
                raise Exception("API Bybit is not healthy")

            if self.stop_event.is_set():
                return False

            try:
                # Récupérer l'analyse complète
                analysis = self.collector.get_complete_analysis(symbol)
            except Exception as e:
                self.logger.error(f"Erreur lors de l'analyse pour {symbol}: {str(e)}")
                # Fallback vers l'ancien système de collecte
                return self._update_market_data_legacy(symbol)

            # Préparer les données de base et le cache
            market_data = {
                'symbol': symbol,
                'timestamp': analysis['timestamp'],
                'basic_analysis': analysis['basic_analysis'],
                'cached_indicators': {
                    'last_update': time.time(),
                    'common': {
                        'ADX': analysis['advanced_analysis']['indicators'].get('ADX'),
                        'ATR': analysis['advanced_analysis']['indicators'].get('ATR')
                    }
                }
            }

            try:
                # Sauvegarder les données de marché et obtenir l'ID
                market_data_id = self.db.save_market_data(market_data)
            except Exception as e:
                self.logger.error(f"Erreur lors de la sauvegarde des données de marché pour {symbol}: {str(e)}")
                return False

            if self.stop_event.is_set():
                return False

            # Préparer et sauvegarder les indicateurs avancés
            advanced_data = {
                'symbol': symbol,
                'timestamp': analysis['timestamp'],
                'type': 'advanced',
                'data': {
                    'indicators': analysis['advanced_analysis']['indicators'],
                    'signals': analysis['advanced_analysis']['signals']
                }
            }

            try:
                self.db.save_advanced_indicators(market_data_id, advanced_data)
            except Exception as e:
                self.logger.error(f"Erreur lors de la sauvegarde des indicateurs avancés pour {symbol}: {str(e)}")
                # Ne pas échouer si les indicateurs avancés échouent
                pass

            # Mettre à jour le timestamp et réinitialiser les erreurs
            self.last_update[symbol] = current_time
            self.error_counts[symbol] = 0
            
            self.logger.info(f"Données mises à jour pour {symbol}")
            return True
            
        except Exception as e:
            self.error_counts[symbol] = self.error_counts.get(symbol, 0) + 1
            self.logger.error(f"Erreur lors de la mise à jour pour {symbol}: {str(e)}")
            self.api_monitor.record_error("market_update", str(e))
            return False

    def _update_market_data_legacy(self, symbol: str) -> bool:
        """Méthode de fallback utilisant l'ancien système de collecte"""
        try:
            if self.stop_event.is_set():
                return False

            # Récupération des données de base
            ticker_data = self.collector.get_ticker(symbol)
            klines_data = self.collector.get_klines(symbol, interval='1m', limit=100)
            orderbook_data = self.collector.get_order_book(symbol, limit=100)
            trades_data = self.collector.get_public_trade_history(symbol, limit=50)

            if self.stop_event.is_set():
                return False

            # Format compatible avec la nouvelle structure
            market_data = {
                'symbol': symbol,
                'timestamp': time.time(),
                'basic_analysis': {
                    'data': {
                        'ticker': ticker_data,
                        'klines': klines_data.to_dict('records') if isinstance(klines_data, pd.DataFrame) else klines_data,
                        'orderbook': orderbook_data,
                        'trades': trades_data,
                        'exchange': 'bybit'
                    }
                }
            }

            # Utiliser la nouvelle méthode de sauvegarde
            self.db.save_market_data(market_data)
            
            self.last_update[symbol] = time.time()
            self.error_counts[symbol] = 0
            
            return True

        except Exception as e:
            self.error_counts[symbol] = self.error_counts.get(symbol, 0) + 1
            self.logger.error(f"Erreur lors de la mise à jour legacy pour {symbol}: {str(e)}")
            return False

    def update_market_data(self, symbol: str) -> bool:
        """Met à jour les données de marché pour un symbole donné"""
        return self._update_market_data(symbol)

    def run(self):
        """Exécute la boucle principale de mise à jour des données"""
        self.logger.info(f"Démarrage de la boucle de mise à jour des données pour l'instance {self.instance_id}")
        
        while not self.stop_event.is_set():
            try:
                # Vérifier la demande d'arrêt
                try:
                    if self.shutdown_queue.get_nowait() == "shutdown":
                        break
                except Empty:
                    pass
                
                for symbol in self.symbols:
                    if self.stop_event.is_set():
                        break
                        
                    current_time = time.time()
                    # Vérifier si une mise à jour est nécessaire
                    if current_time - self.last_update.get(symbol, 0) >= self.update_interval:
                        success = self.update_market_data(symbol)
                        
                        if not success and self.error_counts[symbol] >= self.max_retries:
                            self.logger.warning(f"Trop d'erreurs pour {symbol}, mise en pause temporaire")
                            if self.stop_event.wait(timeout=60):  # Pause d'une minute avant de réessayer
                                break
                            self.error_counts[symbol] = 0  # Réinitialisation du compteur
                    else:
                        self.logger.debug(f"Mise à jour différée pour {symbol} - dernière mise à jour trop récente")
                    
                    # Pause courte entre les symboles
                    time.sleep(0.5)
                
                # Nettoyage périodique des anciennes données (30 jours par défaut)
                self.db.cleanup_old_data()
                
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle principale: {str(e)}")
                
            finally:
                # Attendre avant la prochaine itération
                time.sleep(self.update_interval)
        
        self.logger.info(f"Arrêt de la boucle de mise à jour des données pour l'instance {self.instance_id}")
        self.shutdown_complete.set()

    def start(self):
        """Démarre le service dans un thread séparé"""
        if self.update_thread is not None and self.update_thread.is_alive():
            self.logger.warning("Le service est déjà en cours d'exécution")
            return False
            
        self.stop_event.clear()
        self.shutdown_complete.clear()
        while not self.shutdown_queue.empty():
            self.shutdown_queue.get_nowait()  # Clear any pending shutdown signals
            
        self.update_thread = threading.Thread(target=self.run)
        self.update_thread.daemon = True
        self.update_thread.start()
        return True

    def stop(self):
        """Arrête le service de mise à jour"""
        self.logger.info(f"Arrêt du service de mise à jour des données pour l'instance {self.instance_id}")
        self.stop_event.set()
        
        # Vérifier si le thread existe et est démarré avant d'essayer de le joindre
        if hasattr(self, 'update_thread') and self.update_thread is not None:
            try:
                self.update_thread.join(timeout=10)  # Attendre max 10 secondes
                if self.update_thread.is_alive():
                    self.logger.warning("Le thread de mise à jour ne s'est pas arrêté dans le délai imparti")
            except Exception as e:
                self.logger.error(f"Erreur lors de l'arrêt du thread: {str(e)}")
        
        # Nettoyer la référence au thread
        self.update_thread = None
        
        self.logger.info(f"Arrêt du service de mise à jour des données pour l'instance {self.instance_id}")
