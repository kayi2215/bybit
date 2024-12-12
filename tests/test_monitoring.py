import pytest
import time
import os
from unittest.mock import patch, Mock, MagicMock
from dotenv import load_dotenv
from src.monitoring.api_monitor import APIMonitor

# Fixtures communs
@pytest.fixture
def mock_response():
    """Fixture pour créer une réponse mock"""
    return {
        "retCode": 0,
        "result": {
            "symbol": "BTCUSDT",
            "price": "50000",
            "time": int(time.time() * 1000)
        }
    }

@pytest.fixture
def mock_wallet_response():
    """Fixture pour la réponse du wallet"""
    return {
        "retCode": 0,
        "result": {
            "list": [
                {
                    "totalEquity": "1000",
                    "accountType": "UNIFIED",
                    "totalWalletBalance": "1000",
                    "accountIMRate": "0.1",
                    "totalMarginBalance": "1000"
                }
            ]
        }
    }

@pytest.fixture
def monitor():
    """Fixture pour créer une instance du moniteur"""
    load_dotenv()
    monitor = APIMonitor(testnet=True)
    # Initialiser les compteurs pour les tests
    monitor.total_requests = 0
    monitor.failed_requests = 0
    return monitor

@pytest.fixture
def mock_time():
    """Fixture pour mocker time.time"""
    with patch('time.time', autospec=True) as mock:
        mock.return_value = 1000
        yield mock

