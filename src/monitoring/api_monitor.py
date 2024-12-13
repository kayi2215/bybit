import time
import logging
import requests
import threading
from datetime import datetime
from typing import Dict, Optional, List
import json
import os
from pathlib import Path
from pybit.unified_trading import HTTP
from dotenv import load_dotenv

class APIMonitor:
    def __init__(self, log_dir: str = "logs", testnet: bool = False):
        # Créer le répertoire de logs s'il n'existe pas
        self.log_dir = os.path.abspath(log_dir)
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        self._setup_logging()
        self.metrics: List[Dict] = []
        self.alert_thresholds = {
            'latency': 2000,  # ms - aligné avec Binance
            'error_rate': 0.1,  # 10%
            'consecutive_failures': 3,
            'rate_limit_threshold': 0.8,  # 80% de la limite d'utilisation
            'indicator_calculation_time': 5000,  # ms
            'validation_error_threshold': 0.05  # 5% d'erreurs de validation acceptables
        }
        self.consecutive_failures = 0
        self.testnet = testnet
        self.exchange = "bybit"
        
        # Initialiser les compteurs de requêtes
        self.total_requests = 0
        self.failed_requests = 0
        
        # Initialiser le contrôle du thread
        self.stop_event = threading.Event()
        self.monitoring_thread = None
        self.is_running = False
        
        # Charger les clés API depuis les variables d'environnement
        load_dotenv()
        self.api_key = os.getenv('BYBIT_API_KEY')
        self.api_secret = os.getenv('BYBIT_API_SECRET')
        
        # Initialiser le client Bybit
        if self.api_key and self.api_secret:
            self.client = HTTP(
                testnet=self.testnet,
                api_key=self.api_key,
                api_secret=self.api_secret
            )
        else:
            self.logger.warning("API credentials not found. Running in public API mode only.")
            self.client = None

        self.base_url = "https://api.bybit.com"

    def _setup_logging(self):
        """Configure le système de logging"""
        self.logger = logging.getLogger('bybit_api_monitor')
        self.logger.setLevel(logging.INFO)
        
        # Handler pour le fichier
        fh = logging.FileHandler(f"{self.log_dir}/bybit_api_monitor.log")
        fh.setLevel(logging.INFO)
        
        # Handler pour la console
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        
        # Format
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def is_valid_response(self, response: Dict) -> bool:
        """Vérifie si la réponse de l'API est valide"""
        if not isinstance(response, dict):
            return False
        return response.get('retCode') == 0

    def measure_latency(self, endpoint: str, method: str = "GET", timeout: int = 5, **kwargs) -> Optional[float]:
        """Mesure la latence d'un appel API Bybit"""
        try:
            start_time = time.time()
            
            if not self.client:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=timeout)
            else:
                method_map = {
                    "get_ticker": self.client.get_tickers,
                    "get_orderbook": self.client.get_orderbook,
                    "get_klines": self.client.get_kline
                }
                
                if method not in method_map:
                    self.logger.error(f"Méthode non supportée: {method}")
                    return None

                # Create a threading Event for timeout
                timeout_event = threading.Event()
                response = None
                error = None

                def api_call():
                    nonlocal response, error
                    try:
                        response = method_map[method](**kwargs)
                    except Exception as e:
                        error = e

                # Start API call in a separate thread
                thread = threading.Thread(target=api_call)
                thread.daemon = True
                thread.start()
                
                # Wait for either completion or timeout
                thread.join(timeout=timeout)
                
                if thread.is_alive():
                    self.logger.error(f"Timeout lors de l'appel à {endpoint}")
                    return None
                
                if error is not None:
                    raise error
                
                if response is None:
                    return None
            
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # Convert to milliseconds
            
            if isinstance(response, requests.Response):
                is_valid = response.status_code == 200
            else:
                is_valid = self.is_valid_response(response)
            
            if is_valid:
                self.consecutive_failures = 0
                return latency
            else:
                self.consecutive_failures += 1
                return None
                
        except requests.Timeout:
            self.logger.error(f"Timeout lors de l'appel à {endpoint}")
            self.consecutive_failures += 1
            return None
        except Exception as e:
            self.logger.error(f"Erreur lors de la mesure de latence pour {endpoint}: {str(e)}")
            self.consecutive_failures += 1
            return None

    def check_availability(self, endpoint: str = "/v5/market/tickers", timeout: int = 5) -> bool:
        """Vérifie si l'API Bybit est disponible"""
        try:
            response = requests.get(f"{self.base_url}{endpoint}", timeout=timeout)
            return response.status_code == 200
        except requests.Timeout:
            self.logger.error("Timeout lors de la vérification de disponibilité")
            return False
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification de disponibilité: {str(e)}")
            return False

    def check_rate_limits(self) -> Dict:
        """Vérifie les limites de taux d'utilisation de l'API"""
        try:
            if not self.client:
                response = requests.get(f"{self.base_url}/v5/account/wallet-balance", params={"accountType": "UNIFIED"})
            else:
                response = self.client.get_wallet_balance(accountType="UNIFIED")
            
            # Simuler les limites basées sur les headers de réponse
            current_usage = 50  # Valeur simulée
            rate_limit = 100    # Valeur simulée
            
            usage_percent = (current_usage / rate_limit) * 100
            
            result = {
                'weight': current_usage,
                'limit': rate_limit,
                'usage_percent': usage_percent,
                'status': 'CRITICAL' if usage_percent > self.alert_thresholds['rate_limit_threshold'] * 100 else 'OK'
            }
            
            self.record_metric('rate_limit', usage_percent, 'rate_limits')
            return result
            
        except Exception as e:
            self.logger.error(f"Error checking rate limits: {str(e)}")
            return {
                'weight': 0,
                'limit': 100,
                'usage_percent': 0,
                'status': 'OK'
            }

    def record_metric(self, metric_type: str, value: float, endpoint: str, additional_data: Dict = None):
        """Enregistre une métrique"""
        metric = {
            'timestamp': datetime.now().isoformat(),
            'type': metric_type,
            'value': value,
            'endpoint': endpoint,
            'testnet': self.testnet,
            'exchange': self.exchange
        }
        if additional_data:
            metric.update(additional_data)
        self.metrics.append(metric)
        self._save_metrics()
        self._check_alerts(metric)

    def _save_metrics(self):
        """Sauvegarde les métriques dans un fichier JSON"""
        metrics_file = os.path.join(self.log_dir, 'metrics.json')
        try:
            with open(metrics_file, 'w') as f:
                json.dump(self.metrics, f)
        except Exception as e:
            self.logger.error(f"Error saving metrics: {str(e)}")

    def _check_alerts(self, metric: Dict):
        """Vérifie si une métrique déclenche une alerte"""
        if metric['type'] == 'latency' and metric['value'] > self.alert_thresholds['latency']:
            self.logger.warning(f"High latency detected: {metric['value']}ms for {metric['endpoint']}")
        
        elif metric['type'] == 'error':
            error_rate = self.failed_requests / self.total_requests if self.total_requests > 0 else 0
            if error_rate > self.alert_thresholds['error_rate']:
                self.logger.warning(f"High error rate detected: {error_rate:.2%}")
        
        elif metric['type'] == 'validation':
            validation_metrics = [m for m in self.metrics 
                                if m['type'] == 'validation' 
                                and m['endpoint'] == f'indicators/{metric["endpoint"]}']
            if validation_metrics:
                error_rate = sum(1 for m in validation_metrics if m['value'] == 0) / len(validation_metrics)
                if error_rate > self.alert_thresholds['validation_error_threshold']:
                    self.logger.warning(f"High validation error rate detected: {error_rate:.2%}")
        
        elif metric['type'] == 'calculation_time':
            if metric['value'] > self.alert_thresholds['indicator_calculation_time']:
                self.logger.warning(f"High calculation time detected: {metric['value']}ms")
        
        if self.consecutive_failures >= self.alert_thresholds['consecutive_failures']:
            self.logger.error(f"Multiple consecutive failures detected: {self.consecutive_failures}")

    def get_alerts(self) -> List[Dict]:
        """Récupère les alertes actives"""
        alerts = []
        
        # Vérifier la latency moyenne
        latency_metrics = [m['value'] for m in self.metrics if m['type'] == 'latency']
        if latency_metrics:
            avg_latency = sum(latency_metrics) / len(latency_metrics)
            if avg_latency > self.alert_thresholds['latency']:
                alerts.append({
                    'type': 'latency',
                    'message': f"High average latency: {avg_latency:.2f}ms",
                    'threshold': self.alert_thresholds['latency'],
                    'value': avg_latency,
                    'timestamp': datetime.now().isoformat()
                })

        # Vérifier le taux d'erreur
        error_rate = self.failed_requests / self.total_requests if self.total_requests > 0 else 0
        if error_rate > self.alert_thresholds['error_rate']:
            alerts.append({
                'type': 'error_rate',
                'message': f"High error rate: {error_rate:.2%}",
                'threshold': self.alert_thresholds['error_rate'],
                'value': error_rate,
                'timestamp': datetime.now().isoformat()
            })

        # Vérifier les échecs consécutifs
        if self.consecutive_failures >= self.alert_thresholds['consecutive_failures']:
            alerts.append({
                'type': 'consecutive_failures',
                'message': f"Multiple consecutive failures: {self.consecutive_failures}",
                'threshold': self.alert_thresholds['consecutive_failures'],
                'value': self.consecutive_failures,
                'timestamp': datetime.now().isoformat()
            })

        return alerts

    def get_metrics_summary(self) -> Dict:
        """Génère un résumé des métriques"""
        summary = {
            'total_requests': self.total_requests,
            'failed_requests': self.failed_requests,
            'error_rate': self.failed_requests / self.total_requests if self.total_requests > 0 else 0,
            'consecutive_failures': self.consecutive_failures,
            'alerts': self.get_alerts(),
            'last_update': datetime.now().isoformat()
        }
        
        # Calculer les statistiques de latence
        latency_metrics = [m['value'] for m in self.metrics if m['type'] == 'latency']
        if latency_metrics:
            summary.update({
                'avg_latency': sum(latency_metrics) / len(latency_metrics),
                'min_latency': min(latency_metrics),
                'max_latency': max(latency_metrics)
            })
        
        return summary

    def check_api_health(self) -> Dict:
        """Vérifie la santé globale de l'API"""
        health_status = {
            'status': 'OK',
            'latency': None,
            'availability': False,
            'rate_limits': {},
            'indicators_health': {},
            'performance': {},
            'alerts': [],
            'timestamp': datetime.now().isoformat()
        }
        
        # Vérifier la disponibilité
        health_status['availability'] = self.check_availability()
        
        # Mesurer la latence
        latency = self.measure_latency("/v5/market/tickers", "get_ticker", category="spot", symbol="BTCUSDT")
        health_status['latency'] = latency
        
        # Vérifier les limites de taux
        health_status['rate_limits'] = self.check_rate_limits()
        
        # Vérifier la santé des indicateurs
        health_status['indicators_health'] = self.check_indicators_health()
        
        # Vérifier la performance
        health_status['performance'] = self.monitor_calculation_performance()
        
        # Récupérer les alertes actives
        health_status['alerts'] = self.get_alerts()
        
        # Déterminer le statut global
        if not health_status['availability']:
            health_status['status'] = 'CRITICAL'
        elif health_status['alerts'] or health_status['indicators_health']['status'] != 'OK':
            health_status['status'] = 'WARNING'
        
        return health_status

    def check_indicators_health(self, timeout: int = 5) -> Dict:
        """Vérifie la santé des indicateurs avancés"""
        indicators_health = {
            'status': 'OK',
            'indicators': {},
            'timestamp': datetime.now().isoformat()
        }
        
        for indicator in ['MACD', 'ADX', 'ATR', 'SuperTrend']:
            try:
                # Create a threading Event for timeout
                result = None
                error = None
                
                def check_indicator():
                    nonlocal result, error
                    try:
                        result = self._check_indicator_validity(indicator)
                    except Exception as e:
                        error = e
                
                # Start indicator check in a separate thread
                thread = threading.Thread(target=check_indicator)
                thread.daemon = True
                thread.start()
                
                # Wait for either completion or timeout
                thread.join(timeout=timeout)
                
                if thread.is_alive():
                    self.logger.warning(f"Timeout checking indicator {indicator}")
                    indicators_health['indicators'][indicator] = {
                        'status': 'ERROR',
                        'error': 'Timeout'
                    }
                    indicators_health['status'] = 'WARNING'
                    continue
                
                if error is not None:
                    raise error
                
                if result is None:
                    indicators_health['indicators'][indicator] = {
                        'status': 'ERROR',
                        'error': 'No result'
                    }
                    indicators_health['status'] = 'WARNING'
                    continue
                
                indicators_health['indicators'][indicator] = result
                
                # Mettre à jour le statut global si nécessaire
                if result['status'] != 'OK':
                    indicators_health['status'] = 'WARNING'
                    
            except Exception as e:
                self.logger.error(f"Erreur lors de la vérification de l'indicateur {indicator}: {str(e)}")
                indicators_health['indicators'][indicator] = {
                    'status': 'ERROR',
                    'error': str(e)
                }
                indicators_health['status'] = 'WARNING'
        
        return indicators_health

    def _check_indicator_validity(self, indicator_name: str) -> Dict:
        """Vérifie la validité d'un indicateur spécifique"""
        validation_metrics = [m for m in self.metrics 
                            if m['type'] == 'validation' 
                            and m['endpoint'] == f'indicators/{indicator_name}']
        
        if not validation_metrics:
            return {
                'status': 'UNKNOWN',
                'last_update': None,
                'error_count': 0,
                'validation_errors': [],
                'validation_rules': self._get_validation_rules(indicator_name)
            }
        
        recent_metrics = sorted(validation_metrics, key=lambda x: x['timestamp'])[-10:]
        error_count = sum(1 for m in recent_metrics if m['value'] == 0)
        
        return {
            'status': 'OK' if error_count == 0 else 'WARNING',
            'last_update': recent_metrics[-1]['timestamp'],
            'error_count': error_count,
            'validation_errors': [m.get('error_message') for m in recent_metrics if m['value'] == 0],
            'validation_rules': self._get_validation_rules(indicator_name)
        }

    def _get_validation_rules(self, indicator_name: str) -> Dict:
        """Retourne les règles de validation pour un indicateur"""
        rules = {
            'MACD': {
                'type': 'dict',
                'required_fields': ['value', 'signal', 'histogram'],
                'field_types': {'value': 'float', 'signal': 'float', 'histogram': 'float'}
            },
            'ADX': {
                'type': 'float',
                'range': [0, 100]
            },
            'ATR': {
                'type': 'float',
                'min': 0
            },
            'SuperTrend': {
                'type': 'dict',
                'required_fields': ['value', 'direction'],
                'field_types': {'value': 'float', 'direction': 'str'}
            }
        }
        return rules.get(indicator_name, {})

    def monitor_calculation_performance(self) -> Dict:
        """Monitore la performance des calculs d'indicateurs"""
        performance_metrics = [m for m in self.metrics if m['type'] == 'calculation_time']
        
        if not performance_metrics:
            return {
                'calculation_time': 0,
                'memory_usage': 0,
                'cpu_usage': 0,
                'bottlenecks': [],
                'indicators_performance': {}
            }
        
        recent_metrics = sorted(performance_metrics, key=lambda x: x['timestamp'])[-5:]
        avg_calc_time = sum(m['value'] for m in recent_metrics) / len(recent_metrics)
        
        # Performances par indicateur
        indicators_performance = {}
        bottlenecks = []
        for indicator in ['MACD', 'ADX', 'ATR', 'SuperTrend']:
            indicator_metrics = [m for m in recent_metrics 
                               if m.get('endpoint', '').endswith(indicator)]
            if indicator_metrics:
                avg_time = sum(m['value'] for m in indicator_metrics) / len(indicator_metrics)
                indicators_performance[indicator] = {
                    'avg_calculation_time': avg_time,
                    'status': 'OK' if avg_time < self.alert_thresholds['indicator_calculation_time'] else 'WARNING'
                }
                if avg_time > self.alert_thresholds['indicator_calculation_time']:
                    bottlenecks.append(f"High calculation time for {indicator}: {avg_time:.2f}ms")
        
        if avg_calc_time > self.alert_thresholds['indicator_calculation_time']:
            bottlenecks.append(f"High average calculation time: {avg_calc_time:.2f}ms")
        
        return {
            'calculation_time': avg_calc_time,
            'memory_usage': 0,  # À implémenter si nécessaire
            'cpu_usage': 0,     # À implémenter si nécessaire
            'bottlenecks': bottlenecks,
            'indicators_performance': indicators_performance
        }

    def record_validation_metrics(self, validation_results: Dict):
        """Enregistre les métriques de validation des indicateurs"""
        timestamp = datetime.now().isoformat()
        
        for indicator, result in validation_results.items():
            metric_value = 1 if result.get('valid', False) else 0
            error_message = result.get('error', 'Unknown error')
            
            self.record_metric(
                metric_type='validation',
                value=metric_value,
                endpoint=f'indicators/{indicator}',
                additional_data={
                    'error_message': error_message if not result.get('valid', False) else None,
                    'validation_timestamp': timestamp,
                    'indicator_type': indicator
                }
            )
            
            if not result.get('valid', False):
                self.logger.warning(f"Validation failed for {indicator}: {error_message}")
            
            # Enregistrer le temps de calcul pour tous les indicateurs
            if 'calculation_time' in result:
                self.record_metric(
                    metric_type='calculation_time',
                    value=result['calculation_time'],
                    endpoint=f'indicators/{indicator}'
                )

    def start(self):
        """Démarre le service de monitoring"""
        if self.is_running:
            self.logger.warning("Le service de monitoring est déjà en cours d'exécution")
            return

        self.is_running = True
        self.stop_event.clear()
        self.monitoring_thread = threading.Thread(target=self.run)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        self.logger.info("Service de monitoring démarré")

    def stop(self):
        """Arrête le service de monitoring"""
        if not self.is_running:
            return
            
        self.logger.info("Arrêt du service de monitoring...")
        self.stop_event.set()
        self.is_running = False
        
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=30)
        self.logger.info("Service de monitoring arrêté")

    def run(self):
        """Boucle principale du service de monitoring"""
        while not self.stop_event.is_set():
            try:
                # Effectuer les vérifications de monitoring
                self.check_api_status()
                self.check_rate_limits()
                self.log_metrics()
                
                # Attendre 60 secondes ou jusqu'à ce que stop_event soit défini
                self.stop_event.wait(timeout=60)
            except Exception as e:
                self.logger.error(f"Erreur dans la boucle de monitoring: {str(e)}")
                time.sleep(5)  # Pause courte en cas d'erreur

    def check_api_status(self):
        """Vérifie l'état de l'API"""
        try:
            response = requests.get(f"{self.base_url}/v5/market/tickers")
            if response.status_code == 200:
                self.logger.info("API est disponible")
            else:
                self.logger.error(f"API indisponible: {response.status_code}")
        except Exception as e:
            self.logger.error(f"Erreur lors de la vérification de l'état de l'API: {str(e)}")

    def log_metrics(self):
        """Enregistre les métriques"""
        try:
            self.record_metric('availability', 1, 'api_status')
            self.record_metric('rate_limit', 50, 'rate_limits')
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enregistrement des métriques: {str(e)}")
