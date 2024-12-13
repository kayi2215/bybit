from typing import Dict, List, Optional, Any
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.collection import Collection
from pymongo.database import Database
from datetime import datetime, timedelta, timezone as tz
import logging
import os
from dotenv import load_dotenv
import time
from bson import ObjectId

class MongoDBManager:
    def __init__(self, uri=None, cache_retention_hours: int = 24):
        """
        Initialise le gestionnaire MongoDB
        
        Args:
            uri: URI de connexion MongoDB (optionnel)
            cache_retention_hours: Durée de rétention du cache en heures (défaut: 24)
        """
        if uri is None:
            load_dotenv()
            mongodb_user = os.getenv('MONGO_ROOT_USER', 'admin')
            mongodb_password = os.getenv('MONGO_ROOT_PASSWORD', 'secure_password')
            mongodb_database = os.getenv('MONGODB_DATABASE', 'trading_db')
            mongodb_uri = f"mongodb://{mongodb_user}:{mongodb_password}@localhost:27017/"
            uri = mongodb_uri
        
        # Configuration du logging
        self.logger = logging.getLogger(__name__)
        
        # Collections names from environment variables
        market_data_collection = os.getenv('MONGODB_COLLECTION_MARKET_DATA', 'market_data')
        indicators_collection = os.getenv('MONGODB_COLLECTION_INDICATORS', 'indicators')
        trades_collection = os.getenv('MONGODB_COLLECTION_TRADES', 'trades')
        monitoring_collection = os.getenv('MONGODB_COLLECTION_MONITORING', 'monitoring')
        api_metrics_collection = os.getenv('MONGODB_COLLECTION_API_METRICS', 'api_metrics')
        
        self.client = MongoClient(uri)
        self.db = self.client[mongodb_database]
        
        # Collections
        self.market_data = self.db[market_data_collection]
        self.indicators = self.db[indicators_collection]
        self.trades = self.db[trades_collection]
        self.backtest_results = self.db['backtest_results']
        self.strategy_config = self.db['strategy_config']
        self.monitoring = self.db[monitoring_collection]
        self.api_metrics = self.db[api_metrics_collection]
        
        # Création des index
        self._setup_indexes()
        
        # Configuration du cache
        self.cache_retention_hours = cache_retention_hours
        self.last_cache_cleanup = time.time()
        self.cleanup_interval = 3600  # Nettoyage toutes les heures
        
        # Nettoyage initial du cache
        self._cleanup_cache()
        
        self.logger.info("MongoDB Manager initialized")

    def close(self):
        """Ferme proprement la connexion à MongoDB"""
        if hasattr(self, 'client'):
            try:
                self.client.close()
                self.logger.info("MongoDB connection closed")
            except Exception as e:
                self.logger.error(f"Error closing MongoDB connection: {str(e)}")
            finally:
                del self.client
                
    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False  # Don't suppress exceptions

    def _setup_indexes(self):
        """Configure les index pour optimiser les requêtes"""
        # Index existants
        self.market_data.create_index([("symbol", ASCENDING), ("timestamp", DESCENDING)])
        self.market_data.create_index([("timestamp", DESCENDING)])
        
        # Nouveaux index pour la structure hybride
        self.market_data.create_index([("symbol", ASCENDING), ("created_at", DESCENDING)])
        self.indicators.create_index([("market_data_id", ASCENDING)])
        self.indicators.create_index([("symbol", ASCENDING), ("timestamp", DESCENDING)])
        self.indicators.create_index([("market_data_id", ASCENDING), ("type", ASCENDING)])
        
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

    def cleanup_cache(self):
        """
        Méthode publique pour nettoyer le cache
        """
        return self._cleanup_cache()

    def _cleanup_cache(self):
        """
        Nettoie les entrées de cache obsolètes
        """
        try:
            current_time = time.time()
            
            # Vérifier si un nettoyage est nécessaire
            if current_time - self.last_cache_cleanup < self.cleanup_interval:
                return
                
            # Calculer la limite de temps pour le cache
            retention_limit = current_time - (self.cache_retention_hours * 3600)
            
            # Mettre à jour les documents avec un cache obsolète
            update_result = self.market_data.update_many(
                {
                    'cached_indicators.last_update': {'$lt': retention_limit}
                },
                {
                    '$set': {
                        'cached_indicators': {
                            'last_update': current_time,
                            'common': {}
                        }
                    }
                }
            )
            
            # Supprimer les indicateurs avancés obsolètes
            delete_result = self.indicators.delete_many({
                'timestamp': {'$lt': retention_limit}
            })
            
            self.logger.info(
                f"Nettoyage du cache - Mis à jour: {update_result.modified_count} "
                f"documents, Supprimé: {delete_result.deleted_count} indicateurs"
            )
            
            self.last_cache_cleanup = current_time
            
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage du cache: {str(e)}")

    def save_market_data(self, data: Dict[str, Any]) -> ObjectId:
        """
        Sauvegarde les données de marché avec support pour le cache d'indicateurs
        """
        try:
            # Vérifier et nettoyer le cache si nécessaire
            self._cleanup_cache()
            
            # Continuer avec la sauvegarde normale
            if not all(k in data for k in ['symbol', 'timestamp', 'basic_analysis']):
                raise ValueError("Données de marché incomplètes")

            document = {
                'symbol': data['symbol'],
                'timestamp': data['timestamp'],
                'basic_analysis': data['basic_analysis'],
                'cached_indicators': data.get('cached_indicators', {
                    'last_update': time.time(),
                    'common': {}
                }),
                'created_at': datetime.now(tz.utc)
            }
            
            result = self.market_data.insert_one(document)
            self.logger.debug(f"Données de marché sauvegardées pour {data['symbol']}")
            return result.inserted_id
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des données de marché: {str(e)}")
            raise

    def save_advanced_indicators(self, market_data_id: ObjectId, data: Dict[str, Any]) -> None:
        """
        Sauvegarde les indicateurs avancés liés aux données de marché
        """
        try:
            if not all(k in data for k in ['symbol', 'timestamp', 'type', 'data']):
                raise ValueError("Données d'indicateurs incomplètes")

            document = {
                'market_data_id': market_data_id,
                'symbol': data['symbol'],
                'timestamp': data['timestamp'],
                'type': data['type'],
                'indicators': data['data'],  # Stocker sous 'indicators'
                'created_at': datetime.now(tz.utc)
            }
            
            # Mise à jour ou insertion du document
            self.indicators.update_one(
                {
                    'market_data_id': market_data_id,
                    'symbol': data['symbol']
                },
                {'$set': document},
                upsert=True
            )
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la sauvegarde des indicateurs avancés: {str(e)}")
            raise

    def update_cached_indicators(self, market_data_id: ObjectId, indicators: Dict[str, Any]) -> None:
        """
        Met à jour les indicateurs en cache pour un document market_data
        
        Args:
            market_data_id: ID du document market_data
            indicators: Dictionnaire des indicateurs à mettre en cache
        """
        try:
            update = {
                '$set': {
                    'cached_indicators': {
                        'last_update': time.time(),
                        'common': indicators
                    }
                }
            }
            
            result = self.market_data.update_one({'_id': market_data_id}, update)
            if result.modified_count == 0:
                self.logger.warning(f"Aucune mise à jour du cache pour market_data_id: {market_data_id}")
            else:
                self.logger.debug(f"Cache d'indicateurs mis à jour pour market_data_id: {market_data_id}")
                
        except Exception as e:
            self.logger.error(f"Erreur lors de la mise à jour du cache: {str(e)}")
            raise

    def get_market_data_with_indicators(self, symbol: str, include_advanced: bool = True) -> Optional[Dict]:
        """
        Récupère les données de marché avec les indicateurs pour un symbole
        
        Args:
            symbol: Symbole de trading
            include_advanced: Si True, inclut les indicateurs avancés
            
        Returns:
            Dict contenant les données de marché et les indicateurs
        """
        try:
            # Récupérer les dernières données de marché
            market_data = self.get_latest_market_data(symbol)
            if not market_data:
                return None

            if include_advanced:
                # Récupérer les indicateurs avancés associés
                indicators = self.indicators.find_one({
                    'market_data_id': market_data['_id'],
                    'symbol': symbol
                })
                if indicators and 'indicators' in indicators:
                    market_data['indicators'] = indicators['indicators']

            return market_data
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des données: {str(e)}")
            return None

    def store_market_data(self, data: Dict[str, Any]):
        """
        Méthode de compatibilité pour l'ancien format
        """
        try:
            if not all(k in data for k in ['symbol', 'timestamp', 'data']):
                raise ValueError("Missing required fields in market data")
            
            # Insérer les données
            self.market_data.insert_one(data)
            self.logger.debug(f"Stored market data for {data['symbol']}")
            
        except Exception as e:
            self.logger.error(f"Error storing market data: {str(e)}")
            raise

    def store_indicators(self, symbol: str, indicators: Dict[str, Any]):
        """
        Stocke les indicateurs pour un symbole donné
        """
        try:
            document = {
                'symbol': symbol,
                'timestamp': datetime.now(tz.utc),
                'indicators': indicators,  # Stocker directement sous 'indicators'
                'created_at': datetime.now(tz.utc)
            }
            
            self.indicators.insert_one(document)
            
        except Exception as e:
            self.logger.error(f"Erreur lors du stockage des indicateurs: {str(e)}")
            raise

    def get_latest_market_data(self, symbol: str) -> Dict:
        """
        Récupère les dernières données de marché pour un symbole donné
        """
        try:
            # Récupérer le document le plus récent pour ce symbole
            result = self.market_data.find_one(
                {"symbol": symbol},
                sort=[("timestamp", -1)]
            )
            
            if result:
                return result
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des données pour {symbol}: {str(e)}")
            return None

    def get_latest_indicators(self, symbol: str, limit: int = 1) -> List[Dict]:
        """
        Récupère les derniers indicateurs pour un symbole donné
        """
        try:
            results = list(self.indicators.find(
                {"symbol": symbol},
                sort=[("timestamp", -1)],
                limit=limit
            ))

            formatted_results = []
            for result in results:
                # Créer un dictionnaire de base avec les champs communs
                formatted_result = {
                    "symbol": result["symbol"],
                    "timestamp": result["timestamp"],
                    "indicators": {}  # Initialiser le champ indicators
                }
                
                # Si les indicateurs sont stockés sous 'indicators', les utiliser directement
                if "indicators" in result:
                    formatted_result["indicators"] = result["indicators"]
                # Si les données sont stockées sous 'data' (format avancé)
                elif "data" in result:
                    formatted_result["indicators"] = result["data"]
                # Sinon, collecter tous les autres champs comme indicateurs
                else:
                    indicators_data = {
                        k: v for k, v in result.items() 
                        if k not in ["_id", "created_at", "symbol", "timestamp"]
                    }
                    # Si nous avons des indicateurs directs, les mettre au niveau racine aussi
                    formatted_result.update(indicators_data)
                    formatted_result["indicators"] = indicators_data
                
                formatted_results.append(formatted_result)

            return formatted_results

        except Exception as e:
            self.logger.error(f"Error retrieving indicators: {str(e)}")
            return []

    def store_trade(self, trade_data: Dict[str, Any]):
        """
        Stocke les informations d'une transaction
        :param trade_data: Données de la transaction
        """
        try:
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return
                
            trade_data["timestamp"] = datetime.now(tz.utc)
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
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return
                
            document = {
                "strategy_name": strategy_name,
                "timestamp": datetime.now(tz.utc),
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
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return
                
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
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return
                
            if not data_list:
                return
            
            # Validate and prepare documents
            documents = []
            for data in data_list:
                if not isinstance(data, dict) or 'symbol' not in data or 'data' not in data:
                    raise ValueError("Invalid market data format")
                
                document = {
                    "symbol": data['symbol'],
                    "timestamp": datetime.now(tz.utc),
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
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return
                
            if not indicators_list:
                return
            
            # Validate and prepare documents
            documents = []
            for indicator_data in indicators_list:
                if not isinstance(indicator_data, dict) or 'symbol' not in indicator_data or 'indicators' not in indicator_data:
                    raise ValueError("Invalid indicator data format")
                
                document = {
                    "symbol": indicator_data['symbol'],
                    "timestamp": datetime.now(tz.utc),
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
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return
                
            document = {
                "endpoint": endpoint,
                "metric_type": metric_type,
                "value": value,
                "timestamp": datetime.now(tz.utc)
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
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return
                
            document = {
                "endpoint": endpoint,
                "event_type": event_type,
                "details": details,
                "timestamp": datetime.now(tz.utc)
            }
            self.monitoring.insert_one(document)
            self.logger.debug(f"Stored monitoring event for {endpoint}")
        except Exception as e:
            self.logger.error(f"Error storing monitoring event: {str(e)}")
            raise

    def get_latest_market_data(self, symbol: str) -> Dict:
        """
        Récupère les dernières données de marché pour un symbole donné
        """
        try:
            # Récupérer le document le plus récent pour ce symbole
            result = self.market_data.find_one(
                {"symbol": symbol},
                sort=[("timestamp", -1)]
            )
            
            if result:
                return result
            
            return None
            
        except Exception as e:
            self.logger.error(f"Erreur lors de la récupération des données pour {symbol}: {str(e)}")
            return None

    def get_aggregated_indicators(self, symbol: str, interval: str, start_time: datetime) -> List[Dict]:
        """
        Récupère les indicateurs agrégés pour un symbole donné
        """
        try:
            pipeline = [
                {
                    "$match": {
                        "symbol": symbol,
                        "timestamp": {"$gte": start_time}
                    }
                },
                {
                    "$sort": {"timestamp": -1}
                },
                {
                    "$project": {
                        "_id": 1,
                        "symbol": 1,
                        "timestamp": 1,
                        "indicators": 1  # Projeter les indicateurs
                    }
                }
            ]
            
            results = list(self.indicators.aggregate(pipeline))
            return results

        except Exception as e:
            self.logger.error(f"Error aggregating indicators: {str(e)}")
            return []

    def get_trades_by_timeframe(self, start_time: datetime, end_time: datetime = None) -> List[Dict[str, Any]]:
        """
        Récupère les transactions dans une période donnée
        :param start_time: Début de la période
        :param end_time: Fin de la période (par défaut: maintenant)
        :return: Liste des transactions
        """
        try:
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return []
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return []
            
            if end_time is None:
                end_time = datetime.now(tz.utc)
            
            cursor = self.trades.find({
                "timestamp": {
                    "$gte": start_time,
                    "$lte": end_time
                }
            }).sort("timestamp", ASCENDING)
            
            return list(cursor)
        except Exception as e:
            self.logger.error(f"Error retrieving trades: {str(e)}")
            raise

    def store_monitoring_data(self, data: Dict[str, Any]):
        """
        Stocke les données de monitoring
        :param data: Données de monitoring à stocker
        """
        try:
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return
                
            data["timestamp"] = datetime.now(tz.utc)
            self.monitoring.insert_one(data)
            self.logger.debug("Stored monitoring data")
        except Exception as e:
            self.logger.error(f"Error storing monitoring data: {str(e)}")
            raise

    def get_monitoring_data(self, start_time: datetime, end_time: datetime = None) -> List[Dict[str, Any]]:
        """
        Récupère les données de monitoring pour une période donnée
        :param start_time: Début de la période
        :param end_time: Fin de la période (par défaut: maintenant)
        :return: Liste des données de monitoring
        """
        try:
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return []
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return []
            
            if end_time is None:
                end_time = datetime.now(tz.utc)
            
            cursor = self.monitoring.find({
                "timestamp": {
                    "$gte": start_time,
                    "$lte": end_time
                }
            }).sort("timestamp", ASCENDING)
            
            return list(cursor)
        except Exception as e:
            self.logger.error(f"Error retrieving monitoring data: {str(e)}")
            raise

    def store_api_metric(self, metric_data: Dict[str, Any]):
        """
        Stocke une métrique d'API
        :param metric_data: Données de la métrique à stocker
        """
        try:
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return
                
            metric_data["timestamp"] = datetime.now(tz.utc)
            self.api_metrics.insert_one(metric_data)
            self.logger.debug(f"Stored API metric for {metric_data.get('endpoint')}")
        except Exception as e:
            self.logger.error(f"Error storing API metric: {str(e)}")
            raise

    def get_api_metrics(self, endpoint: str = None, metric_type: str = None, 
                       start_time: datetime = None, end_time: datetime = None) -> List[Dict[str, Any]]:
        """
        Récupère les métriques d'API avec filtres optionnels
        :param endpoint: Filtre par endpoint
        :param metric_type: Filtre par type de métrique
        :param start_time: Début de la période
        :param end_time: Fin de la période
        :return: Liste des métriques d'API
        """
        try:
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return []
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return []
            
            query = {}
            if endpoint:
                query["endpoint"] = endpoint
            if metric_type:
                query["metric_type"] = metric_type
            if start_time or end_time:
                query["timestamp"] = {}
                if start_time:
                    query["timestamp"]["$gte"] = start_time
                if end_time:
                    query["timestamp"]["$lte"] = end_time
            
            cursor = self.api_metrics.find(query).sort("timestamp", ASCENDING)
            return list(cursor)
        except Exception as e:
            self.logger.error(f"Error retrieving API metrics: {str(e)}")
            raise

    def get_historical_data(self, symbol: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        Récupère les données historiques pour une période donnée
        :param symbol: Symbole de la paire de trading
        :param start_time: Début de la période
        :param end_time: Fin de la période
        :return: Liste des données historiques
        """
        try:
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return []
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return []
            
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

    def get_backtest_results(self, strategy_name: str) -> List[Dict[str, Any]]:
        """
        Récupère les résultats des backtests pour une stratégie
        :param strategy_name: Nom de la stratégie
        :return: Liste des résultats des backtests
        """
        try:
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return []
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return []
            
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
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return None
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return None
            
            return self.strategy_config.find_one({"strategy_name": strategy_name})
        except Exception as e:
            self.logger.error(f"Error retrieving strategy config: {str(e)}")
            return None

    def get_trades_history(self, symbol: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère l'historique des transactions
        :param symbol: Symbole de la paire de trading (optionnel)
        :param limit: Nombre maximum de transactions à récupérer
        :return: Liste des transactions
        """
        try:
            if not hasattr(self, 'client') or self.client is None:
                self.logger.error("MongoDB client not available")
                return []
                
            # Vérifier si le client est toujours utilisable
            try:
                self.client.admin.command('ping')
            except Exception:
                self.logger.error("MongoDB connection lost")
                return []
            
            query = {"symbol": symbol} if symbol else {}
            return list(self.trades.find(query).sort("timestamp", DESCENDING).limit(limit))
        except Exception as e:
            self.logger.error(f"Error retrieving trades history: {str(e)}")
            return []

    def cleanup_old_data(self, days_to_keep: int = 30) -> None:
        """
        Nettoie les anciennes données et le cache
        """
        try:
            cutoff_date = datetime.now(tz.utc) - timedelta(days=days_to_keep)
            
            # Supprimer les anciennes données de marché
            old_market_data = list(self.market_data.find({
                "timestamp": {"$lt": cutoff_date}
            }))
            
            # Supprimer les indicateurs associés aux données supprimées
            for data in old_market_data:
                self.indicators.delete_many({
                    "market_data_id": data["_id"]
                })
            
            # Supprimer les anciennes données de marché
            result = self.market_data.delete_many({
                "timestamp": {"$lt": cutoff_date}
            })
            
            self.logger.info(f"Cleaned up {result.deleted_count} old market data records")
            
        except Exception as e:
            self.logger.error(f"Erreur lors du nettoyage des données: {str(e)}")
            raise
