import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import warnings
from src.data_collector.market_data import MarketDataCollector
from src.data_collector.advanced_technical_indicators import AdvancedTechnicalAnalysis
from config.config import BYBIT_API_KEY, BYBIT_API_SECRET

# Filtrer les warnings spécifiques
warnings.filterwarnings("ignore", category=FutureWarning, message="'H' is deprecated")
warnings.filterwarnings("ignore", category=DeprecationWarning, 
                      message="datetime.datetime.utcnow\\(\\) is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now\\(datetime.UTC\\).")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="pybit._http_manager")

@pytest.fixture
def collector():
    return MarketDataCollector(BYBIT_API_KEY, BYBIT_API_SECRET, use_testnet=True)

@pytest.fixture
def sample_data():
    # Utiliser 'h' au lieu de 'H' pour la fréquence
    dates = pd.date_range(start='2023-01-01', periods=100, freq='1h')
    df = pd.DataFrame({
        'timestamp': [int(d.timestamp() * 1000) for d in dates],
        'open': np.random.normal(100, 10, 100),
        'high': np.random.normal(105, 10, 100),
        'low': np.random.normal(95, 10, 100),
        'close': np.random.normal(100, 10, 100),
        'volume': np.random.normal(1000, 100, 100)
    })
    return df

class TestAdvancedIndicators:
    def test_advanced_analysis_structure(self, collector):
        """Test de la structure de l'analyse technique avancée"""
        analysis = collector.get_advanced_technical_analysis('BTCUSDT')
        
        assert 'indicators' in analysis
        assert 'signals' in analysis
        assert 'timestamp' in analysis
        
        # Vérifier la présence des indicateurs avancés
        indicators = analysis['indicators']
        assert 'ADX' in indicators
        assert 'ATR' in indicators
        assert 'MFI' in indicators
        assert 'Tenkan_sen' in indicators
        assert 'Kijun_sen' in indicators

    def test_complete_analysis_structure(self, collector):
        """Test de la structure de l'analyse technique complète"""
        analysis = collector.get_complete_analysis('BTCUSDT')
        
        assert 'timestamp' in analysis
        assert 'basic_analysis' in analysis
        assert 'advanced_analysis' in analysis
        
        advanced = analysis['advanced_analysis']
        assert 'indicators' in advanced
        assert 'signals' in advanced

    def test_ichimoku_calculation(self, sample_data):
        """Test du calcul de l'indicateur Ichimoku"""
        analyzer = AdvancedTechnicalAnalysis()
        ichimoku = analyzer.calculate_ichimoku(sample_data)
        
        assert 'Tenkan_sen' in ichimoku
        assert 'Kijun_sen' in ichimoku
        assert 'Senkou_Span_A' in ichimoku
        assert 'Senkou_Span_B' in ichimoku
        assert 'Chikou_Span' in ichimoku

    def test_adx_calculation(self, sample_data):
        """Test du calcul de l'ADX"""
        analyzer = AdvancedTechnicalAnalysis()
        adx = analyzer.calculate_adx(sample_data)
        
        assert 'ADX' in adx
        assert '+DI' in adx
        assert '-DI' in adx
        assert 0 <= adx['ADX'] <= 100

    def test_advanced_signals_generation(self, sample_data):
        """Test de la génération des signaux avancés"""
        analyzer = AdvancedTechnicalAnalysis()
        signals = analyzer.get_advanced_signals(sample_data)
        
        assert 'Ichimoku' in signals
        assert 'ADX' in signals
        assert 'Stochastic' in signals
        assert 'MFI' in signals

    def test_numerical_consistency(self, collector):
        """Test de la cohérence numérique des calculs avancés"""
        analysis = collector.get_advanced_technical_analysis('BTCUSDT')
        
        for indicator, value in analysis['indicators'].items():
            if value is not None:  # Certains indicateurs Ichimoku peuvent être None
                assert not np.isnan(value), f"L'indicateur {indicator} ne doit pas être NaN"
                assert not np.isinf(value), f"L'indicateur {indicator} ne doit pas être infini"

    def test_error_handling(self, collector):
        """Test de la gestion des erreurs"""
        with pytest.raises(Exception):
            collector.get_advanced_technical_analysis('INVALID_SYMBOL')

if __name__ == "__main__":
    pytest.main([__file__])