class TestUnitMonitoring:
    """Tests unitaires pour le monitoring"""
    
    def test_check_availability_success(self, monitor):
        """Test de la disponibilité de l'API avec mock"""
        with patch.object(monitor.client, 'get_tickers') as mock_get:
            mock_get.return_value = {"retCode": 0, "result": {}}
            assert monitor.check_availability() is True
            mock_get.assert_called_once()

    def test_check_availability_failure(self, monitor):
        """Test de la non-disponibilité de l'API"""
        with patch.object(monitor.client, 'get_tickers') as mock_get:
            mock_get.return_value = {"retCode": 1, "result": {}}
            assert monitor.check_availability() is False
            mock_get.assert_called_once()

    def test_measure_latency(self, monitor, mock_response, mock_wallet_response):
        """Test de la mesure de latence avec mock"""
        with patch('time.time', side_effect=[1000, 1000.5] + [1000.5] * 10), \
             patch.object(monitor.client, 'get_tickers', return_value=mock_response), \
             patch.object(monitor.client, 'get_wallet_balance', return_value=mock_response):
            
            latency = monitor.measure_latency(
                endpoint="/v5/market/tickers",
                method="get_tickers",
                category="spot",
                symbol="BTCUSDT"
            )
            
            assert latency == 500.0  # 500ms
            assert isinstance(latency, float)

    def test_alert_thresholds(self, monitor):
        """Test des seuils d'alerte"""
        monitor.alert_thresholds = {
            'latency': 1000,  # 1 seconde
            'error_rate': 0.1,  # 10%
            'consecutive_failures': 3
        }
        
        assert monitor.alert_thresholds['latency'] == 1000
        assert monitor.alert_thresholds['error_rate'] == 0.1
        assert monitor.alert_thresholds['consecutive_failures'] == 3

    def test_high_latency_alert(self, monitor, mock_response, mock_wallet_response):
        """Test des alertes de latence élevée"""
        with patch('time.time', side_effect=[1000, 1002] + [1002] * 10), \
             patch.object(monitor.client, 'get_tickers', return_value=mock_response), \
             patch.object(monitor.client, 'get_wallet_balance', return_value=mock_wallet_response):
            
            monitor.alert_thresholds['latency'] = 1000  # Seuil à 1 seconde
            latency = monitor.measure_latency(
                endpoint="/v5/market/tickers",
                method="get_tickers",
                category="spot",
                symbol="BTCUSDT"
            )
            
            assert latency == 2000.0  # 2000ms
            assert len(monitor.metrics) > 0
            assert any(m['type'] == 'latency' and m['value'] > monitor.alert_thresholds['latency'] 
                      for m in monitor.metrics)

    def test_consecutive_failures_alert(self, monitor):
        """Test des alertes d'échecs consécutifs"""
        monitor.alert_thresholds['consecutive_failures'] = 2
        monitor.consecutive_failures = 3
        
        alerts = monitor.get_alerts()
        assert any(alert['type'] == 'consecutive_failures' for alert in alerts)

    def test_error_rate_alert(self, monitor):
        """Test des alertes de taux d'erreur"""
        monitor.alert_thresholds['error_rate'] = 0.2  # 20%
        monitor.total_requests = 10
        monitor.failed_requests = 3  # 30% d'erreurs
        
        alerts = monitor.get_alerts()
        assert any(alert['type'] == 'high_error_rate' for alert in alerts)

    def test_metrics_recording(self, monitor, mock_response, mock_wallet_response):
        """Test de l'enregistrement des métriques"""
        with patch('time.time', side_effect=[1000, 1000.1] * 5 + [1000.1] * 10), \
             patch.object(monitor.client, 'get_tickers', return_value=mock_response), \
             patch.object(monitor.client, 'get_wallet_balance', return_value=mock_wallet_response):
            
            # Enregistrer deux métriques
            for _ in range(2):
                latency = monitor.measure_latency(
                    endpoint="/v5/market/tickers",
                    method="get_tickers",
                    category="spot",
                    symbol="BTCUSDT"
                )
                assert abs(latency - 100.0) < 0.1  # Tolérance de 0.1ms
            
            assert len(monitor.metrics) == 2
            assert all(m['type'] == 'latency' for m in monitor.metrics)
            assert all(abs(m['value'] - 100.0) < 0.1 for m in monitor.metrics)

    def test_monitor_endpoint_success(self, monitor, mock_response, mock_wallet_response):
        """Test du monitoring d'un endpoint avec succès"""
        monitor.metrics = []  # Réinitialiser les métriques
        with patch('time.time', side_effect=[1000, 1000.1] + [1000.1] * 10), \
             patch.object(monitor.client, 'get_tickers', return_value=mock_response), \
             patch.object(monitor.client, 'get_wallet_balance', return_value=mock_wallet_response), \
             patch.object(monitor, 'check_availability', return_value=True):
            
            monitor.monitor_endpoint(
                endpoint="/v5/market/tickers",
                method="get_tickers",
                category="spot",
                symbol="BTCUSDT"
            )
            
            assert monitor.total_requests == 1
            assert monitor.failed_requests == 0
            assert len(monitor.metrics) == 1

    def test_monitor_endpoint_failure(self, monitor):
        """Test du monitoring d'un endpoint avec échec"""
        monitor.total_requests = 0
        monitor.failed_requests = 0
        
        with patch('time.time', side_effect=[1000, 1000.1] * 5), \
             patch.object(monitor.client, 'get_tickers', side_effect=Exception("API Error")), \
             patch.object(monitor, 'check_availability', return_value=False):
            
            monitor.monitor_endpoint(
                endpoint="/v5/market/tickers",
                method="get_tickers",
                category="spot",
                symbol="BTCUSDT"
            )
            
            assert monitor.total_requests == 0  # La requête n'est pas comptée car l'endpoint n'est pas disponible
            assert monitor.failed_requests == 0
            assert len(monitor.metrics) == 0

    def test_request_counters(self, monitor, mock_response, mock_wallet_response):
        """Test des compteurs de requêtes"""
        monitor.total_requests = 0
        monitor.failed_requests = 0
        
        # Test requête réussie
        with patch('time.time', side_effect=[0, 0.1, 0.2, 0.3, 0.4, 0.5]), \
             patch.object(monitor.client, 'get_tickers', return_value=mock_response), \
             patch.object(monitor.client, 'get_wallet_balance', return_value=mock_wallet_response), \
             patch.object(monitor, 'check_availability', return_value=True):
            
            monitor.monitor_endpoint("/v5/market/tickers", "get_tickers", category="spot", symbol="BTCUSDT")
            assert monitor.total_requests == 1
            assert monitor.failed_requests == 0

        # Test requête échouée
        with patch('time.time', side_effect=[1.0, 1.1, 1.2, 1.3, 1.4, 1.5]), \
             patch.object(monitor.client, 'get_tickers', side_effect=Exception("API Error")), \
             patch.object(monitor, 'check_availability', return_value=False):
            
            monitor.monitor_endpoint("/v5/market/tickers", "get_tickers", category="spot", symbol="BTCUSDT")
            assert monitor.total_requests == 1  # La requête échouée ne doit pas être comptée
            assert monitor.failed_requests == 0  # La requête n'a pas été tentée car l'endpoint n'était pas disponible

    def test_rate_limits_warning(self, monitor, mock_response, mock_wallet_response):
        """Test des avertissements de limites de taux"""
        with patch('time.time', side_effect=[1000, 1000.1] + [1000.1] * 10), \
             patch.object(monitor.client, 'get_tickers', return_value=mock_response), \
             patch.object(monitor.client, 'get_wallet_balance', return_value=mock_wallet_response):
            
            monitor.monitor_endpoint(
                endpoint="/v5/market/tickers",
                method="get_tickers",
                category="spot",
                symbol="BTCUSDT"
            )
            
            # Vérifier les rate limits
            limits = monitor.check_rate_limits()
            assert isinstance(limits, dict)
            assert 'status' in limits
            assert limits['status'] in ['OK', 'CRITICAL']
            assert 'usage_percent' in limits
            assert 'weight' in limits
            assert 'limit' in limits

    def test_metrics_summary_empty(self, monitor):
        """Test du résumé des métriques quand il n'y a pas de données"""
        summary = monitor.get_metrics_summary()
        assert isinstance(summary, dict)
        assert summary.get('total_requests', 0) == 0
        assert summary.get('error_rate', 0) == 0

    def test_metrics_summary_with_data(self, monitor, mock_response, mock_wallet_response):
        """Test du résumé des métriques avec données"""
        with patch('time.time', side_effect=[1000, 1000.1] * 5 + [1000.1] * 10), \
             patch.object(monitor.client, 'get_tickers', return_value=mock_response), \
             patch.object(monitor.client, 'get_wallet_balance', return_value=mock_wallet_response):
            
            # Enregistrer deux métriques
            for _ in range(2):
                latency = monitor.measure_latency(
                    endpoint="/v5/market/tickers",
                    method="get_tickers",
                    category="spot",
                    symbol="BTCUSDT"
                )
                assert abs(latency - 100.0) < 0.1  # Tolérance de 0.1ms
            
            summary = monitor.get_metrics_summary()
            assert isinstance(summary, dict)
            assert summary['total_requests'] > 0
            assert 'avg_latency' in summary
            assert 'max_latency' in summary
            assert 'min_latency' in summary

class TestIntegrationMonitoring:
    """Tests d'intégration pour le monitoring"""
    
    def test_full_monitoring_cycle(self, monitor):
        """Test d'un cycle complet de monitoring avec l'API réelle"""
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
            # Faire plusieurs mesures
            for _ in range(2):
                monitor.monitor_endpoint(
                    endpoint=endpoint_config['endpoint'],
                    method=endpoint_config['method'],
                    **endpoint_config['params']
                )
                time.sleep(1)
            
            # Vérifier les métriques
            summary = monitor.get_metrics_summary()
            assert isinstance(summary, dict)
            assert all(key in summary for key in ['avg_latency', 'max_latency', 'min_latency'])
            assert summary['total_requests'] > 0

    def test_rate_limits_integration(self, monitor):
        """Test d'intégration des limites de taux"""
        limits = monitor.check_rate_limits()
        assert isinstance(limits, dict)
        assert 'status' in limits
        assert limits['status'] in ['OK', 'WARNING', 'CRITICAL']

if __name__ == "__main__":
    pytest.main(["-v", __file__])
