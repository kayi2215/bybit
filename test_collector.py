from data_collector.market_data import MarketDataCollector
from config import BINANCE_API_KEY, BINANCE_API_SECRET

def test_market_data():
    collector = MarketDataCollector(BINANCE_API_KEY, BINANCE_API_SECRET)
    symbol = 'BTCUSDT'
    
    print("=== Test de collecte des données de base ===")
    
    # Test get current price
    print("\nTest du prix actuel...")
    btc_price = collector.get_current_price(symbol)
    print(f"Prix BTC: {btc_price}\n")
    
    # Test get klines
    print("Test des données historiques...")
    btc_klines = collector.get_klines(symbol, '1h', limit=5)
    print(f"Données historiques BTC:\n{btc_klines}\n")
    
    # Test get order book
    print("Test du carnet d'ordres...")
    order_book = collector.get_order_book(symbol, limit=5)
    print(f"Carnet d'ordres: {order_book}\n")

    print("\n=== Test de l'analyse technique ===")
    
    # Test de l'analyse technique
    print("\nTest de l'analyse technique...")
    technical_analysis = collector.get_technical_analysis(symbol)
    
    print("\nIndicateurs techniques:")
    for indicator, value in technical_analysis['indicators'].items():
        print(f"{indicator}: {value}")
    
    print("\nSignaux de trading:")
    for signal, value in technical_analysis['signals'].items():
        print(f"{signal}: {value}")
    
    print("\nRésumé de l'analyse:")
    print(technical_analysis['summary'])

    print("\n=== Test de l'analyse complète du marché ===")
    
    # Test de l'analyse complète du marché
    print("\nTest de l'analyse complète du marché...")
    market_analysis = collector.get_market_analysis(symbol)
    
    print("\nPrix actuel:")
    print(f"Prix: {market_analysis['current_price']['price']} USDT")
    
    print("\nAnalyse technique:")
    print(f"Dernière mise à jour: {market_analysis['technical_analysis']['last_update']}")
    print("Résumé:", market_analysis['technical_analysis']['summary'])
    
    print("\nCarnet d'ordres (top 5):")
    print("Ordres d'achat:", market_analysis['order_book']['bids'][:5])
    print("Ordres de vente:", market_analysis['order_book']['asks'][:5])

def validate_analysis(analysis_data):
    """
    Valide que toutes les données nécessaires sont présentes dans l'analyse
    """
    required_indicators = ['rsi', 'macd', 'bb_upper', 'bb_lower', 'sma_20', 'ema_20']
    required_signals = ['rsi_signal', 'macd_signal', 'bb_signal']
    
    # Vérification des indicateurs
    for indicator in required_indicators:
        if indicator not in analysis_data['indicators']:
            print(f"ATTENTION: L'indicateur {indicator} est manquant!")
            return False
    
    # Vérification des signaux
    for signal in required_signals:
        if signal not in analysis_data['signals']:
            print(f"ATTENTION: Le signal {signal} est manquant!")
            return False
    
    return True

if __name__ == "__main__":
    test_market_data()
