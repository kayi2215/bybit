import os
from dotenv import load_dotenv

load_dotenv()

# Configuration des APIs
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
BYBIT_API_KEY = os.getenv('BYBIT_API_KEY')
BYBIT_API_SECRET = os.getenv('BYBIT_API_SECRET')

# Paires de trading à surveiller
TRADING_PAIRS = ['BTCUSDT', 'ETHUSDT']

# Intervalles de temps pour les données
INTERVALS = ['1m', '5m', '15m', '1h', '4h', '1d']

# Configuration du logging
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
