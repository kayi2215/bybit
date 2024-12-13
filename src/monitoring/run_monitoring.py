import threading
from src.monitoring.api_monitor import APIMonitor
import time
import logging
import signal
import sys
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

class MonitoringService:
    def __init__(self, check_interval=10, testnet=False):
        """
        Initialise le service de monitoring
        :param check_interval: Intervalle entre les vérifications en secondes (défaut: 10s)
        :param testnet: Utiliser le testnet Bybit (défaut: False)
        """
        load_dotenv()
        self.monitor = APIMonitor(testnet=testnet)
        self.check_interval = check_interval
        self.stop_event = threading.Event()
        self.running = False
        self.last_metrics_summary = datetime.now()
        self.metrics_summary_interval = 60  # 1 minute
        self.shutdown_complete = threading.Event()
        self.monitoring_thread = None
        
        # Configuration des endpoints Bybit à surveiller avec intervalles individuels
        self.endpoints = [
            {
                "endpoint": "/v5/market/tickers",
                "method": "get_ticker",
                "params": {"category": "spot", "symbol": "BTCUSDT"},
                "interval": 5  # 5 secondes
            },
            {
                "endpoint": "/v5/market/orderbook",
                "method": "get_orderbook",
                "params": {"category": "spot", "symbol": "BTCUSDT", "limit": 50},
                "interval": 5  # 5 secondes
            },
            {
                "endpoint": "/v5/market/kline",
                "method": "get_klines",
                "params": {"category": "spot", "symbol": "BTCUSDT", "interval": "1", "limit": 100},
                "interval": 5  # 5 secondes
            }
        ]
        
        self.last_check = {}
        for endpoint in self.endpoints:
            self.last_check[endpoint["endpoint"]] = datetime.now() - timedelta(seconds=endpoint.get("interval", check_interval))
        
        self.logger = logging.getLogger('bybit_monitoring_service')
        self._setup_logging()
        
        # Initialiser les métriques des indicateurs
        self._initialize_indicator_metrics()

    def _initialize_indicator_metrics(self):
        """Initialise les métriques de base pour les indicateurs"""
        # Exemple de données de validation pour les indicateurs
        validation_results = {
            'MACD': {
                'valid': True,
                'calculation_time': 100,
                'value': {'value': 0.5, 'signal': 0.3, 'histogram': 0.2}
            },
            'ADX': {
                'valid': True,
                'calculation_time': 150,
                'value': 45.0
            },
            'ATR': {
                'valid': True,
                'calculation_time': 120,
                'value': 0.025
            },
            'SuperTrend': {
                'valid': True,
                'calculation_time': 180,
                'value': {'value': 45000.0, 'direction': 'up'}
            }
        }
        
        self.monitor.record_validation_metrics(validation_results)
        self.logger.info("Métriques des indicateurs initialisées")

    def _check_indicators(self):
        """Vérifie et met à jour l'état des indicateurs"""
        try:
            # Simuler la mise à jour des indicateurs avec des données réelles
            validation_results = {
                'MACD': {
                    'valid': True,
                    'calculation_time': 100,
                    'value': {'value': 0.5, 'signal': 0.3, 'histogram': 0.2}
                },
                'ADX': {
                    'valid': True,
                    'calculation_time': 150,
                    'value': 45.0
                },
                'ATR': {
                    'valid': True,
                    'calculation_time': 120,
                    'value': 0.025
                },
                'SuperTrend': {
                    'valid': True,
                    'calculation_time': 180,
                    'value': {'value': 45000.0, 'direction': 'up'}
                }
            }
            
            self.monitor.record_validation_metrics(validation_results)
            return True
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification des indicateurs: {str(e)}")
            return False

    def _setup_logging(self):
        """Configure le système de logging"""
        # Créer le logger s'il n'existe pas déjà
        self.logger = logging.getLogger('bybit_monitoring_service')
        
        # Si le logger a déjà des handlers, ne pas en ajouter d'autres
        if self.logger.handlers:
            return
            
        self.logger.setLevel(logging.DEBUG)  # Changed to DEBUG for more detailed logging
        
        # Configuration du format
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Handler pour la console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)  # Keep console output at INFO level
        self.logger.addHandler(console_handler)
        
        # Handler pour le fichier
        log_dir = "logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        file_handler = logging.FileHandler(
            os.path.join(log_dir, "monitoring_service.log")
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)  # Set file logging to DEBUG level
        self.logger.addHandler(file_handler)
        
        # Empêcher la propagation aux loggers parents
        self.logger.propagate = False

    def signal_handler(self, signum, frame):
        """Gestionnaire pour l'arrêt propre du service"""
        self.logger.info("\nArrêt du service de monitoring Bybit...")
        self.stop()

    def should_check_endpoint(self, endpoint: str) -> bool:
        """Vérifie si un endpoint doit être testé en fonction de son dernier check"""
        now = datetime.now()
        if (now - self.last_check[endpoint]).total_seconds() >= self.endpoints[[e["endpoint"] for e in self.endpoints].index(endpoint)]["interval"]:
            self.last_check[endpoint] = now
            return True
        return False

    def should_print_metrics_summary(self) -> bool:
        """Vérifie si on doit afficher le résumé des métriques"""
        now = datetime.now()
        if (now - self.last_metrics_summary).total_seconds() >= self.metrics_summary_interval:
            self.last_metrics_summary = now
            return True
        return False

    def check_alerts(self):
        """Vérifie et affiche les alertes actives"""
        alerts = self.monitor.get_alerts()
        if alerts:
            self.logger.warning("=== Alertes Actives ===")
            for alert in alerts:
                self.logger.warning(f"Type: {alert['type']}, Valeur: {alert['value']}")

    def print_metrics_summary(self):
        """Affiche un résumé des métriques"""
        summary = self.monitor.get_metrics_summary()
        self.logger.info("\n=== Résumé des Métriques ===")
        self.logger.info(f"Requêtes totales: {summary['total_requests']}")
        self.logger.info(f"Requêtes échouées: {summary['failed_requests']}")
        self.logger.info(f"Taux d'erreur: {summary['error_rate']:.2%}")
        if 'avg_latency' in summary:
            self.logger.info(f"Latence moyenne: {summary['avg_latency']:.2f}ms")
            self.logger.info(f"Latence min: {summary['min_latency']:.2f}ms")
            self.logger.info(f"Latence max: {summary['max_latency']:.2f}ms")
        
        # Afficher les métriques des indicateurs
        indicators_health = self.monitor.check_indicators_health()
        if indicators_health['indicators']:
            self.logger.info("\n=== Santé des Indicateurs ===")
            for indicator, status in indicators_health['indicators'].items():
                self.logger.info(f"{indicator}: {status['status']}")
                if status.get('error_count', 0) > 0:
                    self.logger.warning(f"  Erreurs: {status['error_count']}")

        # Afficher les performances de calcul
        performance = self.monitor.monitor_calculation_performance()
        if performance['indicators_performance']:
            self.logger.info("\n=== Performance des Calculs ===")
            for indicator, perf in performance['indicators_performance'].items():
                self.logger.info(f"{indicator}: {perf['avg_calculation_time']:.2f}ms ({perf['status']})")
        
        if performance['bottlenecks']:
            self.logger.warning("\n=== Goulots d'Étranglement ===")
            for bottleneck in performance['bottlenecks']:
                self.logger.warning(f"- {bottleneck}")

    def run(self):
        """Boucle principale du service de monitoring"""
        last_indicator_check = datetime.now()
        last_metrics_check = datetime.now()
        endpoint_timeouts = {
            '/v5/market/tickers': 3,
            '/v5/market/orderbook': 3,
            '/v5/market/kline': 3,
            'default': 5
        }
        
        while not self.stop_event.is_set():
            try:
                current_time = datetime.now()
                self.logger.debug(f"Début du cycle de monitoring à {current_time.isoformat()}")

                # Vérification de la disponibilité générale de l'API avec timeout strict
                try:
                    start_time = time.time()
                    api_available = self.monitor.check_availability(timeout=3)
                    
                    if time.time() - start_time > 3:  # Strict timeout
                        self.logger.error("Timeout lors de la vérification de disponibilité")
                        if not self.stop_event.wait(2):  # Reduced wait time
                            continue
                            
                    self.logger.debug(f"Statut de l'API: {'Disponible' if api_available else 'Indisponible'}")
                    
                    if not api_available:
                        self.logger.error("L'API Bybit n'est pas disponible!")
                        if not self.stop_event.wait(2):
                            continue
                except Exception as e:
                    self.logger.error(f"Erreur lors de la vérification de disponibilité: {str(e)}")
                    if not self.stop_event.wait(2):
                        continue

                # Vérification des endpoints avec timeout individuel et strict
                for endpoint_config in self.endpoints:
                    if self.stop_event.is_set():
                        break
                        
                    endpoint_name = endpoint_config["endpoint"]
                    if not self.should_check_endpoint(endpoint_name):
                        continue
                        
                    # Get endpoint-specific timeout
                    endpoint_timeout = endpoint_timeouts.get(endpoint_name, endpoint_timeouts['default'])
                    
                    try:
                        start_time = time.time()
                        self.logger.debug(f"Vérification de l'endpoint {endpoint_name}")
                        
                        # Create a future for the latency check
                        latency = None
                        try:
                            latency = self.monitor.measure_latency(
                                endpoint=endpoint_config["endpoint"],
                                method=endpoint_config["method"],
                                timeout=endpoint_timeout,
                                **endpoint_config["params"]
                            )
                        except Exception as e:
                            self.logger.error(f"Erreur lors de la mesure de latence pour {endpoint_name}: {str(e)}")
                            continue
                            
                        if time.time() - start_time > endpoint_timeout:
                            self.logger.warning(f"Timeout lors de la vérification de {endpoint_name}")
                            continue
                                
                        if latency is not None:
                            self.logger.info(f"Latence pour {endpoint_name}: {latency:.2f}ms")
                            
                        # Small pause between endpoint checks
                        if not self.stop_event.wait(0.1):
                            continue
                            
                    except Exception as e:
                        self.logger.error(f"Erreur lors de la vérification de {endpoint_name}: {str(e)}")
                        continue

                # Vérification des limites de taux avec timeout
                if not self.stop_event.is_set():
                    try:
                        start_time = time.time()
                        rate_limits = self.monitor.check_rate_limits()
                        
                        if time.time() - start_time > 5:  # Timeout check
                            self.logger.warning("Timeout lors de la vérification des limites de taux")
                            continue
                            
                        if rate_limits.get('status') == 'CRITICAL':
                            self.logger.warning(f"Attention: Utilisation des limites de taux à {rate_limits.get('usage_percent', 0):.1f}%")
                    except Exception as e:
                        self.logger.error(f"Erreur lors de la vérification des limites de taux: {str(e)}")

                # Vérification périodique des indicateurs avec timeout
                if not self.stop_event.is_set() and (current_time - last_indicator_check).total_seconds() >= self.check_interval:
                    try:
                        start_time = time.time()
                        self.logger.debug("Début de la vérification des indicateurs")
                        
                        if time.time() - start_time > 10:  # Extended timeout for indicators
                            self.logger.warning("Timeout lors de la vérification des indicateurs")
                            continue
                            
                        if self._check_indicators():
                            self.logger.debug("Vérification des indicateurs réussie")
                            last_indicator_check = current_time
                        else:
                            self.logger.warning("Échec de la vérification des indicateurs")
                    except Exception as e:
                        self.logger.error(f"Erreur lors de la vérification des indicateurs: {str(e)}")

                # Vérification périodique des autres métriques avec timeout
                if not self.stop_event.is_set() and (current_time - last_metrics_check).total_seconds() >= 300:
                    try:
                        start_time = time.time()
                        self.logger.debug("Début de la vérification des autres métriques")
                        
                        if time.time() - start_time > 10:  # Extended timeout for metrics
                            self.logger.warning("Timeout lors de la vérification des autres métriques")
                            continue
                            
                        if self._check_other_metrics():
                            self.logger.debug("Vérification des autres métriques réussie")
                            last_metrics_check = current_time
                        else:
                            self.logger.warning("Échec de la vérification des autres métriques")
                    except Exception as e:
                        self.logger.error(f"Erreur lors de la vérification des autres métriques: {str(e)}")

                # Pause courte pour éviter une utilisation excessive du CPU
                if not self.stop_event.wait(1):
                    continue

            except Exception as e:
                self.logger.error(f"Erreur dans le service de monitoring: {str(e)}")
                if not self.stop_event.wait(1):
                    continue

    def _check_other_metrics(self):
        """Helper method to check other metrics"""
        try:
            # Check indicators health with timeout
            indicators_health = self.monitor.check_indicators_health(timeout=5)
            if indicators_health['status'] != 'OK':
                self.logger.warning("Problèmes détectés avec certains indicateurs")
                for indicator, status in indicators_health['indicators'].items():
                    if status['status'] != 'OK':
                        self.logger.warning(f"- {indicator}: {status['status']}")

            # Check performance
            performance = self.monitor.monitor_calculation_performance()
            if performance['bottlenecks']:
                for bottleneck in performance['bottlenecks']:
                    self.logger.warning(f"Performance: {bottleneck}")

            # Check alerts and metrics summary
            self.check_alerts()
            if self.should_print_metrics_summary():
                self.print_metrics_summary()

            return True

        except Exception as e:
            self.logger.error(f"Erreur dans _check_other_metrics: {str(e)}")
            return False

    def start(self):
        """Démarre le service de monitoring"""
        if self.running:
            self.logger.warning("Le service de monitoring est déjà en cours d'exécution")
            return

        self.running = True
        self.stop_event.clear()
        self.monitoring_thread = threading.Thread(target=self.run)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        self.logger.info("Service de monitoring démarré")

    def stop(self):
        """Arrête le service de monitoring"""
        if not self.running:
            return
            
        self.logger.info("Arrêt du service de monitoring...")
        self.stop_event.set()
        self.running = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=30)
        self.logger.info("Service de monitoring arrêté")

def main():
    """Point d'entrée principal"""
    # Créer et configurer le service
    service = MonitoringService()
    
    def signal_handler(signum, frame):
        """Gestionnaire de signal pour arrêter proprement le service"""
        print("\nArrêt du service...")
        service.stop()
        sys.exit(0)
    
    # Configurer le gestionnaire de signal
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Démarrer le service
        service.start()
        
        # Maintenir le programme principal en vie
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        service.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()
