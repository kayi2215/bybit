# Architecture du Trading Bot Bybit

## Vue d'ensemble du système

```mermaid
classDiagram
    class TradingBot {
        -logger
        -symbols: List[str]
        -db: MongoDBManager
        -market_data: MarketDataCollector
        -monitoring_service: MonitoringService
        -data_updater: MarketUpdater
        -is_running: bool
        -monitoring_thread: Thread
        -trading_thread: Thread
        +__init__(symbols, db)
        +setup_logging()
        +start_monitoring()
        +trading_loop()
        +start_trading()
        +_process_symbol(symbol)
        +start()
        +stop()
        +handle_shutdown()
    }

    class MarketUpdater {
        -symbols: List[str]
        -db: MongoDBManager
        -collector: MarketDataCollector
        -technical_analysis: TechnicalAnalysis
        -api_monitor: APIMonitor
        -update_interval: int
        -stop_event: Event
        -shutdown_complete: Event
        -last_update: Dict[str, float]
        -error_counts: Dict[str, int]
        +__init__(symbols, db, api_key, api_secret)
        +update_market_data(symbol)
        +start()
        +stop()
        +run()
    }

    class MarketDataCollector {
        -client: HTTP
        -logger
        -technical_analyzer: TechnicalAnalysis
        -api_key: str
        -api_secret: str
        -use_testnet: bool
        +__init__(api_key, api_secret, use_testnet)
        +get_current_price(symbol)
        +get_klines(symbol, interval, limit)
        +get_order_book(symbol, limit)
        +get_recent_trades(symbol, limit)
        +get_technical_analysis(symbol, interval, limit)
        +get_market_analysis(symbol)
        +get_ticker(symbol)
        +interval_to_milliseconds(interval)
        +process_kline_data(klines)
    }

    class TechnicalAnalysis {
        -indicators: dict
        +calculate_rsi(data, periods)
        +calculate_sma(data, periods)
        +calculate_ema(data, periods)
        +calculate_macd(data)
        +calculate_bollinger_bands(data, periods)
        +calculate_all(df)
        +get_signals(df)
        +get_summary(df)
        +validate_indicators(indicators)
    }

    TradingBot --> MarketUpdater
    MarketUpdater --> MarketDataCollector
    MarketUpdater --> TechnicalAnalysis
    MarketDataCollector --> TechnicalAnalysis

    class MongoDBManager {
        -client: MongoClient
        -db: Database
        -market_data: Collection
        -indicators: Collection
        -trades: Collection
        -monitoring: Collection
        -api_metrics: Collection
        -backtest_results: Collection
        -strategy_config: Collection
        -logger
        +__init__(uri, db_name)
        +store_market_data(symbol, data)
        +store_indicators(symbol, indicators)
        +store_trade(trade_data)
        +get_latest_market_data(symbol, limit)
        +get_latest_indicators(symbol, limit)
        +cleanup_old_data()
        +get_monitoring_data()
        +store_api_metrics(metrics)
        +close_connection()
        -validate_connection()
        -_setup_indexes()
    }

    class APIMonitor {
        -metrics: List
        -alert_thresholds: Dict
        -client: HTTP
        -logger
        +measure_latency()
        +check_availability()
        +get_metrics_summary()
        +record_metric()
        +set_alert_threshold(metric, value)
        +check_thresholds()
    }

    class MonitoringService {
        -api_monitor: APIMonitor
        -is_running: bool
        -check_interval: int
        -logger
        +__init__(check_interval)
        +run()
        +stop()
        +check_api_health()
        +handle_alerts()
    }
```

## Composants Principaux

### TradingBot
- Point d'entrée principal du système
- Gère le cycle de vie du bot et la coordination des services
- Implémente le pattern Singleton pour garantir une seule instance
- Utilise _process_symbol pour la mise à jour optimisée des données

### MarketUpdater
- Gère les mises à jour périodiques des données de marché
- Implémente un système de déduplication des mises à jour
- Maintient un timestamp de dernière mise à jour par symbole
- Gère les erreurs avec un système de comptage et retry
- Assure un arrêt propre avec shutdown_complete

### Interaction entre les composants
1. TradingBot initialise MarketUpdater avec les symboles configurés
2. MarketUpdater gère de manière autonome les mises à jour périodiques
3. TradingBot peut demander des mises à jour via _process_symbol
4. La déduplication assure qu'une seule mise à jour est effectuée dans l'intervalle configuré

## Optimisations
1. Déduplication des mises à jour :
   - Utilisation de timestamps pour éviter les mises à jour trop fréquentes
   - Coordination entre TradingBot et MarketUpdater
   
2. Gestion des erreurs :
   - Comptage des erreurs par symbole
   - Système de retry avec backoff
   - Logs détaillés pour le debugging

3. Performance :
   - Réduction des appels API inutiles
   - Optimisation des intervalles de mise à jour
   - Meilleure utilisation des ressources

## Structure des Données

