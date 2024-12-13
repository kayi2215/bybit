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
    monitor.total_requests = 0
    monitor.failed_requests = 0
    monitor.metrics = []
    return monitor

class TestAPIMonitor:
    """Tests pour le monitoring de l'API"""

    def test_initialization(self, monitor):
        """Test de l'initialisation du moniteur"""
        assert monitor.exchange == "bybit"
        assert monitor.testnet is True
        assert monitor.total_requests == 0
        assert monitor.failed_requests == 0
        assert isinstance(monitor.alert_thresholds, dict)
        assert monitor.consecutive_failures == 0

    def test_is_valid_response(self, monitor, mock_response):
        """Test de la validation des réponses"""
        assert monitor.is_valid_response(mock_response) is True
        assert monitor.is_valid_response({"retCode": 1}) is False
        assert monitor.is_valid_response(None) is False
        assert monitor.is_valid_response({}) is False

    def test_measure_latency_success(self, monitor, mock_response):
        """Test de la mesure de latence avec succès"""
        with patch('time.time', side_effect=[1000, 1000.5]), \
             patch.object(monitor.client, 'get_tickers', return_value=mock_response):
            
            latency = monitor.measure_latency("/v5/market/tickers", "get_ticker")
            assert isinstance(latency, float)
            assert latency == 500.0  # 500ms
            assert monitor.consecutive_failures == 0
            assert len([m for m in monitor.metrics if m['type'] == 'latency']) == 1

    def test_measure_latency_failure(self, monitor):
        """Test de la mesure de latence avec échec"""
        with patch('time.time', side_effect=[1000, 1000.5, 1000.5, 1000.5]), \
             patch.object(monitor.client, 'get_tickers', return_value={"retCode": 1}):
            
            latency = monitor.measure_latency("/v5/market/tickers", "get_ticker")
            assert latency is None
            assert monitor.consecutive_failures == 1
            assert len([m for m in monitor.metrics if m['type'] == 'error']) == 1

    def test_check_availability(self, monitor, mock_response):
        """Test de la vérification de disponibilité"""
        with patch.object(monitor.client, 'get_tickers', return_value=mock_response):
            assert monitor.check_availability() is True
            assert len([m for m in monitor.metrics if m['type'] == 'availability']) == 1

    def test_check_rate_limits(self, monitor, mock_wallet_response):
        """Test de la vérification des limites de taux"""
        with patch.object(monitor.client, 'get_wallet_balance', return_value=mock_wallet_response):
            result = monitor.check_rate_limits()
            assert isinstance(result, dict)
            assert 'status' in result
            assert 'usage_percent' in result
            assert len([m for m in monitor.metrics if m['type'] == 'rate_limit']) == 1

    def test_record_metric(self, monitor):
        """Test de l'enregistrement des métriques"""
        monitor.record_metric('test', 100.0, '/test')
        assert len(monitor.metrics) == 1
        metric = monitor.metrics[0]
        assert metric['type'] == 'test'
        assert metric['value'] == 100.0
        assert metric['endpoint'] == '/test'
        assert metric['exchange'] == 'bybit'
        assert metric['testnet'] is True

    def test_get_alerts_latency(self, monitor):
        """Test des alertes de latence"""
        monitor.alert_thresholds['latency'] = 100
        monitor.record_metric('latency', 200.0, '/test')
        alerts = monitor.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]['type'] == 'latency'
        assert alerts[0]['value'] == 200.0

    def test_get_alerts_error_rate(self, monitor):
        """Test des alertes de taux d'erreur"""
        monitor.alert_thresholds['error_rate'] = 0.1
        monitor.total_requests = 10
        monitor.failed_requests = 2
        alerts = monitor.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]['type'] == 'error_rate'
        assert alerts[0]['value'] == 0.2

    def test_get_alerts_consecutive_failures(self, monitor):
        """Test des alertes d'échecs consécutifs"""
        monitor.alert_thresholds['consecutive_failures'] = 3
        monitor.consecutive_failures = 4
        alerts = monitor.get_alerts()
        assert len(alerts) == 1
        assert alerts[0]['type'] == 'consecutive_failures'
        assert alerts[0]['value'] == 4

    def test_get_metrics_summary(self, monitor):
        """Test du résumé des métriques"""
        monitor.record_metric('latency', 100.0, '/test')
        monitor.record_metric('latency', 200.0, '/test')
        monitor.total_requests = 2
        monitor.failed_requests = 1
        
        summary = monitor.get_metrics_summary()
        assert isinstance(summary, dict)
        assert summary['total_requests'] == 2
        assert summary['failed_requests'] == 1
        assert summary['error_rate'] == 0.5
        assert summary['avg_latency'] == 150.0
        assert summary['min_latency'] == 100.0
        assert summary['max_latency'] == 200.0

    def test_error_handling(self, monitor):
        """Test de la gestion des erreurs"""
        with patch.object(monitor.client, 'get_tickers', side_effect=Exception("Test error")):
            result = monitor.check_availability()
            assert result is False
            assert monitor.consecutive_failures == 1
            assert len([m for m in monitor.metrics if m['type'] == 'availability' and m['value'] == 0]) == 1

    def test_check_indicators_health(self, monitor):
        """Test de la vérification de la santé des indicateurs"""
        # Simuler des métriques de validation
        monitor.record_metric(
            metric_type='validation',
            value=1,
            endpoint='indicators/MACD',
            additional_data={
                'error_message': None,
                'validation_timestamp': '2024-01-01T00:00:00',
                'indicator_type': 'MACD'
            }
        )
        monitor.record_metric(
            metric_type='validation',
            value=0,
            endpoint='indicators/ADX',
            additional_data={
                'error_message': 'Invalid value',
                'validation_timestamp': '2024-01-01T00:00:00',
                'indicator_type': 'ADX'
            }
        )

        health = monitor.check_indicators_health()
        
        assert health['status'] == 'WARNING'
        assert 'MACD' in health['indicators']
        assert 'ADX' in health['indicators']
        assert health['indicators']['MACD']['status'] == 'OK'
        assert health['indicators']['ADX']['status'] == 'WARNING'

    def test_indicator_validation_rules(self, monitor):
        """Test des règles de validation des indicateurs"""
        rules = monitor._get_validation_rules('MACD')
        
        assert rules['type'] == 'dict'
        assert 'value' in rules['required_fields']
        assert 'signal' in rules['required_fields']
        assert 'histogram' in rules['required_fields']
        
        rules = monitor._get_validation_rules('ADX')
        assert rules['type'] == 'float'
        assert rules['range'] == [0, 100]

    def test_monitor_calculation_performance(self, monitor):
        """Test du monitoring des performances de calcul"""
        # Simuler des métriques de performance
        monitor.record_metric(
            metric_type='calculation_time',
            value=1000,
            endpoint='indicators/MACD'
        )
        monitor.record_metric(
            metric_type='calculation_time',
            value=6000,  # Au-dessus du seuil
            endpoint='indicators/ADX'
        )

        performance = monitor.monitor_calculation_performance()
        
        assert 'indicators_performance' in performance
        assert 'MACD' in performance['indicators_performance']
        assert 'ADX' in performance['indicators_performance']
        assert performance['indicators_performance']['MACD']['status'] == 'OK'
        assert performance['indicators_performance']['ADX']['status'] == 'WARNING'
        assert len(performance['bottlenecks']) > 0

    def test_record_validation_metrics(self, monitor):
        """Test de l'enregistrement des métriques de validation"""
        validation_results = {
            'MACD': {
                'valid': True,
                'calculation_time': 100
            },
            'ADX': {
                'valid': False,
                'error': 'Invalid value',
                'calculation_time': 150
            }
        }

        monitor.record_validation_metrics(validation_results)
        
        validation_metrics = [m for m in monitor.metrics if m['type'] == 'validation']
        calc_metrics = [m for m in monitor.metrics if m['type'] == 'calculation_time']
        
        assert len(validation_metrics) == 2
        assert len(calc_metrics) == 2
        
        macd_metric = next(m for m in validation_metrics if m['endpoint'] == 'indicators/MACD')
        assert macd_metric['value'] == 1
        assert macd_metric.get('error_message') is None
        
        adx_metric = next(m for m in validation_metrics if m['endpoint'] == 'indicators/ADX')
        assert adx_metric['value'] == 0
        assert adx_metric['error_message'] == 'Invalid value'

    def test_additional_data_in_metrics(self, monitor):
        """Test de l'ajout de données additionnelles aux métriques"""
        additional_data = {
            'test_key': 'test_value',
            'timestamp': '2024-01-01T00:00:00'
        }
        
        monitor.record_metric(
            metric_type='test',
            value=1.0,
            endpoint='test_endpoint',
            additional_data=additional_data
        )
        
        last_metric = monitor.metrics[-1]
        assert 'test_key' in last_metric
        assert last_metric['test_key'] == 'test_value'
        assert last_metric['timestamp'] == '2024-01-01T00:00:00'

if __name__ == "__main__":
    pytest.main(["-v", __file__])
