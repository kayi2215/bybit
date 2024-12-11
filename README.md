# Bot de Trading Crypto

Bot de trading automatique pour le marché des cryptomonnaies utilisant l'API Binance.

## Structure du Projet

```
bot/
├── config/             # Configuration et variables d'environnement
│   ├── config.py
│   └── .env
├── logs/              # Fichiers de logs
├── src/               # Code source
│   ├── bot/          # Logique principale du bot
│   ├── data_collector/# Collecte de données de marché
│   ├── monitoring/   # Surveillance des APIs
│   └── utils/        # Utilitaires
├── tests/            # Tests unitaires et d'intégration
└── main.py           # Point d'entrée principal
```

## Installation

1. Cloner le repository
2. Créer un environnement virtuel :
   ```bash
   python -m venv venv
   source venv/bin/activate  # Sur Unix
   ```
3. Installer les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
4. Copier `.env.example` vers `.env` et configurer vos clés API

## Configuration

1. Configurer les variables d'environnement dans `.env` :
   - `BINANCE_API_KEY`: Votre clé API Binance
   - `BINANCE_API_SECRET`: Votre clé secrète API Binance
   - `USE_TESTNET`: `True` pour utiliser le testnet Binance

## Utilisation

1. Lancer le bot :
   ```bash
   python main.py
   ```

2. Le bot va :
   - Démarrer le service de monitoring
   - Collecter les données de marché
   - Exécuter la stratégie de trading
   - Logger toutes les opérations

## Monitoring

Le système de monitoring surveille :
- La latence des appels API
- La disponibilité des endpoints
- Les taux d'erreur
- Les performances globales

Les logs et métriques sont stockés dans le dossier `logs/`.