```mermaid
graph TB
    subgraph "Structure de Données MongoDB"
        MD[Market Data Collection]
        IND[Indicators Collection]
        TR[Trades Collection]
        MON[Monitoring Collection]
        API[API Metrics Collection]
        BTR[Backtest Results Collection]
        STR[Strategy Config Collection]
        
        MD -->|Contient| MDD[Document]
        MDD -->|Champs| S1[symbol]
        MDD -->|Champs| T1[timestamp]
        MDD -->|Champs| D1[data]
        D1 -->|Contient| P[price]
        D1 -->|Contient| V[volume]
        D1 -->|Contient| RD[raw_data]
        
        IND -->|Contient| INDD[Document]
        INDD -->|Champs| S2[symbol]
        INDD -->|Champs| T2[timestamp]
        INDD -->|Champs| D2[indicators]
        D2 -->|Contient| RSI[rsi]
        D2 -->|Contient| MACD[macd]
        D2 -->|Contient| BB[bollinger]
        
        TR -->|Contient| TRD[Document]
        TRD -->|Champs| S3[symbol]
        TRD -->|Champs| T3[timestamp]
        TRD -->|Champs| D3[trade_data]
        D3 -->|Contient| Side[side]
        D3 -->|Contient| Size[size]
        D3 -->|Contient| Price[price]
        
        MON -->|Contient| MOND[Document]
        MOND -->|Champs| T4[timestamp]
        MOND -->|Champs| Status[status]
        MOND -->|Champs| Metrics[metrics]
        
        API -->|Contient| APID[Document]
        APID -->|Champs| T5[timestamp]
        APID -->|Champs| Latency[latency]
        APID -->|Champs| Success[success_rate]
        
        BTR -->|Contient| BTRD[Document]
        BTRD -->|Champs| S4[symbol]
        BTRD -->|Champs| T6[timestamp]
        BTRD -->|Champs| D4[backtest_data]
        D4 -->|Contient| PnL[pnl]
        D4 -->|Contient| Trades[trades]
        
        STR -->|Contient| STRD[Document]
        STRD -->|Champs| S5[symbol]
        STRD -->|Champs| T7[timestamp]
        STRD -->|Champs| D5[strategy_config]
        D5 -->|Contient| Paramètres[paramètres]
    end
```

## Description des Composants

### TradingBot
- Composant central qui orchestre tout le système
- Gère les cycles de trading et la coordination des services
- Maintient l'état global du système
- Gère les threads de trading, monitoring et mise à jour des données
- Implémente une gestion gracieuse de l'arrêt
- Logging détaillé des opérations

### MarketDataCollector
- Interface directe avec l'API Bybit
- Collecte les données de marché en temps réel
- Intègre l'analyse technique via TechnicalAnalysis
- Gère les formats de données spécifiques à Bybit
- Conversion des intervalles temporels
- Traitement et validation des données brutes

### TechnicalAnalysis
- Calcule les indicateurs techniques (RSI, MACD, Bollinger Bands)
- Fournit des signaux de trading
- Analyse les tendances du marché
- Génère des résumés d'analyse technique
- Validation des indicateurs calculés
- Support pour des périodes personnalisées

### MongoDBManager
- Gère toutes les opérations de base de données
- Maintient plusieurs collections pour différents types de données:
  * market_data: Données de marché brutes
  * indicators: Indicateurs techniques calculés
  * trades: Historique des trades
  * monitoring: Données de surveillance système
  * api_metrics: Métriques de l'API
  * backtest_results: Résultats des backtests
  * strategy_config: Configuration des stratégies
- Gère le nettoyage et l'optimisation des données
- Fournit des méthodes d'accès standardisées
- Validation des connexions
- Gestion propre des fermetures de connexion
- Logging des opérations de base de données
- Configuration via variables d'environnement
- Mise en place automatique des index pour l'optimisation

### APIMonitor & MonitoringService
- Surveille la santé de l'API Bybit
- Mesure la latence et la disponibilité
- Gère les alertes et les métriques
- Assure la fiabilité du système
- Seuils d'alerte configurables
- Intervalle de vérification paramétrable
- Logging des événements de monitoring

### MarketUpdater
- Met à jour les données de marché périodiquement
- Coordonne la collecte et le stockage des données
- Gère les erreurs de mise à jour avec système de retry configurable
- Maintient la fraîcheur des données
- Gestion gracieuse de l'arrêt avec timeout
- File d'attente pour les opérations de shutdown
- Configuration flexible des API keys
- Validation des données de marché
- Caractéristiques supplémentaires :
  * Suivi des erreurs par symbole via error_counts
  * Intervalle de mise à jour configurable (update_interval)
  * Nombre maximum de tentatives paramétrable (max_retries)
  * Vérification de la santé de l'API avant chaque mise à jour
  * Traitement des données avec pandas DataFrame
  * Intégration avec le système de monitoring
  * Gestion des timeouts et des arrêts propres
  * Support du mode testnet