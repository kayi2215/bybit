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
        shutdown_timeout: int = 5
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
        """
        load_dotenv()
        
        self.symbols = symbols
        self.db = db or MongoDBManager()
        self.stop_event = threading.Event()
        self.shutdown_complete = threading.Event()
        self.shutdown_timeout = shutdown_timeout
        self.shutdown_queue = Queue()
        self.update_thread = None
        
        # Configuration des clés API
        self.api_key = api_key or os.getenv('BYBIT_API_KEY')
        self.api_secret = api_secret or os.getenv('BYBIT_API_SECRET')
        
        if not self.api_key or not self.api_secret:
            raise ValueError("Les clés API Bybit sont requises")
        
        # Initialisation des composants
        self.collector = MarketDataCollector(
            api_key=self.api_key,
            api_secret=self.api_secret,
            use_testnet=use_testnet
        )
        self.api_monitor = APIMonitor()
        self.technical_analysis = TechnicalAnalysis()
        
        # Configuration du logging et des paramètres
        self.logger = logging.getLogger(__name__)
        self.update_interval = 10  # Intervalle de mise à jour en secondes
        self.max_retries = 3  # Nombre maximum de tentatives en cas d'erreur
        
        # Dictionnaire pour suivre les erreurs par symbole
        self.error_counts: Dict[str, int] = {symbol: 0 for symbol in symbols}

    def update_market_data(self, symbol: str) -> bool:
        """Met à jour les données de marché pour un symbole donné"""
        try:
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
                'ticker': ticker_data,
                'klines': klines_data.to_dict('records') if isinstance(klines_data, pd.DataFrame) else klines_data,
                'orderbook': orderbook_data,
                'trades': trades_data,
                'exchange': 'bybit'
            }

            # Sauvegarde des données de marché
            self.db.store_market_data(market_data)

            # Sauvegarde des indicateurs techniques s'ils sont disponibles
            if technical_data and not self.stop_event.is_set():
                technical_data['symbol'] = symbol
                technical_data['timestamp'] = datetime.now()
                self.db.store_indicators(technical_data)
                self.logger.info(f"Indicateurs techniques mis à jour pour {symbol}")

            # Réinitialisation du compteur d'erreurs
            self.error_counts[symbol] = 0
            return True

        except Exception as e:
            # Gestion des erreurs
            self.error_counts[symbol] += 1
            self.logger.error(f"Erreur lors de la mise à jour des données pour {symbol} (tentative {self.error_counts[symbol]}): {str(e)}")
            return False

    def run(self):
        """Lance la boucle de mise à jour des données"""
        self.logger.info("Démarrage du service de mise à jour des données")
        
        while not self.stop_event.is_set():
            try:
                # Check for shutdown request
                try:
                    if self.shutdown_queue.get_nowait() == "shutdown":
                        break
                except Empty:
                    pass
                
                for symbol in self.symbols:
                    if self.stop_event.is_set():
                        break
                        
                    # Mise à jour des données avec gestion des erreurs
                    success = self.update_market_data(symbol)
                    
                    if not success and self.error_counts[symbol] >= self.max_retries:
                        self.logger.warning(f"Trop d'erreurs pour {symbol}, mise en pause temporaire")
                        if self.stop_event.wait(timeout=60):  # Pause d'une minute avant de réessayer
                            break
                        self.error_counts[symbol] = 0  # Réinitialisation du compteur
                    
                    if self.stop_event.wait(timeout=self.update_interval):
                        break
                    
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle principale: {str(e)}")
                if self.stop_event.wait(timeout=30):  # Pause plus longue en cas d'erreur générale
                    break
                
        self.logger.info("Arrêt du service de mise à jour des données")
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
        """Arrête proprement le service de mise à jour"""
        if self.update_thread is None or not self.update_thread.is_alive():
            return True
            
        self.logger.info("Demande d'arrêt du service de mise à jour")
        self.stop_event.set()
        self.shutdown_queue.put("shutdown")
        
        # Attente de l'arrêt complet avec timeout configurable
        shutdown_success = self.shutdown_complete.wait(timeout=self.shutdown_timeout)
        if not shutdown_success:
            self.logger.warning("Le service de mise à jour ne s'est pas arrêté dans le délai imparti")
            self.update_thread = None
            
        return shutdown_success
