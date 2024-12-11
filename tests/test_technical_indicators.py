from src.data_collector.market_data import MarketDataCollector
from config.config import BINANCE_API_KEY, BINANCE_API_SECRET

def test_technical_analysis():
    # Initialiser le collecteur de données
    collector = MarketDataCollector(BINANCE_API_KEY, BINANCE_API_SECRET)
    
    print("Récupération des données historiques...")
    # Obtenir les données historiques pour le calcul des indicateurs
    df = collector.get_klines('BTCUSDT', '1h', limit=100)
    
    print("\nCalcul des indicateurs techniques...")
    # Obtenir l'analyse technique complète
    analysis = collector.get_technical_analysis('BTCUSDT')
    
    print("\nDernières valeurs des indicateurs :")
    for indicator, value in analysis['indicators'].items():
        print(f"{indicator}: {value}")
    
    print("\nSignaux de trading :")
    for signal, value in analysis['signals'].items():
        print(f"{signal}: {value}")
    
    print("\nRésumé de l'analyse :")
    print(analysis['summary'])

if __name__ == "__main__":
    test_technical_analysis()
