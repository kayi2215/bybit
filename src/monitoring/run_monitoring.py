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
    def __init__(self, check_interval=60, testnet=False):
        """
        Initialise le service de monitoring
        :param check_interval: Intervalle entre les vérifications en secondes (défaut: 60s)
        :param testnet: Utiliser le testnet Bybit (défaut: False)
        """
        load_dotenv()
        self.monitor = APIMonitor(testnet=testnet)
        self.check_interval = check_interval
        self.stop_event = threading.Event()
        self.running = False
        self.last_metrics_summary = datetime.now()
        self.metrics_summary_interval = 300  # 5 minutes
        self.shutdown_complete = threading.Event()  # Nouvel événement pour la synchronisation
        self.monitoring_thread = None
        
        # Configuration des endpoints Bybit à surveiller
        self.endpoints = [
            {
                "endpoint": "/v5/market/tickers",
                "method": "get_ticker",
                "params": {"category": "spot", "symbol": "BTCUSDT"}
            },
            {
                "endpoint": "/v5/market/orderbook",
                "method": "get_orderbook",
                "params": {"category": "spot", "symbol": "BTCUSDT", "limit": 50}
            },
            {
                "endpoint": "/v5/market/kline",
                "method": "get_klines",
                "params": {"category": "spot", "symbol": "BTCUSDT", "interval": "1", "limit": 100}
            }
        ]
        
        self.last_check = {}
        for endpoint in self.endpoints:
            self.last_check[endpoint["endpoint"]] = datetime.now() - timedelta(seconds=check_interval)
        
        self.logger = logging.getLogger('bybit_monitoring_service')
        self._setup_logging()

    def _setup_logging(self):
        """Configure le système de logging"""
        # Créer le logger s'il n'existe pas déjà
        self.logger = logging.getLogger('bybit_monitoring_service')
        
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
            os.path.join(log_dir, "monitoring_service.log")
        )
        file_handler.setFormatter(formatter)
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
        if (now - self.last_check[endpoint]).total_seconds() >= self.check_interval:
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

    def run(self):
        """Lance le service de monitoring en continu"""
        self.running = True
        self.shutdown_complete.clear()  # Réinitialiser l'événement de fin
        
        self.logger.info(f"Service de monitoring Bybit démarré - Intervalle de vérification: {self.check_interval}s")
        self.logger.info("Appuyez sur Ctrl+C pour arrêter le service")
        
        while not self.stop_event.wait(1):  # Attendre 1 seconde ou jusqu'à ce que stop_event soit set
            try:
                # Vérification de la disponibilité générale de l'API
                if not self.monitor.check_availability():
                    self.logger.error("L'API Bybit n'est pas disponible!")
                    time.sleep(self.check_interval)
                    continue

                # Vérification des endpoints
                for endpoint_config in self.endpoints:
                    if self.stop_event.is_set():  # Vérifier si on doit s'arrêter
                        break
                    
                    endpoint = endpoint_config["endpoint"]
                    if self.should_check_endpoint(endpoint):
                        self.logger.info(f"Vérification de l'endpoint: {endpoint}")
                        
                        # Mesure de la latence
                        latency = self.monitor.measure_latency(
                            endpoint=endpoint,
                            method=endpoint_config["method"],
                            **endpoint_config["params"]
                        )
                        
                        if latency is not None:
                            self.logger.info(f"Latence pour {endpoint}: {latency:.2f}ms")
                        
                        # Vérification des limites de taux
                        rate_limits = self.monitor.check_rate_limits()
                        if rate_limits.get('status') == 'CRITICAL':
                            self.logger.warning(f"Attention: Utilisation des limites de taux à {rate_limits.get('usage_percent', 0):.1f}%")
                
                if self.stop_event.is_set():  # Vérifier si on doit s'arrêter
                    break
                
                # Vérification des alertes
                self.check_alerts()
                
                # Affichage périodique du résumé des métriques
                if self.should_print_metrics_summary():
                    self.print_metrics_summary()
                
            except Exception as e:
                self.logger.error(f"Erreur dans le service de monitoring: {str(e)}")
                time.sleep(self.check_interval)
        
        self.running = False
        self.logger.info("Service de monitoring arrêté")
        self.shutdown_complete.set()  # Signaler que l'arrêt est terminé

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
