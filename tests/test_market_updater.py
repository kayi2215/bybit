import unittest
from unittest.mock import Mock, patch, create_autospec
import time
from datetime import datetime
import os
import pandas as pd

from src.services.market_updater import MarketUpdater
from src.database.mongodb_manager import MongoDBManager
from src.data_collector.market_data import MarketDataCollector
from src.monitoring.api_monitor import APIMonitor

class TestMarketUpdater(unittest.TestCase):
    def setUp(self):
        """Configuration initiale des tests"""
        # Création des mocks
        self.mock_collector = Mock()
        self.mock_db = create_autospec(MongoDBManager)
        self.mock_technical_analysis = Mock()
        self.mock_advanced_technical_analysis = Mock()
        self.mock_api_monitor = Mock()
        
        # Configuration du MarketUpdater avec les mocks
        self.market_updater = MarketUpdater(['BTCUSDT'], db=self.mock_db)
        self.market_updater.collector = self.mock_collector
        self.market_updater.technical_analysis = self.mock_technical_analysis
        self.market_updater.advanced_technical_analysis = self.mock_advanced_technical_analysis
        self.market_updater.api_monitor = self.mock_api_monitor
        
        # Configuration des retours par défaut
        self.mock_api_monitor.check_api_health.return_value = {"status": "OK"}
        self.mock_db.store_market_data.return_value = True
        self.mock_db.store_indicators.return_value = True
        self.mock_db.save_market_data.return_value = "mock_market_data_id"
        self.mock_db.save_advanced_indicators.return_value = True
        
        # Reduce intervals for faster tests
        self.market_updater.update_interval = 0.1
        self.market_updater.shutdown_timeout = 1

    def tearDown(self):
        """Nettoyage après chaque test"""
        if hasattr(self.market_updater, 'stop'):
            self.market_updater.stop()
        # Reset all mocks
        self.mock_collector.reset_mock()
        self.mock_db.reset_mock()
        self.mock_technical_analysis.reset_mock()
        self.mock_advanced_technical_analysis.reset_mock()
        self.mock_api_monitor.reset_mock()

    def test_init(self):
        """Test de l'initialisation du MarketUpdater"""
        self.assertEqual(self.market_updater.symbols, ['BTCUSDT'])
        self.assertEqual(self.market_updater.db, self.mock_db)
        self.assertEqual(self.market_updater.error_counts, {'BTCUSDT': 0})

    def test_update_market_data_success(self):
        """Test de la mise à jour réussie des données de marché"""
        symbol = "BTCUSDT"
        timestamp = datetime.now()
        
        # Mock de l'analyse complète
        complete_analysis = {
            'timestamp': timestamp,
            'basic_analysis': {
                'ticker': {'price': 50000.0},
                'klines': pd.DataFrame({
                    'timestamp': [1, 2, 3],
                    'open': [100, 101, 102],
                    'high': [103, 104, 105],
                    'low': [98, 99, 100],
                    'close': [101, 102, 103],
                    'volume': [1000, 1100, 1200]
                }).to_dict('records'),
                'orderbook': {
                    'bids': [['49999', '1.0']],
                    'asks': [['50001', '1.0']]
                },
                'trades': [{
                    'price': '50000',
                    'qty': '1.0',
                    'time': int(timestamp.timestamp() * 1000)
                }]
            },
            'advanced_analysis': {
                'indicators': {
                    'RSI': 65.5,
                    'MACD': {
                        'value': 100.0,
                        'signal': 95.0,
                        'histogram': 5.0
                    },
                    'ADX': 25.0,
                    'ATR': 15.0
                },
                'signals': {
                    'trend': 'bullish',
                    'strength': 'strong'
                }
            }
        }
        
        self.mock_collector.get_complete_analysis.return_value = complete_analysis
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertTrue(result)
        self.mock_collector.get_complete_analysis.assert_called_once_with(symbol)
        self.mock_db.save_market_data.assert_called_once()
        self.mock_db.save_advanced_indicators.assert_called_once()

    def test_update_market_data_failure(self):
        """Test de la gestion des erreurs lors de la mise à jour"""
        symbol = 'BTCUSDT'
        
        # Configuration du mock pour lever une exception
        self.mock_collector.get_complete_analysis.side_effect = Exception("API Error")
        
        # Configuration du mock pour que le fallback échoue aussi
        self.mock_collector.get_ticker.side_effect = Exception("API Error")
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertFalse(result)
        self.assertEqual(self.market_updater.error_counts[symbol], 1)
        self.mock_db.save_market_data.assert_not_called()

    def test_run_and_stop(self):
        """Test du démarrage et de l'arrêt du service"""
        # Configuration des mocks pour une exécution réussie
        self.mock_collector.get_complete_analysis.return_value = {
            'timestamp': datetime.now(),
            'basic_analysis': {
                'ticker': {'price': 50000.0}
            },
            'advanced_analysis': {
                'indicators': {'RSI': 65.5},
                'signals': {'trend': 'bullish'}
            }
        }
        
        # Démarrage du service dans un thread séparé
        self.market_updater.start()
        
        # Attente d'au moins une mise à jour
        time.sleep(0.2)
        
        # Arrêt du service
        self.market_updater.stop()
        
        # Attente de l'arrêt complet
        self.market_updater.shutdown_complete.wait(timeout=1)
        
        # Vérifications
        self.mock_db.save_market_data.assert_called()
        self.mock_db.save_advanced_indicators.assert_called()
        self.assertTrue(self.market_updater.stop_event.is_set())

    def test_api_health_check_failure(self):
        """Test de la gestion d'une API non disponible"""
        symbol = 'BTCUSDT'
        
        # Configuration du mock pour simuler une API non disponible
        self.mock_api_monitor.check_api_health.return_value = {"status": "ERROR"}
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertFalse(result)
        self.assertEqual(self.market_updater.error_counts[symbol], 1)
        self.mock_collector.get_complete_analysis.assert_not_called()
        self.mock_db.save_market_data.assert_not_called()

    def test_fallback_to_legacy_update(self):
        """Test du fallback vers l'ancien système en cas d'échec"""
        symbol = "BTCUSDT"
        timestamp = datetime.now()
        
        # Simuler un échec de l'analyse complète
        self.mock_collector.get_complete_analysis.side_effect = Exception("Analysis failed")
        
        # Configurer les mocks pour le mode legacy
        self.mock_collector.get_ticker.return_value = {
            'symbol': symbol,
            'last_price': '50000',
            'volume_24h': '1000'
        }
        self.mock_collector.get_klines.return_value = pd.DataFrame({
            'timestamp': [1, 2, 3],
            'close': [101, 102, 103]
        })
        self.mock_collector.get_order_book.return_value = {
            'bids': [['49999', '1.0']],
            'asks': [['50001', '1.0']]
        }
        self.mock_collector.get_public_trade_history.return_value = [{
            'price': '50000',
            'qty': '1.0',
            'time': int(timestamp.timestamp() * 1000)
        }]
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertTrue(result)
        self.mock_collector.get_ticker.assert_called_once()
        self.mock_collector.get_klines.assert_called_once()
        self.mock_db.save_market_data.assert_called_once()

    def test_error_handling_and_retry(self):
        """Test de la gestion des erreurs et des tentatives de reconnexion"""
        symbol = "BTCUSDT"
        timestamp = datetime.now()
        
        # Simuler des échecs successifs
        self.mock_collector.get_complete_analysis.side_effect = [
            Exception("First failure"),
            {  # Succès à la deuxième tentative
                'timestamp': timestamp,
                'basic_analysis': {
                    'ticker': {'price': 50000.0}
                },
                'advanced_analysis': {
                    'indicators': {'RSI': 65.5},
                    'signals': {'trend': 'bullish'}
                }
            }
        ]
        
        # Configuration du mock pour que le fallback échoue aussi
        self.mock_collector.get_ticker.side_effect = Exception("API Error")
        
        # Première tentative (échec)
        result1 = self.market_updater.update_market_data(symbol)
        self.assertFalse(result1)
        self.assertEqual(self.market_updater.error_counts[symbol], 1)
        
        # Deuxième tentative (succès)
        result2 = self.market_updater.update_market_data(symbol)
        self.assertTrue(result2)
        self.assertEqual(self.market_updater.error_counts[symbol], 0)

    def test_cache_management(self):
        """Test de la gestion du cache des indicateurs"""
        symbol = "BTCUSDT"
        timestamp = datetime.now()
        
        # Mock de l'analyse avec des indicateurs à mettre en cache
        analysis = {
            'timestamp': timestamp,
            'basic_analysis': {
                'ticker': {'price': 50000.0}
            },
            'advanced_analysis': {
                'indicators': {
                    'ADX': 25.0,
                    'ATR': 15.0
                },
                'signals': {
                    'trend': 'bullish'
                }
            }
        }
        
        self.mock_collector.get_complete_analysis.return_value = analysis
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertTrue(result)
        self.mock_db.save_market_data.assert_called_once()
        market_data = self.mock_db.save_market_data.call_args[0][0]
        self.assertIn('cached_indicators', market_data)
        self.assertEqual(market_data['cached_indicators']['common']['ADX'], 25.0)
        self.assertEqual(market_data['cached_indicators']['common']['ATR'], 15.0)

    def test_update_deduplication(self):
        """Test que les mises à jour trop rapprochées sont différées"""
        symbol = "BTCUSDT"
        
        # Configuration des mocks avec les bonnes méthodes
        self.mock_collector.get_complete_analysis.return_value = {
            'timestamp': datetime.now(),
            'basic_analysis': {
                'ticker': {'price': 50000.0}
            },
            'advanced_analysis': {
                'indicators': {'RSI': 65.5},
                'signals': {'trend': 'bullish'}
            }
        }
        
        # Première mise à jour
        self.assertTrue(self.market_updater.update_market_data(symbol))
        first_update_time = self.market_updater.last_update[symbol]
        
        # Tentative de mise à jour immédiate
        self.assertTrue(self.market_updater.update_market_data(symbol))
        
        # Vérifier que le mock n'a été appelé qu'une seule fois
        self.assertEqual(self.mock_collector.get_complete_analysis.call_count, 1)
        
        # Attendre que l'intervalle soit passé
        time.sleep(self.market_updater.update_interval + 0.1)
        
        # Nouvelle mise à jour
        self.assertTrue(self.market_updater.update_market_data(symbol))
        second_update_time = self.market_updater.last_update[symbol]
        
        # Vérifier que la deuxième mise à jour a bien eu lieu
        self.assertEqual(self.mock_collector.get_complete_analysis.call_count, 2)
        self.assertGreater(second_update_time, first_update_time)

    def test_graceful_shutdown(self):
        """Test de l'arrêt propre du service"""
        # Démarrer le service
        self.market_updater.start()
        time.sleep(0.2)  # Laisser le temps au thread de démarrer
        
        # Vérifier que le service tourne
        self.assertTrue(self.market_updater.update_thread.is_alive())
        
        # Sauvegarder une référence au thread
        update_thread = self.market_updater.update_thread
        
        # Demander l'arrêt
        self.market_updater.stop()
        
        # Vérifier que le thread s'est arrêté proprement
        update_thread.join(timeout=2)
        self.assertFalse(update_thread.is_alive())
        self.assertTrue(self.market_updater.shutdown_complete.is_set())

    def test_complete_market_data_update(self):
        """Test de la mise à jour complète des données avec indicateurs avancés"""
        symbol = "BTCUSDT"
        timestamp = datetime.now()
        
        # Mock de l'analyse complète
        complete_analysis = {
            'timestamp': timestamp,
            'basic_analysis': {
                'ticker': {'price': 50000.0},
                'klines': pd.DataFrame({
                    'timestamp': [1, 2, 3],
                    'open': [100, 101, 102],
                    'high': [103, 104, 105],
                    'low': [98, 99, 100],
                    'close': [101, 102, 103],
                    'volume': [1000, 1100, 1200]
                }).to_dict('records'),
                'orderbook': {
                    'bids': [['49999', '1.0']],
                    'asks': [['50001', '1.0']]
                },
                'trades': [{
                    'price': '50000',
                    'qty': '1.0',
                    'time': int(timestamp.timestamp() * 1000)
                }]
            },
            'advanced_analysis': {
                'indicators': {
                    'RSI': 65.5,
                    'MACD': {
                        'value': 100.0,
                        'signal': 95.0,
                        'histogram': 5.0
                    },
                    'ADX': 25.0,
                    'ATR': 15.0
                },
                'signals': {
                    'trend': 'bullish',
                    'strength': 'strong'
                }
            }
        }
        
        self.mock_collector.get_complete_analysis.return_value = complete_analysis
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertTrue(result)
        self.mock_collector.get_complete_analysis.assert_called_once()
        self.mock_db.save_market_data.assert_called_once()
        self.mock_db.save_advanced_indicators.assert_called_once()

    def test_advanced_indicators_calculation(self):
        """Test du calcul des indicateurs avancés"""
        symbol = "BTCUSDT"
        timestamp = datetime.now()
        
        # Mock de l'analyse complète avec les indicateurs avancés
        complete_analysis = {
            'timestamp': timestamp,
            'basic_analysis': {
                'ticker': {'price': 50000.0},
                'klines': pd.DataFrame({
                    'timestamp': [1, 2, 3],
                    'close': [101, 102, 103]
                }).to_dict('records')
            },
            'advanced_analysis': {
                'indicators': {
                    'ADX': 25.0,
                    'ATR': 15.0,
                    'SuperTrend': {
                        'value': 102.5,
                        'direction': 'up'
                    }
                },
                'signals': {
                    'trend': 'bullish'
                }
            }
        }
        
        self.mock_collector.get_complete_analysis.return_value = complete_analysis
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertTrue(result)
        self.mock_collector.get_complete_analysis.assert_called_once()
        self.mock_db.save_market_data.assert_called_once()
        self.mock_db.save_advanced_indicators.assert_called_once()

    def test_advanced_indicators_validation(self):
        """Test la validation des indicateurs avancés"""
        symbol = "BTCUSDT"
        timestamp = datetime.now()
        
        # Mock avec des indicateurs invalides
        invalid_analysis = {
            'timestamp': timestamp,
            'basic_analysis': {
                'ticker': {'price': 50000.0}
            },
            'advanced_analysis': {
                'indicators': {
                    'MACD': 'invalid_value',  # Devrait être un dict
                    'ADX': -5.0,  # Valeur invalide
                    'ATR': None   # Valeur manquante
                },
                'signals': {
                    'trend': 'invalid_trend'
                }
            }
        }
        
        self.mock_collector.get_complete_analysis.return_value = invalid_analysis
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # La mise à jour doit réussir même avec des indicateurs invalides
        self.assertTrue(result)
        # Mais les indicateurs invalides ne doivent pas être sauvegardés
        self.mock_db.save_advanced_indicators.assert_not_called()

    def test_indicator_calculation_frequency(self):
        """Test la fréquence de calcul des indicateurs"""
        symbol = "BTCUSDT"
        timestamp = datetime.now()
        
        # Configuration initiale
        complete_analysis = {
            'timestamp': timestamp,
            'basic_analysis': {
                'ticker': {'price': 50000.0}
            },
            'advanced_analysis': {
                'indicators': {'RSI': 65.5},
                'signals': {'trend': 'bullish'}
            }
        }
        
        self.mock_collector.get_complete_analysis.return_value = complete_analysis
        
        # Première mise à jour
        self.market_updater.update_market_data(symbol)
        first_call_time = time.time()
        
        # Deuxième mise à jour immédiate
        self.market_updater.update_market_data(symbol)
        
        # Vérifier que le calcul n'a été fait qu'une seule fois
        self.assertEqual(self.mock_collector.get_complete_analysis.call_count, 1)
        
        # Attendre que l'intervalle soit passé
        time.sleep(self.market_updater.update_interval + 0.1)
        
        # Troisième mise à jour
        self.market_updater.update_market_data(symbol)
        
        # Vérifier que le calcul a été fait une deuxième fois
        self.assertEqual(self.mock_collector.get_complete_analysis.call_count, 2)

    def test_advanced_indicators_persistence(self):
        """Test la persistance des indicateurs avancés"""
        symbol = "BTCUSDT"
        timestamp = datetime.now()
        
        # Mock avec un ensemble complet d'indicateurs
        complete_analysis = {
            'timestamp': timestamp,
            'basic_analysis': {
                'ticker': {'price': 50000.0}
            },
            'advanced_analysis': {
                'indicators': {
                    'MACD': {
                        'value': 100.0,
                        'signal': 95.0,
                        'histogram': 5.0
                    },
                    'ADX': 25.0,
                    'ATR': 15.0,
                    'SuperTrend': {
                        'value': 49500.0,
                        'direction': 1
                    }
                },
                'signals': {
                    'trend': 'bullish',
                    'strength': 'strong',
                    'volatility': 'medium'
                }
            }
        }
        
        self.mock_collector.get_complete_analysis.return_value = complete_analysis
        
        # Exécution de la mise à jour
        result = self.market_updater.update_market_data(symbol)
        
        # Vérifications
        self.assertTrue(result)
        
        # Vérifier que les données sont correctement structurées pour la persistance
        market_data = self.mock_db.save_market_data.call_args[0][0]
        self.assertIn('cached_indicators', market_data)
        self.assertEqual(market_data['cached_indicators']['common']['ADX'], 25.0)
        self.assertEqual(market_data['cached_indicators']['common']['ATR'], 15.0)
        
        # Vérifier la structure des indicateurs avancés
        advanced_data = self.mock_db.save_advanced_indicators.call_args[0][1]
        self.assertEqual(advanced_data['type'], 'advanced')
        self.assertIn('MACD', advanced_data['data']['indicators'])
        self.assertIn('SuperTrend', advanced_data['data']['indicators'])
        self.assertEqual(advanced_data['data']['signals']['trend'], 'bullish')

if __name__ == '__main__':
    unittest.main()
