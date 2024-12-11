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
    # Ignorer les NaN au début de la série (période de warmup)
    valid_rsi = rsi.dropna()
    assert (valid_rsi >= 0).all() and (valid_rsi <= 100).all()

def test_calculate_macd(ta, sample_data):
    """Test du calcul du MACD"""
    macd, signal = ta.calculate_macd(sample_data['close'])
    assert not macd.empty and not signal.empty
    assert isinstance(macd, pd.Series)
    assert isinstance(signal, pd.Series)
    assert len(macd) == len(signal)
    # Vérifier les valeurs non-NaN
    assert not macd.dropna().empty
    assert not signal.dropna().empty

def test_calculate_bollinger_bands(ta, sample_data):
    """Test du calcul des bandes de Bollinger"""
    upper, middle, lower = ta.calculate_bollinger_bands(sample_data['close'])
    assert not upper.empty and not middle.empty and not lower.empty
    
    # Ignorer les NaN au début de la période
    valid_idx = upper.notna() & middle.notna() & lower.notna()
    assert (upper[valid_idx] >= middle[valid_idx]).all()
    assert (middle[valid_idx] >= lower[valid_idx]).all()

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
        assert not indicators[indicator].empty
        assert indicators[indicator].dtype == float
        # Vérifier qu'il y a des valeurs non-NaN
        assert not indicators[indicator].dropna().empty

def test_get_signals(ta, sample_data):
    """Test de la génération des signaux"""
    signals = ta.get_signals(sample_data)
    
    # Vérifier la présence de tous les signaux
    expected_signals = ['RSI', 'MACD', 'BB']
    for signal in expected_signals:
        assert signal in signals
    
    # Vérifier les valeurs possibles pour chaque signal
    assert signals['RSI'] in ['Survente', 'Surachat', 'Neutre', 'Indéterminé', 'Erreur']
    assert signals['MACD'] in ['Achat', 'Vente', 'Neutre', 'Indéterminé', 'Erreur']
    assert signals['BB'] in ['Surachat', 'Survente', 'Neutre', 'Indéterminé', 'Erreur']

def test_get_summary(ta, sample_data):
    """Test de la génération du résumé"""
    summary = ta.get_summary(sample_data)
    
    # Vérifier que le résumé contient les informations essentielles
    assert isinstance(summary, str)
    assert "=== Résumé de l'analyse technique ===" in summary
    assert "Prix actuel:" in summary
    assert "RSI:" in summary
    assert "MACD:" in summary
    assert "Bandes de Bollinger:" in summary
    assert "Tendance" in summary

def test_error_handling(ta):
    """Test de la gestion des erreurs"""
    # Test avec un DataFrame vide
    with pytest.raises(Exception):
        ta.calculate_all(pd.DataFrame())
    
    # Test avec des données manquantes
    bad_data = pd.DataFrame({
        'open': [1, 2, np.nan],
        'high': [2, 3, 4],
        'low': [0.5, 1.5, 2.5],
        'close': [1.5, 2.5, 3.5],
        'volume': [1000, 2000, 3000]
    })
    
    # Vérifier que les indicateurs sont calculés même avec des données manquantes
    indicators = ta.calculate_all(bad_data)
    assert not indicators['RSI'].empty

def test_data_validation(ta):
    """Test de la validation des données"""
    # Test avec des colonnes manquantes
    incomplete_data = pd.DataFrame({
        'close': [1, 2, 3],
        'volume': [100, 200, 300]
    })
    
    with pytest.raises(ValueError) as exc_info:
        ta.calculate_all(incomplete_data)
    assert "Colonnes manquantes" in str(exc_info.value)
    
    # Test avec trop peu de données
    small_data = pd.DataFrame({
        'open': [1],
        'high': [2],
        'low': [0.5],
        'close': [1.5],
        'volume': [1000]
    })
    
    signals = ta.get_signals(small_data)
    assert all(signal in ['Indéterminé', 'Erreur'] for signal in signals.values())

if __name__ == "__main__":
    pytest.main([__file__])
