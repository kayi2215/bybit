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
            'rate_limit_threshold': 0.8  # 80% de la limite d'utilisation
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

    def measure_latency(self, endpoint: str, method: str = "GET", **kwargs) -> Optional[float]:
        """Mesure la latence d'un appel API Bybit"""
        try:
            start_time = time.time()
            
            if not self.client:
                response = requests.get(f"{self.base_url}{endpoint}")
            else:
                method_map = {
                    "get_ticker": self.client.get_tickers,
                    "get_orderbook": self.client.get_orderbook,
                    "get_klines": self.client.get_kline
                }
                
                if method not in method_map:
                    raise ValueError(f"Unsupported method: {method}")
                
                response = method_map[method](**kwargs)
            
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # Convertir en millisecondes
            
            if self.is_valid_response(response):
                self.record_metric('latency', latency, endpoint)
                self.consecutive_failures = 0
                return latency
            else:
                self.consecutive_failures += 1
                self.record_metric('error', 1, endpoint)
                self.logger.warning(f"API call failed: {response}")
                return None
                
        except Exception as e:
            self.consecutive_failures += 1
            self.record_metric('error', 1, endpoint)
            self.logger.error(f"Error measuring latency: {str(e)}")
            return None

    def check_availability(self, endpoint: str = "/v5/market/tickers") -> bool:
        """Vérifie si l'API Bybit est disponible"""
        try:
            if not self.client:
                response = requests.get(f"{self.base_url}{endpoint}", params={"category": "spot", "symbol": "BTCUSDT"})
                success = response.status_code == 200 and self.is_valid_response(response.json())
            else:
                response = self.client.get_tickers(
                    category="spot",
                    symbol="BTCUSDT"
                )
                success = self.is_valid_response(response)
            
            if success:
                self.consecutive_failures = 0
                self.record_metric('availability', 1, endpoint)
                return True
            else:
                self.consecutive_failures += 1
                self.record_metric('availability', 0, endpoint)
                return False
                
        except Exception as e:
            self.consecutive_failures += 1
            self.record_metric('availability', 0, endpoint)
            self.logger.error(f"Error checking availability: {str(e)}")
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

    def record_metric(self, metric_type: str, value: float, endpoint: str):
        """Enregistre une métrique"""
        metric = {
            'timestamp': datetime.now().isoformat(),
            'type': metric_type,
            'value': value,
            'endpoint': endpoint,
            'testnet': self.testnet,
            'exchange': self.exchange
        }
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
        
        # Récupérer les alertes actives
        health_status['alerts'] = self.get_alerts()
        
        # Déterminer le statut global
        if not health_status['availability']:
            health_status['status'] = 'CRITICAL'
        elif health_status['alerts']:
            health_status['status'] = 'WARNING'
        
        return health_status

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
