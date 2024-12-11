from typing import Dict, List, Optional, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from datetime import datetime, timedelta
import logging
import os
from dotenv import load_dotenv
import time

class MongoDBManager:
    def __init__(self):
        """Initialise la connexion à MongoDB"""
        load_dotenv()
        
        # Configuration du logging
        self.logger = logging.getLogger(__name__)
        
        # Get MongoDB credentials from environment variables
        mongodb_user = os.getenv('MONGO_ROOT_USER', 'admin')
        mongodb_password = os.getenv('MONGO_ROOT_PASSWORD', 'secure_password')
        mongodb_database = os.getenv('MONGODB_DATABASE', 'trading_db')
        
        # Collections names from environment variables
        market_data_collection = os.getenv('MONGODB_COLLECTION_MARKET_DATA', 'market_data')
        indicators_collection = os.getenv('MONGODB_COLLECTION_INDICATORS', 'indicators')
        trades_collection = os.getenv('MONGODB_COLLECTION_TRADES', 'trades')
        monitoring_collection = os.getenv('MONGODB_COLLECTION_MONITORING', 'monitoring')
        api_metrics_collection = os.getenv('MONGODB_COLLECTION_API_METRICS', 'api_metrics')
        
        # Construction de l'URI MongoDB avec les identifiants
        mongodb_uri = f"mongodb://{mongodb_user}:{mongodb_password}@localhost:27017/"
        
        # Connexion à MongoDB avec retry logic
        max_retries = 3
        retry_count = 0
        while retry_count < max_retries:
            try:
                self.client = MongoClient(mongodb_uri, serverSelectionTimeoutMS=5000)
                # Test de la connexion
                self.client.admin.command('ping')
                self.logger.info("Successfully connected to MongoDB")
                break
            except Exception as e:
                retry_count += 1
                if retry_count == max_retries:
                    self.logger.error(f"Failed to connect to MongoDB after {max_retries} attempts: {str(e)}")
                    raise
                self.logger.warning(f"Failed to connect to MongoDB (attempt {retry_count}): {str(e)}")
                time.sleep(1)  # Wait before retrying
        
        # Sélection de la base de données
        self.db: Database = self.client[mongodb_database]
        
        # Collections
        self.market_data: Collection = self.db[market_data_collection]
        self.indicators: Collection = self.db[indicators_collection]
        self.trades: Collection = self.db[trades_collection]
        self.backtest_results: Collection = self.db['backtest_results']
        self.strategy_config: Collection = self.db['strategy_config']
        self.monitoring: Collection = self.db[monitoring_collection]
        self.api_metrics: Collection = self.db[api_metrics_collection]
        
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
        
        # Index pour backtest_results
        self.backtest_results.create_index([("strategy_name", ASCENDING), ("timestamp", DESCENDING)])
        
        # Index pour strategy_config
        self.strategy_config.create_index([("strategy_name", ASCENDING)])
        
        # Index pour monitoring
        self.monitoring.create_index([("timestamp", DESCENDING)])
        self.monitoring.create_index([("endpoint", ASCENDING), ("timestamp", DESCENDING)])
        
        # Index pour api_metrics
        self.api_metrics.create_index([("timestamp", DESCENDING)])
        self.api_metrics.create_index([("endpoint", ASCENDING), ("metric_type", ASCENDING), ("timestamp", DESCENDING)])

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

    def store_backtest_result(self, strategy_name: str, result: Dict[str, Any]):
        """
        Stocke le résultat d'un backtest
        :param strategy_name: Nom de la stratégie
        :param result: Résultat du backtest
        """
        try:
            document = {
                "strategy_name": strategy_name,
                "timestamp": datetime.now(),
                "result": result
            }
            self.backtest_results.insert_one(document)
            self.logger.info(f"Stored backtest result for {strategy_name}")
        except Exception as e:
            self.logger.error(f"Error storing backtest result: {str(e)}")
            raise

    def store_strategy_config(self, strategy_name: str, config: Dict[str, Any]):
        """
        Stocke la configuration d'une stratégie
        :param strategy_name: Nom de la stratégie
        :param config: Configuration de la stratégie
        """
        try:
            document = {
                "strategy_name": strategy_name,
                "config": config
            }
            self.strategy_config.insert_one(document)
            self.logger.info(f"Stored strategy config for {strategy_name}")
        except Exception as e:
            self.logger.error(f"Error storing strategy config: {str(e)}")
            raise

    def store_market_data_bulk(self, data_list: List[Dict[str, Any]]):
        """
        Stocke plusieurs données de marché en une seule opération
        :param data_list: Liste des données à stocker
        """
        try:
            if not data_list:
                return
            
            # Validate and prepare documents
            documents = []
            for data in data_list:
                if not isinstance(data, dict) or 'symbol' not in data or 'data' not in data:
                    raise ValueError("Invalid market data format")
                
                document = {
                    "symbol": data['symbol'],
                    "timestamp": datetime.now(),
                    "data": data['data']
                }
                documents.append(document)
            
            # Insert documents in bulk
            result = self.market_data.insert_many(documents)
            self.logger.info(f"Stored {len(result.inserted_ids)} market data documents")
        except Exception as e:
            self.logger.error(f"Error storing market data in bulk: {str(e)}")
            raise

    def store_indicators_bulk(self, indicators_list: List[Dict[str, Any]]):
        """
        Stocke plusieurs indicateurs en une seule opération
        :param indicators_list: Liste des indicateurs à stocker
        """
        try:
            if not indicators_list:
                return
            
            # Validate and prepare documents
            documents = []
            for indicator_data in indicators_list:
                if not isinstance(indicator_data, dict) or 'symbol' not in indicator_data or 'indicators' not in indicator_data:
                    raise ValueError("Invalid indicator data format")
                
                document = {
                    "symbol": indicator_data['symbol'],
                    "timestamp": datetime.now(),
                    "indicators": indicator_data['indicators']
                }
                documents.append(document)
            
            # Insert documents in bulk
            result = self.indicators.insert_many(documents)
            self.logger.info(f"Stored {len(result.inserted_ids)} indicator documents")
        except Exception as e:
            self.logger.error(f"Error storing indicators in bulk: {str(e)}")
            raise

    def store_api_metrics(self, endpoint: str, metric_type: str, value: float):
        """
        Stocke les métriques de l'API Bybit
        :param endpoint: Endpoint de l'API
        :param metric_type: Type de métrique (latency, availability, rate_limit)
        :param value: Valeur de la métrique
        """
        try:
            document = {
                "endpoint": endpoint,
                "metric_type": metric_type,
                "value": value,
                "timestamp": datetime.now()
            }
            self.api_metrics.insert_one(document)
            self.logger.debug(f"Stored API metric for {endpoint}: {metric_type}")
        except Exception as e:
            self.logger.error(f"Error storing API metric: {str(e)}")
            raise

    def store_monitoring_event(self, endpoint: str, event_type: str, details: Dict[str, Any]):
        """
        Stocke les événements de monitoring
        :param endpoint: Endpoint concerné
        :param event_type: Type d'événement (error, warning, info)
        :param details: Détails de l'événement
        """
        try:
            document = {
                "endpoint": endpoint,
                "event_type": event_type,
                "details": details,
                "timestamp": datetime.now()
            }
            self.monitoring.insert_one(document)
            self.logger.debug(f"Stored monitoring event for {endpoint}")
        except Exception as e:
            self.logger.error(f"Error storing monitoring event: {str(e)}")
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

    def get_backtest_results(self, strategy_name: str) -> List[Dict[str, Any]]:
        """
        Récupère les résultats des backtests pour une stratégie
        :param strategy_name: Nom de la stratégie
        :return: Liste des résultats des backtests
        """
        try:
            return list(self.backtest_results.find({"strategy_name": strategy_name}).sort("timestamp", DESCENDING))
        except Exception as e:
            self.logger.error(f"Error retrieving backtest results: {str(e)}")
            return []

    def get_strategy_config(self, strategy_name: str) -> Optional[Dict[str, Any]]:
        """
        Récupère la configuration d'une stratégie
        :param strategy_name: Nom de la stratégie
        :return: Configuration de la stratégie
        """
        try:
            return self.strategy_config.find_one({"strategy_name": strategy_name})
        except Exception as e:
            self.logger.error(f"Error retrieving strategy config: {str(e)}")
            return None

    def get_api_metrics(self, endpoint: str, metric_type: str, 
                       start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        Récupère les métriques de l'API pour une période donnée
        :param endpoint: Endpoint de l'API
        :param metric_type: Type de métrique
        :param start_time: Début de la période
        :param end_time: Fin de la période
        :return: Liste des métriques
        """
        try:
            query = {
                "endpoint": endpoint,
                "metric_type": metric_type,
                "timestamp": {
                    "$gte": start_time,
                    "$lte": end_time
                }
            }
            return list(self.api_metrics.find(query).sort("timestamp", DESCENDING))
        except Exception as e:
            self.logger.error(f"Error retrieving API metrics: {str(e)}")
            raise

    def get_monitoring_events(self, endpoint: Optional[str] = None,
                            event_type: Optional[str] = None,
                            start_time: Optional[datetime] = None,
                            end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Récupère les événements de monitoring
        :param endpoint: Filtrer par endpoint (optionnel)
        :param event_type: Filtrer par type d'événement (optionnel)
        :param start_time: Début de la période (optionnel)
        :param end_time: Fin de la période (optionnel)
        :return: Liste des événements
        """
        try:
            query = {}
            if endpoint:
                query["endpoint"] = endpoint
            if event_type:
                query["event_type"] = event_type
            if start_time and end_time:
                query["timestamp"] = {
                    "$gte": start_time,
                    "$lte": end_time
                }
            return list(self.monitoring.find(query).sort("timestamp", DESCENDING))
        except Exception as e:
            self.logger.error(f"Error retrieving monitoring events: {str(e)}")
            raise

    def cleanup_old_data(self, days_to_keep: int = 30):
        """
        Nettoie les anciennes données
        :param days_to_keep: Nombre de jours de données à conserver
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)
            
            # Nettoyer les données de marché
            result = self.market_data.delete_many({"timestamp": {"$lt": cutoff_date}})
            self.logger.info(f"Deleted {result.deleted_count} old market data documents")
            
            # Nettoyer les indicateurs
            result = self.indicators.delete_many({"timestamp": {"$lt": cutoff_date}})
            self.logger.info(f"Deleted {result.deleted_count} old indicators documents")
            
            # Nettoyer les transactions
            result = self.trades.delete_many({"timestamp": {"$lt": cutoff_date}})
            self.logger.info(f"Deleted {result.deleted_count} old trades documents")
            
            # Nettoyer les résultats des backtests
            result = self.backtest_results.delete_many({"timestamp": {"$lt": cutoff_date}})
            self.logger.info(f"Deleted {result.deleted_count} old backtest results documents")
            
            # Nettoyer les métriques de l'API
            result = self.api_metrics.delete_many({"timestamp": {"$lt": cutoff_date}})
            self.logger.info(f"Deleted {result.deleted_count} old API metrics documents")
            
            # Nettoyer les événements de monitoring
            result = self.monitoring.delete_many({"timestamp": {"$lt": cutoff_date}})
            self.logger.info(f"Deleted {result.deleted_count} old monitoring events documents")
            
            # Force un délai pour s'assurer que les suppressions sont effectuées
            time.sleep(0.5)
            
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
