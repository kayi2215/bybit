import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple

class AdvancedTechnicalAnalysis:
    def __init__(self):
        self.advanced_indicators = {}

    def calculate_ichimoku(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calcule l'indicateur Ichimoku Kinko Hyo"""
        high9 = df['high'].rolling(9).max()
        low9 = df['low'].rolling(9).min()
        tenkan_sen = (high9 + low9) / 2

        high26 = df['high'].rolling(26).max()
        low26 = df['low'].rolling(26).min()
        kijun_sen = (high26 + low26) / 2

        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
        
        high52 = df['high'].rolling(52).max()
        low52 = df['low'].rolling(52).min()
        senkou_span_b = ((high52 + low52) / 2).shift(26)

        chikou_span = df['close'].shift(-26)

        return {
            'Tenkan_sen': float(tenkan_sen.iloc[-1]),
            'Kijun_sen': float(kijun_sen.iloc[-1]),
            'Senkou_Span_A': float(senkou_span_a.iloc[-1]) if not pd.isna(senkou_span_a.iloc[-1]) else None,
            'Senkou_Span_B': float(senkou_span_b.iloc[-1]) if not pd.isna(senkou_span_b.iloc[-1]) else None,
            'Chikou_Span': float(chikou_span.iloc[-1]) if not pd.isna(chikou_span.iloc[-1]) else None
        }

    def calculate_adx(self, df: pd.DataFrame, period: int = 14) -> Dict[str, float]:
        """Calcule l'Average Directional Index (ADX)"""
        df = df.copy()
        df['TR'] = pd.DataFrame({
            'HL': df['high'] - df['low'],
            'HD': abs(df['high'] - df['close'].shift(1)),
            'LD': abs(df['low'] - df['close'].shift(1))
        }).max(axis=1)
        
        df['+DM'] = (df['high'] - df['high'].shift(1)).clip(lower=0)
        df['-DM'] = (df['low'].shift(1) - df['low']).clip(lower=0)
        df.loc[df['+DM'] < df['-DM'], '+DM'] = 0
        df.loc[df['-DM'] < df['+DM'], '-DM'] = 0

        TR_s = df['TR'].ewm(span=period, min_periods=period).mean()
        DMplus_s = df['+DM'].ewm(span=period, min_periods=period).mean()
        DMminus_s = df['-DM'].ewm(span=period, min_periods=period).mean()

        DIplus = 100 * DMplus_s / TR_s
        DIminus = 100 * DMminus_s / TR_s
        DX = 100 * abs(DIplus - DIminus) / (DIplus + DIminus)
        ADX = DX.ewm(span=period, min_periods=period).mean()

        return {
            'ADX': float(ADX.iloc[-1]),
            '+DI': float(DIplus.iloc[-1]),
            '-DI': float(DIminus.iloc[-1])
        }

    def calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcule l'Average True Range (ATR)"""
        df = df.copy()
        df['TR'] = pd.DataFrame({
            'HL': df['high'] - df['low'],
            'HD': abs(df['high'] - df['close'].shift(1)),
            'LD': abs(df['low'] - df['close'].shift(1))
        }).max(axis=1)
        
        atr = df['TR'].ewm(span=period, min_periods=period).mean()
        return float(atr.iloc[-1])

    def calculate_stochastic(self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Dict[str, float]:
        """Calcule l'oscillateur stochastique"""
        lowest_low = df['low'].rolling(window=k_period).min()
        highest_high = df['high'].rolling(window=k_period).max()
        
        k = 100 * ((df['close'] - lowest_low) / (highest_high - lowest_low))
        d = k.rolling(window=d_period).mean()
        
        return {
            '%K': float(k.iloc[-1]),
            '%D': float(d.iloc[-1])
        }

    def calculate_obv(self, df: pd.DataFrame) -> float:
        """Calcule l'On-Balance Volume (OBV)"""
        df = df.copy()
        df['OBV'] = (np.sign(df['close'].diff()) * df['volume']).fillna(0).cumsum()
        return float(df['OBV'].iloc[-1])

    def calculate_mfi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calcule le Money Flow Index"""
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        money_flow = typical_price * df['volume']
        
        positive_flow = pd.Series(0.0, index=df.index)
        negative_flow = pd.Series(0.0, index=df.index)
        
        # Calculer les flux positifs et négatifs
        price_diff = typical_price.diff()
        positive_flow[price_diff > 0] = money_flow[price_diff > 0]
        negative_flow[price_diff < 0] = money_flow[price_diff < 0]
        
        positive_mf = positive_flow.rolling(window=period).sum()
        negative_mf = negative_flow.rolling(window=period).sum()
        
        mfi = 100 - (100 / (1 + (positive_mf / negative_mf)))
        return float(mfi.iloc[-1])

    def calculate_pivot_points(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calcule les points pivots classiques"""
        pivot = (df['high'].iloc[-1] + df['low'].iloc[-1] + df['close'].iloc[-1]) / 3
        r1 = 2 * pivot - df['low'].iloc[-1]
        s1 = 2 * pivot - df['high'].iloc[-1]
        r2 = pivot + (df['high'].iloc[-1] - df['low'].iloc[-1])
        s2 = pivot - (df['high'].iloc[-1] - df['low'].iloc[-1])
        
        return {
            'Pivot': float(pivot),
            'R1': float(r1),
            'S1': float(s1),
            'R2': float(r2),
            'S2': float(s2)
        }

    def calculate_all_advanced(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Calcule tous les indicateurs techniques avancés
        :param df: DataFrame avec les colonnes OHLCV
        :return: Dictionnaire contenant tous les indicateurs calculés
        """
        # Convertir les colonnes numériques en float
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # Ichimoku
        ichimoku = self.calculate_ichimoku(df)
        self.advanced_indicators.update(ichimoku)

        # ADX
        adx = self.calculate_adx(df)
        self.advanced_indicators.update(adx)

        # ATR
        self.advanced_indicators['ATR'] = self.calculate_atr(df)

        # Stochastic
        stoch = self.calculate_stochastic(df)
        self.advanced_indicators.update(stoch)

        # OBV
        self.advanced_indicators['OBV'] = self.calculate_obv(df)

        # MFI
        self.advanced_indicators['MFI'] = self.calculate_mfi(df)

        # Pivot Points
        pivot_points = self.calculate_pivot_points(df)
        self.advanced_indicators.update(pivot_points)

        return self.advanced_indicators

    def get_advanced_signals(self, df: pd.DataFrame) -> Dict[str, str]:
        """
        Génère des signaux de trading basés sur les indicateurs avancés
        :param df: DataFrame avec les données OHLCV
        :return: Dictionnaire contenant les signaux de trading
        """
        indicators = self.calculate_all_advanced(df)
        signals = {}
        
        # Signal Ichimoku
        if indicators['Tenkan_sen'] > indicators['Kijun_sen']:
            signals['Ichimoku'] = 'Haussier'
        else:
            signals['Ichimoku'] = 'Baissier'

        # Signal ADX
        if indicators['ADX'] > 25:
            if indicators['+DI'] > indicators['-DI']:
                signals['ADX'] = 'Forte tendance haussière'
            else:
                signals['ADX'] = 'Forte tendance baissière'
        else:
            signals['ADX'] = 'Pas de tendance forte'

        # Signal Stochastic
        if indicators['%K'] < 20:
            signals['Stochastic'] = 'Survente'
        elif indicators['%K'] > 80:
            signals['Stochastic'] = 'Surachat'
        else:
            signals['Stochastic'] = 'Neutre'

        # Signal MFI
        if indicators['MFI'] < 20:
            signals['MFI'] = 'Survente'
        elif indicators['MFI'] > 80:
            signals['MFI'] = 'Surachat'
        else:
            signals['MFI'] = 'Neutre'

        return signals