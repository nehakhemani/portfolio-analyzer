import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import yfinance as yf
from datetime import datetime, timedelta
import time
import logging
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import warnings
warnings.filterwarnings('ignore')

try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logging.warning("TA library not available. Install with: pip install ta")

class EnhancedMLRecommendationEngine:
    def __init__(self):
        self.request_delay = 0.5
        self.scaler = StandardScaler()
        self.rf_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.gb_model = GradientBoostingClassifier(n_estimators=100, random_state=42)
        self.kmeans_model = KMeans(n_clusters=5, random_state=42)
        self.trained = False
        
    def generate_recommendations(self, holdings_df: pd.DataFrame) -> List[Dict]:
        """Generate enhanced ML-powered recommendations"""
        recommendations = []
        
        print(f"Generating enhanced ML recommendations for {len(holdings_df)} holdings...")
        
        # Extract features for all holdings
        features_list = []
        for idx, (_, holding) in enumerate(holdings_df.iterrows()):
            ticker = holding['ticker']
            print(f"Processing {ticker} ({idx+1}/{len(holdings_df)})...")
            
            features = self.extract_comprehensive_features(ticker, holding)
            features_list.append(features)
            
            if idx < len(holdings_df) - 1:
                time.sleep(self.request_delay)
        
        # Create feature matrix
        feature_matrix = self.create_feature_matrix(features_list)
        
        # Train models on current data if we have enough samples
        if len(feature_matrix) >= 5:
            self.train_models(feature_matrix, holdings_df)
        
        # Generate recommendations
        for idx, (features, (_, holding)) in enumerate(zip(features_list, holdings_df.iterrows())):
            rec = self.create_enhanced_recommendation(
                holding['ticker'], holding, features, feature_matrix, idx
            )
            recommendations.append(rec)
        
        return recommendations
    
    def extract_comprehensive_features(self, ticker: str, holding: dict) -> dict:
        """Extract comprehensive features for ML analysis"""
        features = {
            'ticker': ticker,
            'current_return': ((holding['end_value'] - holding['start_value']) / holding['start_value'] * 100) if holding['start_value'] > 0 else 0,
            'dividend_yield': (holding['dividends'] / holding['start_value'] * 100) if holding['start_value'] > 0 else 0,
            'position_size': holding['end_value'],
            'has_live_data': False
        }
        
        try:
            stock = yf.Ticker(ticker)
            
            # Get historical data (3 months for better analysis)
            hist = stock.history(period="3mo")
            if hist.empty:
                raise Exception("No historical data")
            
            # Get stock info
            info = stock.info
            
            # Basic price features
            current_price = hist['Close'].iloc[-1]
            features.update({
                'current_price': current_price,
                'volume_avg': hist['Volume'].mean(),
                'has_live_data': True
            })
            
            # Technical indicators
            if len(hist) >= 20:
                features.update(self.calculate_technical_indicators(hist))
            
            # Fundamental features from info
            features.update(self.extract_fundamental_features(info))
            
            # Market sentiment features
            features.update(self.calculate_sentiment_features(hist))
            
        except Exception as e:
            logging.error(f"Could not fetch comprehensive data for {ticker}: {e}")
            # Fill with default values
            features.update({
                'rsi': 50, 'macd_signal': 0, 'bb_position': 0.5,
                'price_ma_ratio': 1.0, 'volatility': 20, 'momentum_5d': 0,
                'momentum_20d': 0, 'pe_ratio': 20, 'market_cap': 1e9,
                'price_to_book': 2.0, 'debt_to_equity': 0.5,
                'volume_trend': 0, 'price_trend': 0
            })
        
        return features
    
    def calculate_technical_indicators(self, hist: pd.DataFrame) -> dict:
        """Calculate technical analysis indicators"""
        indicators = {}
        
        try:
            if TA_AVAILABLE and len(hist) >= 20:
                # RSI
                indicators['rsi'] = ta.momentum.rsi(hist['Close']).iloc[-1]
                
                # MACD
                macd_line = ta.trend.macd(hist['Close']).iloc[-1]
                macd_signal = ta.trend.macd_signal(hist['Close']).iloc[-1]
                indicators['macd_signal'] = 1 if macd_line > macd_signal else -1
                
                # Bollinger Bands position
                bb_high = ta.volatility.bollinger_hband(hist['Close']).iloc[-1]
                bb_low = ta.volatility.bollinger_lband(hist['Close']).iloc[-1]
                current_price = hist['Close'].iloc[-1]
                indicators['bb_position'] = (current_price - bb_low) / (bb_high - bb_low) if bb_high != bb_low else 0.5
                
                # Moving average ratios
                sma_20 = ta.trend.sma_indicator(hist['Close'], window=20).iloc[-1]
                indicators['price_ma_ratio'] = current_price / sma_20 if sma_20 > 0 else 1.0
                
            else:
                # Manual calculation for basic indicators
                closes = hist['Close']
                current_price = closes.iloc[-1]
                
                # Simple RSI approximation
                deltas = closes.diff()
                gains = deltas.where(deltas > 0, 0).rolling(window=14).mean()
                losses = (-deltas.where(deltas < 0, 0)).rolling(window=14).mean()
                rs = gains / losses
                indicators['rsi'] = 100 - (100 / (1 + rs.iloc[-1])) if not rs.empty else 50
                
                # Moving average ratio
                ma_20 = closes.rolling(window=20).mean().iloc[-1]
                indicators['price_ma_ratio'] = current_price / ma_20 if ma_20 > 0 else 1.0
                
                # Default values for others
                indicators.update({
                    'macd_signal': 0, 'bb_position': 0.5
                })
                
        except Exception as e:
            logging.error(f"Error calculating technical indicators: {e}")
            indicators = {
                'rsi': 50, 'macd_signal': 0, 'bb_position': 0.5, 'price_ma_ratio': 1.0
            }
        
        return indicators
    
    def extract_fundamental_features(self, info: dict) -> dict:
        """Extract fundamental analysis features"""
        return {
            'pe_ratio': info.get('forwardPE', info.get('trailingPE', 20)),
            'market_cap': info.get('marketCap', 1e9),
            'price_to_book': info.get('priceToBook', 2.0),
            'debt_to_equity': info.get('debtToEquity', 50) / 100 if info.get('debtToEquity') else 0.5,
            'profit_margin': info.get('profitMargins', 0.1),
            'beta': info.get('beta', 1.0)
        }
    
    def calculate_sentiment_features(self, hist: pd.DataFrame) -> dict:
        """Calculate market sentiment and momentum features"""
        closes = hist['Close']
        volumes = hist['Volume']
        
        # Price momentum
        momentum_5d = ((closes.iloc[-1] - closes.iloc[-6]) / closes.iloc[-6] * 100) if len(closes) >= 6 else 0
        momentum_20d = ((closes.iloc[-1] - closes.iloc[-21]) / closes.iloc[-21] * 100) if len(closes) >= 21 else 0
        
        # Volatility
        returns = closes.pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100 if len(returns) > 0 else 20
        
        # Volume trend
        volume_trend = (volumes.iloc[-5:].mean() / volumes.iloc[-20:-5].mean() - 1) * 100 if len(volumes) >= 20 else 0
        
        # Price trend strength
        price_trend = np.corrcoef(range(len(closes)), closes)[0, 1] if len(closes) > 1 else 0
        
        return {
            'volatility': volatility,
            'momentum_5d': momentum_5d,
            'momentum_20d': momentum_20d,
            'volume_trend': volume_trend,
            'price_trend': price_trend
        }
    
    def create_feature_matrix(self, features_list: List[dict]) -> pd.DataFrame:
        """Create feature matrix for ML models"""
        feature_columns = [
            'current_return', 'dividend_yield', 'position_size', 'rsi', 'macd_signal',
            'bb_position', 'price_ma_ratio', 'volatility', 'momentum_5d', 'momentum_20d',
            'pe_ratio', 'market_cap', 'price_to_book', 'debt_to_equity', 'volume_trend', 'price_trend'
        ]
        
        matrix_data = []
        for features in features_list:
            row = [features.get(col, 0) for col in feature_columns]
            matrix_data.append(row)
        
        return pd.DataFrame(matrix_data, columns=feature_columns)
    
    def train_models(self, feature_matrix: pd.DataFrame, holdings_df: pd.DataFrame):
        """Train ML models on current portfolio data"""
        try:
            # Create synthetic target based on current performance
            targets = []
            for _, holding in holdings_df.iterrows():
                return_pct = ((holding['end_value'] - holding['start_value']) / holding['start_value'] * 100) if holding['start_value'] > 0 else 0
                
                if return_pct > 30:
                    targets.append(2)  # SELL (take profits)
                elif return_pct < -20:
                    targets.append(0)  # SELL (cut losses)
                else:
                    targets.append(1)  # HOLD
            
            # Prepare data
            X = self.scaler.fit_transform(feature_matrix.fillna(0))
            y = np.array(targets)
            
            # Train models
            self.rf_model.fit(X, y)
            self.gb_model.fit(X, y)
            self.kmeans_model.fit(X)
            
            self.trained = True
            logging.info("ML models trained successfully")
            
        except Exception as e:
            logging.error(f"Error training models: {e}")
            self.trained = False
    
    def create_enhanced_recommendation(self, ticker: str, holding: dict, 
                                     features: dict, feature_matrix: pd.DataFrame, 
                                     idx: int) -> dict:
        """Create recommendation using ML models"""
        
        return_pct = features['current_return']
        
        # Base recommendation
        base_rec = self.get_base_recommendation(return_pct, features)
        
        # ML enhancement if models are trained
        if self.trained and len(feature_matrix) > idx:
            ml_rec = self.get_ml_recommendation(feature_matrix.iloc[idx:idx+1])
            confidence_boost = 15
        else:
            ml_rec = base_rec
            confidence_boost = 0
        
        # Risk assessment
        risk_score = self.calculate_risk_score(features)
        
        # Market regime detection
        market_regime = self.detect_market_regime(features)
        
        # Final recommendation logic
        final_action = self.combine_recommendations(base_rec, ml_rec, risk_score, market_regime)
        
        # Generate rationale
        rationale = self.generate_rationale(features, risk_score, market_regime, final_action)
        
        # Calculate confidence
        confidence = self.calculate_confidence(features, risk_score, confidence_boost)
        
        return {
            'ticker': ticker,
            'current_value': round(holding['end_value'], 2),
            'return_percentage': round(return_pct, 2),
            'recommendation': final_action['action'],
            'action': final_action['label'],
            'rationale': rationale,
            'target_action': final_action['target'],
            'confidence': confidence,
            'ml_score': final_action['score'],
            'risk_score': risk_score,
            'market_regime': market_regime,
            'data_source': 'Enhanced ML' if features.get('has_live_data', False) else 'Portfolio + Synthetic'
        }
    
    def get_base_recommendation(self, return_pct: float, features: dict) -> dict:
        """Get base recommendation from traditional analysis"""
        rsi = features.get('rsi', 50)
        volatility = features.get('volatility', 20)
        
        if return_pct > 50 and rsi > 70:
            return {'action': 'SELL', 'label': 'Take Profits', 'target': 'Sell 50-70%', 'score': 85}
        elif return_pct < -25 and volatility > 35:
            return {'action': 'SELL', 'label': 'Cut Losses', 'target': 'Exit position', 'score': 25}
        elif rsi < 30 and return_pct > -10:
            return {'action': 'BUY', 'label': 'Oversold Opportunity', 'target': 'Add to position', 'score': 75}
        elif return_pct > 20:
            return {'action': 'HOLD', 'label': 'Monitor Winner', 'target': 'Set trailing stop', 'score': 65}
        else:
            return {'action': 'HOLD', 'label': 'Maintain', 'target': 'Monitor quarterly', 'score': 50}
    
    def get_ml_recommendation(self, feature_row: pd.DataFrame) -> dict:
        """Get ML model recommendation"""
        try:
            X = self.scaler.transform(feature_row.fillna(0))
            
            # Get predictions from both models
            rf_pred = self.rf_model.predict(X)[0]
            gb_pred = self.gb_model.predict(X)[0]
            
            # Get probabilities for confidence
            rf_proba = self.rf_model.predict_proba(X)[0]
            gb_proba = self.gb_model.predict_proba(X)[0]
            
            # Ensemble prediction
            avg_proba = (rf_proba + gb_proba) / 2
            final_pred = np.argmax(avg_proba)
            confidence = np.max(avg_proba) * 100
            
            action_map = {
                0: {'action': 'SELL', 'label': 'ML: Cut Losses', 'target': 'Exit position', 'score': 30},
                1: {'action': 'HOLD', 'label': 'ML: Maintain', 'target': 'Monitor position', 'score': 50},
                2: {'action': 'SELL', 'label': 'ML: Take Profits', 'target': 'Reduce position', 'score': 80}
            }
            
            result = action_map[final_pred].copy()
            result['ml_confidence'] = confidence
            return result
            
        except Exception as e:
            logging.error(f"Error in ML prediction: {e}")
            return {'action': 'HOLD', 'label': 'Hold (ML Error)', 'target': 'Monitor', 'score': 50}
    
    def calculate_risk_score(self, features: dict) -> int:
        """Calculate risk score (0-100)"""
        risk_score = 50  # Base risk
        
        # Volatility risk
        volatility = features.get('volatility', 20)
        if volatility > 40:
            risk_score += 20
        elif volatility > 25:
            risk_score += 10
        
        # Momentum risk
        momentum_5d = abs(features.get('momentum_5d', 0))
        if momentum_5d > 10:
            risk_score += 10
        
        # Valuation risk
        pe_ratio = features.get('pe_ratio', 20)
        if pe_ratio > 30:
            risk_score += 10
        elif pe_ratio < 10:
            risk_score += 5
        
        # Technical risk
        rsi = features.get('rsi', 50)
        if rsi > 80 or rsi < 20:
            risk_score += 10
        
        return min(max(risk_score, 0), 100)
    
    def detect_market_regime(self, features: dict) -> str:
        """Detect current market regime"""
        momentum_20d = features.get('momentum_20d', 0)
        volatility = features.get('volatility', 20)
        volume_trend = features.get('volume_trend', 0)
        
        if momentum_20d > 10 and volatility < 25:
            return "Bull Market"
        elif momentum_20d < -10 and volatility > 30:
            return "Bear Market"
        elif volatility > 35:
            return "High Volatility"
        elif abs(momentum_20d) < 5 and volatility < 20:
            return "Sideways"
        else:
            return "Transitional"
    
    def combine_recommendations(self, base_rec: dict, ml_rec: dict, 
                              risk_score: int, market_regime: str) -> dict:
        """Combine different recommendation signals"""
        
        # Weight the recommendations
        base_weight = 0.6
        ml_weight = 0.4
        
        # Adjust weights based on market regime
        if market_regime in ["High Volatility", "Bear Market"]:
            base_weight = 0.8  # Trust traditional analysis more in volatile markets
            ml_weight = 0.2
        
        # Combine scores
        combined_score = (base_rec['score'] * base_weight + ml_rec['score'] * ml_weight)
        
        # Risk adjustment
        if risk_score > 75:
            if combined_score > 60:
                return {'action': 'SELL', 'label': 'High Risk Exit', 'target': 'Reduce exposure', 'score': combined_score}
        elif risk_score < 30:
            if combined_score < 40:
                return {'action': 'BUY', 'label': 'Low Risk Opportunity', 'target': 'Consider adding', 'score': combined_score}
        
        # Default to highest confidence recommendation
        if ml_rec.get('ml_confidence', 0) > 70 and self.trained:
            return ml_rec
        else:
            return base_rec
    
    def generate_rationale(self, features: dict, risk_score: int, 
                          market_regime: str, final_action: dict) -> str:
        """Generate detailed rationale"""
        parts = []
        
        return_pct = features['current_return']
        parts.append(f"Return: {return_pct:.1f}%")
        
        if features.get('has_live_data', False):
            rsi = features.get('rsi', 50)
            if rsi > 70:
                parts.append(f"Overbought (RSI: {rsi:.0f})")
            elif rsi < 30:
                parts.append(f"Oversold (RSI: {rsi:.0f})")
            
            momentum = features.get('momentum_5d', 0)
            if abs(momentum) > 5:
                parts.append(f"5-day momentum: {momentum:+.1f}%")
        
        parts.append(f"Risk: {risk_score}/100")
        parts.append(f"Market: {market_regime}")
        
        if self.trained:
            parts.append("ML-enhanced")
        
        return " | ".join(parts)
    
    def calculate_confidence(self, features: dict, risk_score: int, 
                           confidence_boost: int) -> int:
        """Calculate final confidence score"""
        base_confidence = 60
        
        # Data quality boost
        if features.get('has_live_data', False):
            base_confidence += 15
        
        # ML model boost
        base_confidence += confidence_boost
        
        # Risk-adjusted confidence
        if risk_score > 80:
            base_confidence -= 10
        elif risk_score < 30:
            base_confidence += 10
        
        # Return magnitude boost
        return_pct = abs(features['current_return'])
        if return_pct > 50:
            base_confidence += 10
        
        return min(max(base_confidence, 30), 95)