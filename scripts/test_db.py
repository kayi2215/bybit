import os
import sys

# Ajouter le répertoire racine au PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.mongodb_manager import MongoDBManager
from datetime import datetime

def test_market_data():
    """Test l'insertion et la récupération des données de marché"""
    print("\nTest des données de marché:")
    try:
        # Données de test
        test_data = {
            "price": 50000.0,
            "volume": 100.0,
            "timestamp": datetime.now()
        }
        
        # Insertion
        db.store_market_data("BTCUSDT", test_data)
        print("✅ Insertion réussie")
        
        # Récupération
        result = db.get_latest_market_data("BTCUSDT")
        print(f"📊 Dernières données: {result}")
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")

def test_indicators():
    """Test l'insertion et la récupération des indicateurs"""
    print("\nTest des indicateurs:")
    try:
        # Données de test
        test_indicators = {
            "rsi": 65.5,
            "macd": {"value": 100.0, "signal": 95.0}
        }
        
        # Insertion
        db.store_indicators("BTCUSDT", test_indicators)
        print("✅ Insertion réussie")
        
        # Récupération
        result = db.get_latest_indicators("BTCUSDT")
        print(f"📈 Derniers indicateurs: {result}")
        
    except Exception as e:
        print(f"❌ Erreur: {str(e)}")

if __name__ == "__main__":
    try:
        print("🔄 Connexion à MongoDB...")
        db = MongoDBManager()
        print("✅ Connexion réussie!")
        
        # Exécution des tests
        test_market_data()
        test_indicators()
        
    except Exception as e:
        print(f"❌ Erreur de connexion: {str(e)}")
    finally:
        if 'db' in locals():
            db.close()
            print("\n🔒 Connexion fermée")
