from src.bot.trading_bot import TradingBot
import time

def main():
    """Point d'entrée principal du bot de trading"""
    try:
        # Créer et démarrer le bot
        bot = TradingBot()
        bot.start()
        
        # Maintenir le programme en vie
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nArrêt du bot...")
        bot.stop()
    except Exception as e:
        print(f"Erreur lors de l'exécution du bot: {str(e)}")
        if 'bot' in locals():
            bot.stop()

if __name__ == "__main__":
    main()
