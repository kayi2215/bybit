from data_collector.market_data import MarketDataCollector
from data_collector.technical_indicators import TechnicalAnalysis
from config import BINANCE_API_KEY, BINANCE_API_SECRET

def test_technical_analysis():
    # Initialiser le collecteur de données
    collector = MarketDataCollector(BINANCE_API_KEY, BINANCE_API_SECRET)
    
    # Récupérer les données historiques (100 dernières périodes)
    print("Récupération des données historiques...")
    df = collector.get_klines('BTCUSDT', '1h', limit=100)
    
    # Initialiser l'analyseur technique
    ta = TechnicalAnalysis()
    
    # Calculer les indicateurs
    print("\nCalcul des indicateurs techniques...")
    indicators = ta.calculate_all(df)
    
    # Afficher les dernières valeurs des indicateurs
    print("\nDernières valeurs des indicateurs :")
    for name, indicator in indicators.items():
        if not indicator.empty:
            print(f"{name}: {indicator.iloc[-1]:.2f}")
    
    # Obtenir et afficher les signaux
    print("\nSignaux de trading :")
    signals = ta.get_signals(df)
    for signal_type, value in signals.items():
        print(f"{signal_type}: {value}")
    
    # Afficher le résumé
    print("\nRésumé de l'analyse :")
    print(ta.get_summary(df))

if __name__ == "__main__":
    test_technical_analysis()
