from typing import Dict, List, Optional, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv

class MongoDBManager:
    def __init__(self):
        """Initialise la connexion à MongoDB"""
        load_dotenv()
        
        # Configuration du logging
        self.logger = logging.getLogger(__name__)
        
        # Construction de l'URI MongoDB avec les identifiants
        mongodb_uri = f"mongodb://admin:secure_password@localhost:27017/"
        
        # Connexion à MongoDB
        try:
            self.client = MongoClient(mongodb_uri)
            # Test de la connexion
            self.client.admin.command('ping')
            self.logger.info("Successfully connected to MongoDB")
        except Exception as e:
            self.logger.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
        
        # Sélection de la base de données
        self.db: Database = self.client['trading_db']
        
        # Collections
        self.market_data: Collection = self.db['market_data']
        self.indicators: Collection = self.db['indicators']
        self.trades: Collection = self.db['trades']
        
        # Création des index
        self._setup_indexes()
        
        self.logger.info("MongoDB Manager initialized")

    def _setup_indexes(self):
        """Configure les index pour optimiser les requêtes"""
        # Index pour market_data
        self.market_data.create_index([("symbol", ASCENDING), ("timestamp", DESCENDING)])
        self.market_data.create_index([("timestamp", DESCENDING)])
        
        # Index pour indicators
        self.indicators.create_index([("symbol", ASCENDING), ("timestamp", DESCENDING)])
        
        # Index pour trades
        self.trades.create_index([("timestamp", DESCENDING)])
        self.trades.create_index([("symbol", ASCENDING), ("timestamp", DESCENDING)])

    def store_market_data(self, symbol: str, data: Dict[str, Any]):
        """
        Stocke les données de marché
        :param symbol: Symbole de la paire de trading
        :param data: Données à stocker
        """
        try:
            document = {
                "symbol": symbol,
                "timestamp": datetime.now(),
                "data": data
            }
            self.market_data.insert_one(document)
            self.logger.debug(f"Stored market data for {symbol}")
        except Exception as e:
            self.logger.error(f"Error storing market data: {str(e)}")
            raise

    def store_indicators(self, symbol: str, indicators: Dict[str, Any]):
        """
        Stocke les indicateurs techniques
        :param symbol: Symbole de la paire de trading
        :param indicators: Indicateurs à stocker
        """
        try:
            document = {
                "symbol": symbol,
                "timestamp": datetime.now(),
                "indicators": indicators
            }
            self.indicators.insert_one(document)
            self.logger.debug(f"Stored indicators for {symbol}")
        except Exception as e:
            self.logger.error(f"Error storing indicators: {str(e)}")
            raise

    def store_trade(self, trade_data: Dict[str, Any]):
        """
        Stocke les informations d'une transaction
        :param trade_data: Données de la transaction
        """
        try:
            trade_data["timestamp"] = datetime.now()
            self.trades.insert_one(trade_data)
            self.logger.info(f"Stored trade for {trade_data.get('symbol')}")
        except Exception as e:
            self.logger.error(f"Error storing trade: {str(e)}")
            raise

    def get_latest_market_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les dernières données de marché pour un symbole
        :param symbol: Symbole de la paire de trading
        :return: Dernières données de marché
        """
        try:
            data = self.market_data.find_one(
                {"symbol": symbol},
                sort=[("timestamp", DESCENDING)]
            )
            return data
        except Exception as e:
            self.logger.error(f"Error retrieving market data: {str(e)}")
            return None

    def get_historical_data(self, symbol: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        Récupère les données historiques pour une période donnée
        :param symbol: Symbole de la paire de trading
        :param start_time: Début de la période
        :param end_time: Fin de la période
        :return: Liste des données historiques
        """
        try:
            query = {
                "symbol": symbol,
                "timestamp": {
                    "$gte": start_time,
                    "$lte": end_time
                }
            }
            return list(self.market_data.find(query).sort("timestamp", ASCENDING))
        except Exception as e:
            self.logger.error(f"Error retrieving historical data: {str(e)}")
            return []

    def get_latest_indicators(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les derniers indicateurs techniques pour un symbole
        :param symbol: Symbole de la paire de trading
        :return: Derniers indicateurs techniques
        """
        try:
            data = self.indicators.find_one(
                {"symbol": symbol},
                sort=[("timestamp", DESCENDING)]
            )
            return data
        except Exception as e:
            self.logger.error(f"Error retrieving indicators: {str(e)}")
            return None

    def get_trades_history(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des transactions
        :param symbol: Symbole de la paire de trading (optionnel)
        :param limit: Nombre maximum de transactions à récupérer
        :return: Liste des transactions
        """
        try:
            query = {"symbol": symbol} if symbol else {}
            return list(self.trades.find(query).sort("timestamp", DESCENDING).limit(limit))
        except Exception as e:
            self.logger.error(f"Error retrieving trades history: {str(e)}")
            return []

    def cleanup_old_data(self, days_to_keep: int = 30):
        """
        Nettoie les anciennes données
        :param days_to_keep: Nombre de jours de données à conserver
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Nettoyer les données de marché
            self.market_data.delete_many({"timestamp": {"$lt": cutoff_date}})
            
            # Nettoyer les indicateurs
            self.indicators.delete_many({"timestamp": {"$lt": cutoff_date}})
            
            self.logger.info(f"Cleaned up data older than {days_to_keep} days")
        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {str(e)}")
            raise

    def close(self):
        """Ferme la connexion à MongoDB"""
        try:
            self.client.close()
            self.logger.info("MongoDB connection closed")
        except Exception as e:
            self.logger.error(f"Error closing MongoDB connection: {str(e)}")
            raise
