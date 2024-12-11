from src.monitoring.api_monitor import APIMonitor
import time

def test_api_monitoring():
    # Initialiser le moniteur
    monitor = APIMonitor()
    
    # Points de terminaison à surveiller
    endpoints = [
        "https://api.binance.com/api/v3/ping",  # Endpoint de ping
        "https://api.binance.com/api/v3/time",  # Endpoint de temps serveur
        "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"  # Prix BTC
    ]
    
    print("=== Test du système de monitoring API ===\n")
    
    # Tester chaque endpoint
    for endpoint in endpoints:
        print(f"\nSurveillance de l'endpoint: {endpoint}")
        
        # Faire plusieurs mesures
        for _ in range(3):
            monitor.monitor_endpoint(endpoint)
            time.sleep(1)  # Attendre 1 seconde entre les mesures
        
        # Afficher le résumé des métriques
        summary = monitor.get_metrics_summary()
        print("\nRésumé des métriques:")
        print(f"Latence moyenne: {summary.get('avg_latency', 0):.2f}ms")
        print(f"Latence max: {summary.get('max_latency', 0):.2f}ms")
        print(f"Latence min: {summary.get('min_latency', 0):.2f}ms")
        print(f"Nombre total de requêtes: {summary.get('total_requests', 0)}")
        print(f"Taux d'erreur: {summary.get('error_rate', 0)*100:.2f}%")

if __name__ == "__main__":
    test_api_monitoring()
