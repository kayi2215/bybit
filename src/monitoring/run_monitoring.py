import threading
from api_monitor import APIMonitor
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
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        
        # Handler pour la console
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)
        
        # Handler pour le fichier
        log_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        fh = logging.FileHandler(os.path.join(log_dir, 'bybit_api_monitoring.log'))
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

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

    def stop(self):
        """Arrête le service de monitoring"""
        self.logger.info("Arrêt du service de monitoring Bybit...")
        self.stop_event.set()
        # Attendre que le service soit complètement arrêté (timeout de 10 secondes)
        self.shutdown_complete.wait(timeout=10)

def main():
    """Point d'entrée principal"""
    # Paramètres par défaut
    check_interval = int(os.getenv('MONITORING_INTERVAL', '60'))  # 60 secondes par défaut
    testnet = os.getenv('USE_TESTNET', 'true').lower() == 'true'  # Testnet par défaut
    
    # Création du service
    service = MonitoringService(check_interval=check_interval, testnet=testnet)
    
    # Configuration du gestionnaire de signal dans le thread principal
    def signal_handler(signum, frame):
        service.stop()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Démarrage du service
    service.run()

if __name__ == "__main__":
    main()
