import time
from monitoring.api_monitor import APIMonitor
import signal
import sys
from datetime import datetime, timedelta

class MonitoringService:
    def __init__(self, check_interval: int = 60):
        """
        Initialise le service de monitoring
        :param check_interval: Intervalle entre les vérifications en secondes (défaut: 60s)
        """
        self.monitor = APIMonitor()
        self.check_interval = check_interval
        self.running = False
        self.endpoints = [
            "https://api.binance.com/api/v3/ping",
            "https://api.binance.com/api/v3/time",
            "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        ]
        self.last_check = {}
        for endpoint in self.endpoints:
            self.last_check[endpoint] = datetime.now() - timedelta(seconds=check_interval)

    def signal_handler(self, signum, frame):
        """Gestionnaire pour l'arrêt propre du service"""
        print("\nArrêt du service de monitoring...")
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
        
        print(f"Service de monitoring démarré - Intervalle de vérification: {self.check_interval}s")
        print("Appuyez sur Ctrl+C pour arrêter le service")
        
        while self.running:
            for endpoint in self.endpoints:
                if self.should_check_endpoint(endpoint):
                    try:
                        self.monitor.monitor_endpoint(endpoint)
                    except Exception as e:
                        print(f"Erreur lors du monitoring de {endpoint}: {str(e)}")
            
            # Petite pause pour éviter de surcharger le CPU
            time.sleep(1)

        print("Service de monitoring arrêté")

if __name__ == "__main__":
    # Créer et démarrer le service
    service = MonitoringService(check_interval=60)  # Vérifie chaque endpoint toutes les 60 secondes
    service.run()
