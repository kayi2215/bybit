import time
import logging
import requests
from datetime import datetime
from typing import Dict, Optional, List
import json
import os
from pathlib import Path

class APIMonitor:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        self._setup_logging()
        self.metrics: List[Dict] = []
        self.alert_thresholds = {
            'latency': 1000,  # ms
            'error_rate': 0.1,  # 10%
            'consecutive_failures': 3
        }
        self.consecutive_failures = 0
        
        # Créer le répertoire de logs s'il n'existe pas
        Path(log_dir).mkdir(parents=True, exist_ok=True)

    def _setup_logging(self):
        """Configure le système de logging"""
        self.logger = logging.getLogger('api_monitor')
        self.logger.setLevel(logging.INFO)
        
        # Handler pour le fichier
        fh = logging.FileHandler(f"{self.log_dir}/api_monitor.log")
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

    def measure_latency(self, api_endpoint: str) -> Optional[float]:
        """Mesure la latence d'un appel API"""
        try:
            start_time = time.time()
            response = requests.get(api_endpoint)
            end_time = time.time()
            
            latency = (end_time - start_time) * 1000  # Convertir en millisecondes
            
            if response.status_code == 200:
                self.consecutive_failures = 0
                return latency
            else:
                self.consecutive_failures += 1
                self.logger.warning(f"API call failed with status code: {response.status_code}")
                return None
                
        except Exception as e:
            self.consecutive_failures += 1
            self.logger.error(f"Error measuring latency: {str(e)}")
            return None

    def check_availability(self, api_endpoint: str) -> bool:
        """Vérifie si l'API est disponible"""
        try:
            response = requests.get(api_endpoint)
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Error checking availability: {str(e)}")
            return False

    def record_metric(self, metric_type: str, value: float, endpoint: str):
        """Enregistre une métrique"""
        metric = {
            'timestamp': datetime.now().isoformat(),
            'type': metric_type,
            'value': value,
            'endpoint': endpoint
        }
        self.metrics.append(metric)
        
        # Sauvegarder les métriques dans un fichier JSON
        self._save_metrics()
        
        # Vérifier les seuils d'alerte
        self._check_alerts(metric)

    def _save_metrics(self):
        """Sauvegarde les métriques dans un fichier JSON"""
        metrics_file = f"{self.log_dir}/metrics.json"
        try:
            with open(metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving metrics: {str(e)}")

    def _check_alerts(self, metric: Dict):
        """Vérifie si des alertes doivent être déclenchées"""
        if metric['type'] == 'latency' and metric['value'] > self.alert_thresholds['latency']:
            self.logger.warning(f"High latency detected: {metric['value']}ms for {metric['endpoint']}")
        
        if self.consecutive_failures >= self.alert_thresholds['consecutive_failures']:
            self.logger.error(f"Multiple consecutive failures detected for {metric['endpoint']}")

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

    def check_api_health(self, api_endpoint: str) -> bool:
        """
        Vérifie la santé de l'API en contrôlant sa disponibilité et sa latence
        :param api_endpoint: URL de l'endpoint à vérifier
        :return: True si l'API est en bonne santé, False sinon
        """
        try:
            # Vérifier la disponibilité
            if not self.check_availability(api_endpoint):
                self.logger.warning(f"API {api_endpoint} is not available")
                return False
            
            # Mesurer la latence
            latency = self.measure_latency(api_endpoint)
            if latency is None or latency > self.alert_thresholds['latency']:
                self.logger.warning(f"API {api_endpoint} latency is too high or failed: {latency}ms")
                return False
            
            # Vérifier les échecs consécutifs
            if self.consecutive_failures >= self.alert_thresholds['consecutive_failures']:
                self.logger.warning(f"API {api_endpoint} has too many consecutive failures")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking API health: {str(e)}")
            return False

    def monitor_endpoint(self, api_endpoint: str):
        """Surveille un endpoint API"""
        self.logger.info(f"Monitoring endpoint: {api_endpoint}")
        
        # Vérifier la disponibilité
        available = self.check_availability(api_endpoint)
        if not available:
            self.logger.error(f"API endpoint {api_endpoint} is not available")
            return
        
        # Mesurer la latence
        latency = self.measure_latency(api_endpoint)
        if latency is not None:
            self.record_metric('latency', latency, api_endpoint)
            self.logger.info(f"Latency for {api_endpoint}: {latency}ms")
        
        # Obtenir et logger le résumé des métriques
        summary = self.get_metrics_summary()
        if summary:
            self.logger.info(f"Metrics summary: {json.dumps(summary, indent=2)}")
