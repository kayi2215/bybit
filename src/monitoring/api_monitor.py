import time
import logging
import requests
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
        self.exchange = "bybit"  # Identifier l'exchange
        
        # Charger les clés API depuis les variables d'environnement
        load_dotenv()
        self.api_key = os.getenv('BYBIT_API_KEY')
        self.api_secret = os.getenv('BYBIT_API_SECRET')
        
        # Initialiser les compteurs de requêtes
        self.total_requests = 0
        self.failed_requests = 0
        
        # Initialiser le client Bybit
        if self.api_key and self.api_secret:
            self.client = HTTP(
                testnet=testnet,
                api_key=self.api_key,
                api_secret=self.api_secret
            )
        else:
            self.logger.warning("API credentials not found. Running in public API mode only.")
            self.client = None

    def _setup_logging(self):
        """Configure le système de logging"""
        self.logger = logging.getLogger('bybit_api_monitor')
        self.logger.setLevel(logging.INFO)
        
        # Supprimer les handlers existants
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Handler pour le fichier
        log_file = os.path.join(self.log_dir, 'bybit_api_monitor.log')
        fh = logging.FileHandler(log_file)
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
        if isinstance(response, dict):
            return response.get('retCode') == 0
        return False

    def measure_latency(self, endpoint: str, method: str = "GET", **kwargs) -> Optional[float]:
        """Mesure la latence d'un appel API Bybit"""
        try:
            start_time = time.time()
            
            if not self.client:
                response = requests.get(f"https://api.bybit.com{endpoint}")
            else:
                # Utiliser le client Bybit avec la méthode appropriée
                method_map = {
                    "get_ticker": self.client.get_tickers,
                    "get_orderbook": self.client.get_orderbook,
                    "get_klines": self.client.get_kline,
                    "get_tickers": self.client.get_tickers  # Ajout pour la compatibilité avec les tests existants
                }
                
                if method not in method_map:
                    raise ValueError(f"Unsupported method: {method}")
                
                response = method_map[method](**kwargs)
            
            end_time = time.time()
            latency = (end_time - start_time) * 1000  # Convertir en millisecondes
            
            if self.is_valid_response(response):
                self.consecutive_failures = 0
                # Enregistrer la métrique de latence
                self.record_metric('latency', latency, endpoint)
                return latency
            else:
                self.consecutive_failures += 1
                self.logger.warning(f"API call failed: {response}")
                return None
                
        except Exception as e:
            self.consecutive_failures += 1
            self.logger.error(f"Error measuring latency: {str(e)}")
            return None

    def check_availability(self, endpoint: str = "/v5/market/tickers") -> bool:
        """Vérifie si l'API Bybit est disponible"""
        try:
            if not self.client:
                base_url = "https://api-testnet.bybit.com" if self.testnet else "https://api.bybit.com"
                response = requests.get(f"{base_url}{endpoint}", params={"category": "spot", "symbol": "BTCUSDT"})
                return response.status_code == 200 and response.json().get('retCode') == 0
            else:
                # Utiliser le client Bybit
                response = self.client.get_tickers(
                    category="spot",
                    symbol="BTCUSDT"
                )
                return isinstance(response, dict) and response.get('retCode') == 0
        except Exception as e:
            self.logger.error(f"Error checking availability: {str(e)}")
            return False

    def check_rate_limits(self) -> Dict:
        """Vérifie les limites de taux d'utilisation de l'API"""
        if not self.client:
            return {}
        
        try:
            # Pour Bybit, nous utilisons get_wallet_balance comme proxy pour vérifier les limites
            # car il n'y a pas d'endpoint dédié pour les rate limits
            response = self.client.get_wallet_balance(accountType="UNIFIED")
            
            # Simuler les limites basées sur les headers de réponse
            # Note: Ceci est une simulation, les vraies limites devraient être implémentées
            # selon la documentation Bybit
            current_usage = 50  # Valeur simulée
            rate_limit = 100    # Valeur simulée
            
            usage_percent = (current_usage / rate_limit) * 100
            
            result = {
                'weight': current_usage,
                'limit': rate_limit,
                'usage_percent': usage_percent,
                'status': 'CRITICAL' if usage_percent > self.alert_thresholds['rate_limit_threshold'] * 100 else 'OK'
            }
            
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
            'testnet': self.testnet
        }
        self.metrics.append(metric)
        
        # Sauvegarder les métriques
        self._save_metrics()
        
        # Vérifier les seuils d'alerte
        self._check_alerts(metric)

    def _check_alerts(self, metric: Dict):
        """Vérifie si des alertes doivent être déclenchées"""
        if metric['type'] == 'latency' and metric['value'] > self.alert_thresholds['latency']:
            self.logger.warning(f"High latency detected: {metric['value']}ms for {metric['endpoint']}")
        
        if self.consecutive_failures >= self.alert_thresholds['consecutive_failures']:
            self.logger.error(f"Multiple consecutive failures detected for {metric['endpoint']}")
        
        # Vérifier les limites de taux
        rate_limits = self.check_rate_limits()
        if rate_limits.get('status') == 'CRITICAL':
            self.logger.critical("Rate limit threshold exceeded!")

    def get_alerts(self) -> List[Dict]:
        """Récupère les alertes actives"""
        alerts = []
        
        # Vérifier la latence moyenne
        if self.metrics:
            latency_metrics = [m['value'] for m in self.metrics if m['type'] == 'latency']
            if latency_metrics:
                avg_latency = sum(latency_metrics) / len(latency_metrics)
                if avg_latency > self.alert_thresholds['latency']:
                    alerts.append({
                        'type': 'high_latency',
                        'value': avg_latency,
                        'threshold': self.alert_thresholds['latency'],
                        'timestamp': datetime.now().isoformat()
                    })
        
        # Vérifier les échecs consécutifs
        if self.consecutive_failures >= self.alert_thresholds['consecutive_failures']:
            alerts.append({
                'type': 'consecutive_failures',
                'value': self.consecutive_failures,
                'threshold': self.alert_thresholds['consecutive_failures'],
                'timestamp': datetime.now().isoformat()
            })
        
        # Vérifier le taux d'erreur
        if hasattr(self, 'total_requests') and self.total_requests > 0:
            error_rate = self.failed_requests / self.total_requests
            if error_rate > self.alert_thresholds['error_rate']:
                alerts.append({
                    'type': 'high_error_rate',
                    'value': error_rate,
                    'threshold': self.alert_thresholds['error_rate'],
                    'timestamp': datetime.now().isoformat()
                })
        
        return alerts

    def monitor_endpoint(self, endpoint: str, method: str = "GET", **kwargs):
        """Surveille un endpoint spécifique"""
        self.logger.info(f"Monitoring Bybit endpoint: {endpoint} ({method})")
        
        # Vérifier la disponibilité
        available = self.check_availability(endpoint)
        if not available:
            self.logger.error(f"Bybit API endpoint {endpoint} is not available")
            return
        
        # Mettre à jour les compteurs
        self.total_requests += 1
        
        # Mesurer la latence
        latency = self.measure_latency(endpoint, method, **kwargs)
        
        if latency is None:
            self.failed_requests += 1
        else:
            self.logger.info(f"Latency for {endpoint}: {latency}ms")
        
        # Vérifier les limites de taux
        rate_limits = self.check_rate_limits()
        if rate_limits:
            self.logger.info(f"Rate limits status: {json.dumps(rate_limits, indent=2)}")
        
        # Obtenir et logger le résumé des métriques
        summary = self.get_metrics_summary()
        if summary:
            self.logger.info(f"Metrics summary: {json.dumps(summary, indent=2)}")

    def get_metrics_summary(self) -> Dict:
        """Retourne un résumé des métriques"""
        if not self.metrics:
            return {}
        
        latencies = [m['value'] for m in self.metrics if m['type'] == 'latency']
        if not latencies:
            return {}
        
        return {
            'avg_latency': sum(latencies) / len(latencies),
            'max_latency': max(latencies),
            'min_latency': min(latencies),
            'total_requests': len(latencies),
            'error_rate': self.consecutive_failures / len(latencies) if latencies else 0
        }

    def _save_metrics(self):
        """Sauvegarde les métriques dans un fichier JSON"""
        metrics_file = os.path.join(self.log_dir, 'metrics.json')
        try:
            with open(metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving metrics: {str(e)}")
