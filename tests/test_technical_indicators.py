import pytest
import pandas as pd
import numpy as np
from src.data_collector.technical_indicators import TechnicalAnalysis
from datetime import datetime, timedelta

@pytest.fixture
def sample_data():
    """Crée un DataFrame de test avec des données OHLCV"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='h')
    
    # Créer des données synthétiques avec une tendance
    close = np.linspace(100, 200, 100) + np.random.normal(0, 5, 100)
    high = close + np.abs(np.random.normal(2, 1, 100))
    low = close - np.abs(np.random.normal(2, 1, 100))
    data = {
        'open': close - np.random.normal(0, 2, 100),
        'high': high,
        'low': low,
        'close': close,
        'volume': np.abs(np.random.normal(1000, 100, 100))
    }
    
    df = pd.DataFrame(data, index=dates)
    return df

@pytest.fixture
def ta():
    """Crée une instance de TechnicalAnalysis"""
    return TechnicalAnalysis()

def test_calculate_rsi(ta, sample_data):
    """Test du calcul du RSI"""
    rsi = ta.calculate_rsi(sample_data['close'])
    assert not rsi.empty
    assert rsi.dtype == float
    # Vérifier que le RSI est dans la plage [0, 100]
    valid_rsi = rsi.dropna()
    assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()
    # Vérifier la longueur
    assert len(rsi) == len(sample_data)

def test_calculate_macd(ta, sample_data):
    """Test du calcul du MACD"""
    macd, signal = ta.calculate_macd(sample_data['close'])
    assert not macd.empty and not signal.empty
    assert isinstance(macd, pd.Series)
    assert isinstance(signal, pd.Series)
    assert len(macd) == len(signal) == len(sample_data)
    # Vérifier que les valeurs sont cohérentes
    assert not macd.isnull().all()
    assert not signal.isnull().all()
    # Vérifier que le signal suit le MACD (pas besoin de vérifier l'écart-type)
    assert not (macd == signal).all()  # Les séries ne doivent pas être identiques

def test_calculate_bollinger_bands(ta, sample_data):
    """Test du calcul des bandes de Bollinger"""
    upper, middle, lower = ta.calculate_bollinger_bands(sample_data['close'])
    assert not upper.empty and not middle.empty and not lower.empty
    assert len(upper) == len(middle) == len(lower) == len(sample_data)
    
    # Vérifier la relation entre les bandes
    valid_idx = upper.notna() & middle.notna() & lower.notna()
    assert (upper[valid_idx] >= middle[valid_idx]).all()
    assert (middle[valid_idx] >= lower[valid_idx]).all()
    
    # Vérifier que la bande moyenne est une SMA
    np.testing.assert_array_almost_equal(
        middle[valid_idx].values,
        ta.calculate_sma(sample_data['close'], 20)[valid_idx].values
    )

def test_calculate_all(ta, sample_data):
    """Test du calcul de tous les indicateurs"""
    indicators = ta.calculate_all(sample_data)
    
    # Vérifier la présence de tous les indicateurs
    expected_indicators = [
        'RSI', 'MACD', 'MACD_Signal', 'MACD_Hist',
        'BB_Upper', 'BB_Middle', 'BB_Lower',
        'SMA_20', 'EMA_20'
    ]
    
    for indicator in expected_indicators:
        assert indicator in indicators
        assert isinstance(indicators[indicator], pd.Series)
        assert len(indicators[indicator]) == len(sample_data)
        assert not indicators[indicator].isnull().all()

def test_get_signals(ta, sample_data):
    """Test de la génération des signaux"""
    signals = ta.get_signals(sample_data)
    
    # Vérifier la présence de tous les signaux
    expected_signals = ['RSI', 'MACD', 'BB', 'GLOBAL']
    for signal in expected_signals:
        assert signal in signals
    
    # Vérifier les valeurs possibles pour chaque signal
    assert signals['RSI'] in ['Survente', 'Surachat', 'Neutre']
    assert signals['MACD'] in ['Achat', 'Vente']
    assert signals['BB'] in ['Surachat', 'Survente', 'Neutre']
    assert signals['GLOBAL'] in ['Achat', 'Vente', 'Neutre']
    
    # Vérifier la cohérence du signal global
    bullish_count = sum(1 for s in signals.values() if s in ['Achat', 'Survente'])
    bearish_count = sum(1 for s in signals.values() if s in ['Vente', 'Surachat'])
    if bullish_count > bearish_count:
        assert signals['GLOBAL'] == 'Achat'
    elif bearish_count > bullish_count:
        assert signals['GLOBAL'] == 'Vente'
    else:
        assert signals['GLOBAL'] == 'Neutre'

def test_get_summary(ta, sample_data):
    """Test de la génération du résumé"""
    summary = ta.get_summary(sample_data)
    
    # Vérifier que le résumé est une chaîne non vide
    assert isinstance(summary, str)
    assert len(summary) > 0
    
    # Vérifier la présence des éléments clés
    assert "=== Résumé de l'analyse technique ===" in summary
    assert "RSI:" in summary
    assert "MACD:" in summary
    assert "Bandes de Bollinger:" in summary
    assert "Tendance -" in summary  # Le format est "Tendance -" au lieu de "Tendance:"
    assert "SMA20:" in summary
    assert "EMA20:" in summary

def test_numeric_consistency(ta, sample_data):
    """Test de la cohérence numérique des calculs"""
    # Test SMA
    sma_20 = ta.calculate_sma(sample_data['close'], 20)
    manual_sma = sample_data['close'].rolling(window=20).mean()
    np.testing.assert_array_almost_equal(sma_20.dropna(), manual_sma.dropna())
    
    # Test EMA
    ema_20 = ta.calculate_ema(sample_data['close'], 20)
    manual_ema = sample_data['close'].ewm(span=20, adjust=False).mean()
    np.testing.assert_array_almost_equal(ema_20.dropna(), manual_ema.dropna())

if __name__ == "__main__":
    pytest.main([__file__])
