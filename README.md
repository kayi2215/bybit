# Crypto Trading Bot

## Description
Bot de trading automatisé pour les crypto-monnaies, utilisant l'API Binance pour la collecte de données de marché en temps réel.

## Installation
1. Cloner le repository
2. Installer les dépendances : `pip install -r requirements.txt`
3. Copier le fichier `.env.example` vers `.env` et remplir avec vos clés API
4. Configurer les paires de trading dans `config.py`

## Configuration
- Créez un compte sur Binance et générez vos clés API
- Ajoutez vos clés API dans le fichier `.env`
- Modifiez les paires de trading dans `config.py` selon vos besoins

## Utilisation
```python
from data_collector.market_data import MarketDataCollector
from config import BINANCE_API_KEY, BINANCE_API_SECRET, TRADING_PAIRS

# Initialiser le collecteur de données
collector = MarketDataCollector(BINANCE_API_KEY, BINANCE_API_SECRET)

# Obtenir le prix actuel
btc_price = collector.get_current_price('BTCUSDT')

# Obtenir les données historiques
btc_klines = collector.get_klines('BTCUSDT', '1h', limit=100)

# Obtenir le carnet d'ordres
order_book = collector.get_order_book('BTCUSDT')
```

## Sécurité
- Ne jamais commiter vos clés API
- Utiliser des variables d'environnement pour les informations sensibles
- Limiter les permissions des clés API au minimum nécessaire
