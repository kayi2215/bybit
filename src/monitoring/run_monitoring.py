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
        self.running = False
        
        # Configuration des endpoints Bybit à surveiller
        self.endpoints = [
            {
                "endpoint": "/v5/market/tickers",
                "method": "get_tickers",
                "params": {"category": "spot", "symbol": "BTCUSDT"}
            },
            {
                "endpoint": "/v5/market/orderbook",
                "method": "get_orderbook",
                "params": {"category": "spot", "symbol": "BTCUSDT", "limit": 50}
            },
            {
                "endpoint": "/v5/market/kline",
                "method": "get_kline",
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

    def signal_handler(self, signum, frame):
        """Gestionnaire pour l'arrêt propre du service"""
        self.logger.info("\nArrêt du service de monitoring Bybit...")
        self.running = False

    def should_check_endpoint(self, endpoint: str) -> bool:
        """Vérifie si un endpoint doit être testé en fonction de son dernier check"""
        now = datetime.now()
        if (now - self.last_check[endpoint]).total_seconds() >= self.check_interval:
            self.last_check[endpoint] = now
            return True
        return False

    def run(self):
        """Lance le service de monitoring en continu"""
        self.running = True
        
        # Configuration du gestionnaire de signal pour Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)
        
        self.logger.info(f"Service de monitoring Bybit démarré - Intervalle de vérification: {self.check_interval}s")
        self.logger.info("Appuyez sur Ctrl+C pour arrêter le service")
        
        while self.running:
            try:
                for endpoint_config in self.endpoints:
                    endpoint = endpoint_config["endpoint"]
                    if self.should_check_endpoint(endpoint):
                        self.logger.info(f"Vérification de l'endpoint: {endpoint}")
                        
                        # Monitoring de l'endpoint
                        self.monitor.monitor_endpoint(
                            endpoint=endpoint,
                            method=endpoint_config["method"],
                            **endpoint_config["params"]
                        )
                        
                        # Vérification des limites de taux
                        rate_limits = self.monitor.check_rate_limits()
                        if rate_limits.get('status') == 'CRITICAL':
                            self.logger.warning("Attention: Limites de taux critiques!")
                
                # Obtenir et logger le résumé des métriques
                summary = self.monitor.get_metrics_summary()
                if summary:
                    self.logger.info(f"Résumé des métriques: {summary}")
                
                time.sleep(1)  # Petite pause pour éviter une utilisation excessive du CPU
                
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle de monitoring: {str(e)}")
                time.sleep(5)  # Attendre un peu plus longtemps en cas d'erreur

def main():
    # Charger les variables d'environnement
    load_dotenv()
    
    # Détecter l'environnement
    use_testnet = os.getenv('USE_TESTNET', 'False').lower() == 'true'
    check_interval = int(os.getenv('MONITOR_CHECK_INTERVAL', '60'))
    
    # Créer et démarrer le service
    service = MonitoringService(
        check_interval=check_interval,
        testnet=use_testnet
    )
    service.run()

if __name__ == "__main__":
    main()
