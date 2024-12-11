from data_collector.market_data import MarketDataCollector
from config import BINANCE_API_KEY, BINANCE_API_SECRET

def test_market_data():
    collector = MarketDataCollector(BINANCE_API_KEY, BINANCE_API_SECRET)
    
    # Test get current price
    print("Testing current price...")
    btc_price = collector.get_current_price('BTCUSDT')
    print(f"BTC Price: {btc_price}\n")
    
    # Test get klines
    print("Testing historical data...")
    btc_klines = collector.get_klines('BTCUSDT', '1h', limit=5)
    print(f"BTC Klines:\n{btc_klines}\n")
    
    # Test get order book
    print("Testing order book...")
    order_book = collector.get_order_book('BTCUSDT', limit=5)
    print(f"Order Book: {order_book}")

if __name__ == "__main__":
    test_market_data()
