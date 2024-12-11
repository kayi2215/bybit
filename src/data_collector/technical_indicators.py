import pandas as pd
import numpy as np
import talib as ta
from typing import Dict, Any

class TechnicalAnalysis:
    def __init__(self):
        self.indicators = {}

    def calculate_rsi(self, data: pd.Series, periods: int = 14) -> pd.Series:
        """Calcule le RSI (Relative Strength Index)"""
        try:
            return pd.Series(ta.RSI(data.values, timeperiod=periods), index=data.index)
        except Exception as e:
            print(f"Erreur lors du calcul du RSI avec ta-lib: {str(e)}")
            # Fallback à l'implémentation manuelle
            delta = data.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=periods).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=periods).mean()
            rs = gain / loss
            return 100 - (100 / (1 + rs))

    def calculate_sma(self, data: pd.Series, periods: int) -> pd.Series:
        """Calcule la moyenne mobile simple"""
        return pd.Series(ta.SMA(data.values, timeperiod=periods), index=data.index)

    def calculate_ema(self, data: pd.Series, periods: int) -> pd.Series:
        """Calcule la moyenne mobile exponentielle"""
        return pd.Series(ta.EMA(data.values, timeperiod=periods), index=data.index)

    def calculate_macd(self, data: pd.Series) -> tuple:
        """Calcule le MACD (Moving Average Convergence Divergence)"""
        try:
            macd, signal, hist = ta.MACD(data.values, fastperiod=12, slowperiod=26, signalperiod=9)
            return (pd.Series(macd, index=data.index),
                    pd.Series(signal, index=data.index))
        except Exception as e:
            print(f"Erreur lors du calcul du MACD avec ta-lib: {str(e)}")
            # Fallback à l'implémentation manuelle
            exp1 = data.ewm(span=12, adjust=False).mean()
            exp2 = data.ewm(span=26, adjust=False).mean()
            macd = exp1 - exp2
            signal = macd.ewm(span=9, adjust=False).mean()
            return macd, signal

    def calculate_bollinger_bands(self, data: pd.Series, periods: int = 20) -> tuple:
        """Calcule les bandes de Bollinger"""
        try:
            upper, middle, lower = ta.BBANDS(data.values, timeperiod=periods)
            return (pd.Series(upper, index=data.index),
                    pd.Series(middle, index=data.index),
                    pd.Series(lower, index=data.index))
        except Exception as e:
            print(f"Erreur lors du calcul des Bandes de Bollinger avec ta-lib: {str(e)}")
            # Fallback à l'implémentation manuelle
            sma = self.calculate_sma(data, periods)
            std = data.rolling(window=periods).std()
            upper_band = sma + (std * 2)
            lower_band = sma - (std * 2)
            return upper_band, sma, lower_band

    def calculate_all(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calcule tous les indicateurs techniques principaux
        
        Args:
            df (pd.DataFrame): DataFrame contenant les données OHLCV avec les colonnes:
                - open: Prix d'ouverture
                - high: Prix le plus haut
                - low: Prix le plus bas
                - close: Prix de clôture
                - volume: Volume des transactions
                
        Returns:
            Dict[str, Any]: Dictionnaire contenant les indicateurs calculés:
                - RSI: Relative Strength Index
                - MACD: Moving Average Convergence Divergence
                - MACD_Signal: Signal line du MACD
                - MACD_Hist: Histogramme MACD
                - BB_Upper: Bande de Bollinger supérieure
                - BB_Middle: Bande de Bollinger moyenne
                - BB_Lower: Bande de Bollinger inférieure
                - SMA_20: Moyenne mobile simple sur 20 périodes
                - EMA_20: Moyenne mobile exponentielle sur 20 périodes
                
        Raises:
            ValueError: Si des colonnes requises sont manquantes
            Exception: Pour toute autre erreur lors du calcul
        """
        # Vérification et préparation des données
        required_columns = ['open', 'high', 'low', 'close', 'volume']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Colonnes manquantes: {', '.join(missing_columns)}")

        try:
            # Création d'une copie pour éviter de modifier le DataFrame original
            df_calc = df.copy()
            
            # Conversion et nettoyage des données
            for col in required_columns:
                df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce')
                if df_calc[col].isna().all():
                    raise ValueError(f"La colonne {col} ne contient que des valeurs invalides")
                df_calc[col] = df_calc[col].ffill().bfill()

            # Initialisation du dictionnaire des indicateurs
            self.indicators = {}

            # Calcul du RSI
            try:
                self.indicators['RSI'] = self.calculate_rsi(df_calc['close'])
            except Exception as e:
                print(f"Erreur lors du calcul du RSI, utilisation du fallback: {str(e)}")
                self.indicators['RSI'] = self.calculate_rsi(df_calc['close'])

            # Calcul du MACD
            try:
                macd, signal = self.calculate_macd(df_calc['close'])
                self.indicators['MACD'] = macd
                self.indicators['MACD_Signal'] = signal
                self.indicators['MACD_Hist'] = macd - signal
            except Exception as e:
                print(f"Erreur lors du calcul du MACD, utilisation du fallback: {str(e)}")
                macd, signal = self.calculate_macd(df_calc['close'])
                self.indicators['MACD'] = macd
                self.indicators['MACD_Signal'] = signal
                self.indicators['MACD_Hist'] = macd - signal

            # Calcul des Bandes de Bollinger
            try:
                bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df_calc['close'])
                self.indicators['BB_Upper'] = bb_upper
                self.indicators['BB_Middle'] = bb_middle
                self.indicators['BB_Lower'] = bb_lower
            except Exception as e:
                print(f"Erreur lors du calcul des Bandes de Bollinger, utilisation du fallback: {str(e)}")
                bb_upper, bb_middle, bb_lower = self.calculate_bollinger_bands(df_calc['close'])
                self.indicators['BB_Upper'] = bb_upper
                self.indicators['BB_Middle'] = bb_middle
                self.indicators['BB_Lower'] = bb_lower

            # Calcul des moyennes mobiles
            self.indicators['SMA_20'] = self.calculate_sma(df_calc['close'], 20)
            self.indicators['EMA_20'] = self.calculate_ema(df_calc['close'], 20)

            # Nettoyage final des NaN
            for key in self.indicators:
                self.indicators[key] = self.indicators[key].bfill()

            return self.indicators

        except ValueError as e:
            # Propager les erreurs de validation telles quelles
            raise e
        except Exception as e:
            error_msg = f"Erreur lors du calcul des indicateurs: {str(e)}"
            print(error_msg)
            raise Exception(error_msg)

    def get_signals(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Génère des signaux de trading basés sur les indicateurs techniques
        
        Args:
            df (pd.DataFrame): DataFrame avec les données OHLCV
            
        Returns:
            Dict[str, str]: Dictionnaire contenant les signaux:
                - RSI: 'Survente', 'Surachat', ou 'Neutre'
                - MACD: 'Achat' ou 'Vente'
                - BB: 'Surachat', 'Survente', 'Neutre', ou 'Indéterminé'
        """
        try:
            indicators = self.calculate_all(df)
            signals = {}
            
            # Vérification des données
            if len(df) < 2:
                raise ValueError("Pas assez de données pour générer des signaux")

            # Signal RSI avec vérification des valeurs
            last_rsi = indicators['RSI'].iloc[-1]
            if pd.isna(last_rsi):
                signals['RSI'] = 'Indéterminé'
            else:
                signals['RSI'] = 'Survente' if last_rsi < 30 else 'Surachat' if last_rsi > 70 else 'Neutre'

            # Signal MACD avec vérification de croisement
            last_macd = indicators['MACD'].iloc[-2:]
            last_signal = indicators['MACD_Signal'].iloc[-2:]
            
            if pd.isna(last_macd).any() or pd.isna(last_signal).any():
                signals['MACD'] = 'Indéterminé'
            else:
                # Détection du croisement
                crossed_up = last_macd.iloc[0] <= last_signal.iloc[0] and last_macd.iloc[1] > last_signal.iloc[1]
                crossed_down = last_macd.iloc[0] >= last_signal.iloc[0] and last_macd.iloc[1] < last_signal.iloc[1]
                
                if crossed_up:
                    signals['MACD'] = 'Achat'
                elif crossed_down:
                    signals['MACD'] = 'Vente'
                else:
                    signals['MACD'] = 'Neutre'

            # Signal Bollinger avec validation complète
            try:
                last_close = float(df['close'].iloc[-1])
                last_bb_upper = indicators['BB_Upper'].iloc[-1]
                last_bb_lower = indicators['BB_Lower'].iloc[-1]
                
                if pd.isna(last_bb_upper) or pd.isna(last_bb_lower) or pd.isna(last_close):
                    signals['BB'] = 'Indéterminé'
                else:
                    if last_close > last_bb_upper:
                        signals['BB'] = 'Surachat'
                    elif last_close < last_bb_lower:
                        signals['BB'] = 'Survente'
                    else:
                        signals['BB'] = 'Neutre'
            except Exception:
                signals['BB'] = 'Indéterminé'

            return signals
            
        except Exception as e:
            print(f"Erreur lors de la génération des signaux: {str(e)}")
            return {
                'RSI': 'Erreur',
                'MACD': 'Erreur',
                'BB': 'Erreur'
            }

    def get_summary(self, df: pd.DataFrame) -> str:
        """
        Génère un résumé détaillé de l'analyse technique
        
        Args:
            df (pd.DataFrame): DataFrame avec les données OHLCV
            
        Returns:
            str: Résumé formaté de l'analyse technique
        """
        try:
            signals = self.get_signals(df)
            indicators = self.indicators  # Utilise les indicateurs déjà calculés
            
            summary = []
            summary.append("=== Résumé de l'analyse technique ===")
            
            # Prix actuel et variation
            try:
                last_price = float(df['close'].iloc[-1])
                prev_price = float(df['close'].iloc[-2])
                price_change = ((last_price - prev_price) / prev_price) * 100
                summary.append(f"Prix actuel: {last_price:.2f} ({price_change:+.2f}%)")
            except Exception:
                summary.append("Prix actuel: Non disponible")
            
            # RSI avec valeur numérique
            if signals['RSI'] != 'Erreur' and signals['RSI'] != 'Indéterminé':
                last_rsi = indicators['RSI'].iloc[-1]
                summary.append(f"RSI: {last_rsi:.1f} - {signals['RSI']}")
            else:
                summary.append(f"RSI: {signals['RSI']}")
            
            # MACD avec valeurs
            if signals['MACD'] != 'Erreur' and signals['MACD'] != 'Indéterminé':
                last_macd = indicators['MACD'].iloc[-1]
                last_signal = indicators['MACD_Signal'].iloc[-1]
                summary.append(f"MACD: {last_macd:.2f} vs Signal: {last_signal:.2f} - {signals['MACD']}")
            else:
                summary.append(f"MACD: {signals['MACD']}")
            
            # Bandes de Bollinger avec écart
            if signals['BB'] != 'Erreur' and signals['BB'] != 'Indéterminé':
                last_bb_upper = indicators['BB_Upper'].iloc[-1]
                last_bb_lower = indicators['BB_Lower'].iloc[-1]
                bb_width = ((last_bb_upper - last_bb_lower) / indicators['BB_Middle'].iloc[-1]) * 100
                summary.append(f"Bandes de Bollinger: {signals['BB']} (Largeur: {bb_width:.1f}%)")
            else:
                summary.append(f"Bandes de Bollinger: {signals['BB']}")
            
            # Tendance des moyennes mobiles
            try:
                sma_trend = "↑" if indicators['SMA_20'].iloc[-1] > indicators['SMA_20'].iloc[-2] else "↓"
                ema_trend = "↑" if indicators['EMA_20'].iloc[-1] > indicators['EMA_20'].iloc[-2] else "↓"
                summary.append(f"Tendance - SMA20: {sma_trend} EMA20: {ema_trend}")
            except Exception:
                summary.append("Tendance: Non disponible")
            
            return "\n".join(summary)
            
        except Exception as e:
            return f"Erreur lors de la génération du résumé: {str(e)}"
