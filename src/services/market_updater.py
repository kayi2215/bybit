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

class MarketUpdater:
    def __init__(
        self,
        symbols: List[str],
        db: Optional[MongoDBManager] = None,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        use_testnet: bool = False,
        shutdown_timeout: int = 5,
        instance_id: Optional[str] = None
    ):
        """
        Initialise le service de mise à jour des données de marché
        
        Args:
            symbols: Liste des paires de trading à surveiller
            db: Instance optionnelle de MongoDBManager
            api_key: Clé API Bybit (optionnelle, utilise la config par défaut si non fournie)
            api_secret: Secret API Bybit (optionnel, utilise la config par défaut si non fourni)
            use_testnet: Utiliser le testnet Bybit au lieu du mainnet
            shutdown_timeout: Délai d'arrêt en secondes
            instance_id: Identifiant unique de l'instance du bot
        """
        load_dotenv()
        
        self.symbols = symbols
        self.db = db or MongoDBManager()
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
        
        # Dictionnaire pour suivre les erreurs par symbole
        self.error_counts: Dict[str, int] = {symbol: 0 for symbol in symbols}

    def update_market_data(self, symbol: str) -> bool:
        """Met à jour les données de marché pour un symbole donné"""
        try:
            current_time = time.time()
            # Vérifier si une mise à jour est nécessaire (éviter les mises à jour trop fréquentes)
            if current_time - self.last_update.get(symbol, 0) < self.update_interval:
                self.logger.debug(f"Mise à jour ignorée pour {symbol} - trop récente")
                return True

            # Check stop event before starting update
            if self.stop_event.is_set():
                return False

            # Vérifie d'abord la disponibilité de l'API
            health_status = self.api_monitor.check_api_health()
            if not health_status or health_status.get('status') != 'OK':
                raise Exception("API Bybit is not healthy")

            # Check stop event before data collection
            if self.stop_event.is_set():
                return False

            # Récupération des données
            ticker_data = self.collector.get_ticker(symbol)
            klines_data = self.collector.get_klines(symbol, interval='1m', limit=100)
            orderbook_data = self.collector.get_order_book(symbol, limit=100)
            trades_data = self.collector.get_public_trade_history(symbol, limit=50)

            # Check stop event before processing
            if self.stop_event.is_set():
                return False

            # Calcul des indicateurs techniques
            if isinstance(klines_data, pd.DataFrame):
                technical_data = self.technical_analysis.get_summary(klines_data)
            else:
                self.logger.warning(f"Impossible de calculer les indicateurs techniques pour {symbol}: format de données invalide")
                technical_data = None

            # Check stop event before saving
            if self.stop_event.is_set():
                return False

            # Préparation des données pour la sauvegarde
            market_data = {
                'symbol': symbol,
                'timestamp': datetime.now(),
                'data': {
                    'ticker': ticker_data,
                    'klines': klines_data.to_dict('records') if isinstance(klines_data, pd.DataFrame) else klines_data,
                    'orderbook': orderbook_data,
                    'trades': trades_data,
                    'exchange': 'bybit'
                }
            }

            # Sauvegarde des données de marché
            self.db.store_market_data(market_data)

            # Sauvegarde des indicateurs techniques s'ils sont disponibles
            if technical_data and not self.stop_event.is_set():
                technical_data['symbol'] = symbol
                technical_data['timestamp'] = datetime.now()
                self.db.store_indicators(symbol=symbol, indicators=technical_data)
                self.logger.info(f"Indicateurs techniques mis à jour pour {symbol}")

            # Réinitialisation du compteur d'erreurs
            self.error_counts[symbol] = 0
            self.last_update[symbol] = current_time
            return True

        except Exception as e:
            # Gestion des erreurs
            self.error_counts[symbol] += 1
            self.logger.error(f"Erreur lors de la mise à jour des données pour {symbol} (tentative {self.error_counts[symbol]}): {str(e)}")
            return False

    def run(self):
        """Exécute la boucle principale de mise à jour des données"""
        self.logger.info(f"Démarrage du service de mise à jour des données pour l'instance {self.instance_id}")
        
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
                
                # Attendre avant la prochaine itération
                if self.stop_event.wait(timeout=self.update_interval):
                    break
                    
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle de mise à jour: {str(e)}")
                if self.stop_event.wait(timeout=30):  # Pause plus longue en cas d'erreur générale
                    break
        
        self.logger.info(f"Arrêt du service de mise à jour des données pour l'instance {self.instance_id}")
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
