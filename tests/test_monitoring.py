import pytest
import time
import os
from dotenv import load_dotenv
from src.monitoring.api_monitor import APIMonitor

@pytest.fixture
def monitor():
    """Fixture pour créer une instance du moniteur"""
    load_dotenv()
    return APIMonitor(testnet=True)  # Utiliser le testnet pour les tests

def test_api_availability(monitor):
    """Test de la disponibilité de l'API"""
    assert monitor.check_availability() is True

def test_api_latency(monitor):
    """Test de la mesure de latence"""
    latency = monitor.measure_latency(
        endpoint="/v5/market/tickers",
        method="get_tickers",
        category="spot",
        symbol="BTCUSDT"
    )
    assert latency is not None
    assert isinstance(latency, float)
    assert latency > 0

def test_rate_limits(monitor):
    """Test de la vérification des limites de taux"""
    limits = monitor.check_rate_limits()
    assert isinstance(limits, dict)
    assert 'status' in limits
    assert limits['status'] in ['OK', 'WARNING', 'CRITICAL']

def test_metrics_recording(monitor):
    """Test de l'enregistrement des métriques"""
    # Effectuer quelques appels API
    for _ in range(3):
        monitor.monitor_endpoint(
            endpoint="/v5/market/tickers",
            method="get_tickers",
            category="spot",
            symbol="BTCUSDT"
        )
        time.sleep(1)  # Attendre entre les appels
    
    # Vérifier le résumé des métriques
    summary = monitor.get_metrics_summary()
    assert isinstance(summary, dict)
    assert 'avg_latency' in summary
    assert 'max_latency' in summary
    assert 'min_latency' in summary
    assert 'total_requests' in summary
    assert summary['total_requests'] >= 3

def test_error_handling(monitor):
    """Test de la gestion des erreurs"""
    # Tester avec un endpoint invalide
    latency = monitor.measure_latency(
        endpoint="/invalid/endpoint",
        method="GET"
    )
    assert latency is None
    assert monitor.consecutive_failures > 0

def test_full_monitoring_cycle():
    """Test d'un cycle complet de monitoring"""
    # Créer une nouvelle instance pour ce test
    monitor = APIMonitor(testnet=True)
    
    print("\n=== Test du système de monitoring API Bybit ===\n")
    
    # Endpoints à tester
    endpoints = [
        {
            "endpoint": "/v5/market/tickers",
            "method": "get_tickers",
            "params": {"category": "spot", "symbol": "BTCUSDT"}
        },
        {
            "endpoint": "/v5/market/orderbook",
            "method": "get_orderbook",
            "params": {"category": "spot", "symbol": "BTCUSDT", "limit": 50}
        }
    ]
    
    for endpoint_config in endpoints:
        print(f"\nSurveillance de l'endpoint: {endpoint_config['endpoint']}")
        
        # Faire plusieurs mesures
        for _ in range(3):
            monitor.monitor_endpoint(
                endpoint=endpoint_config['endpoint'],
                method=endpoint_config['method'],
                **endpoint_config['params']
            )
            time.sleep(1)
        
        # Afficher le résumé
        summary = monitor.get_metrics_summary()
        print("\nRésumé des métriques:")
        print(f"Latence moyenne: {summary.get('avg_latency', 0):.2f}ms")
        print(f"Latence max: {summary.get('max_latency', 0):.2f}ms")
        print(f"Latence min: {summary.get('min_latency', 0):.2f}ms")
        print(f"Nombre total de requêtes: {summary.get('total_requests', 0)}")
        print(f"Taux d'erreur: {summary.get('error_rate', 0)*100:.2f}%")
        
        # Vérifier les limites de taux
        rate_limits = monitor.check_rate_limits()
        print(f"Statut des limites de taux: {rate_limits.get('status', 'N/A')}")

if __name__ == "__main__":
    test_full_monitoring_cycle()
