from src.bot.trading_bot import TradingBot

def main():
    """Point d'entrée principal du bot de trading"""
    try:
        # Créer et démarrer le bot
        bot = TradingBot()
        bot.start()
    except KeyboardInterrupt:
        print("\nArrêt du bot...")
    except Exception as e:
        print(f"Erreur lors de l'exécution du bot: {str(e)}")

if __name__ == "__main__":
    main()
