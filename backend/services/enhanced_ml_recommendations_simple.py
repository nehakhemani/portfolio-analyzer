import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import yfinance as yf
from datetime import datetime, timedelta
import time
import logging
import warnings
warnings.filterwarnings('ignore')

# Import the new sentiment analyzer
from .market_sentiment import MarketSentimentAnalyzer

class EnhancedMLRecommendationEngine:
    """
    Enhanced ML Recommendation Engine using custom algorithms
    instead of scikit-learn to avoid compilation issues
    """
    
    def __init__(self):
        self.request_delay = 0.5
        self.sentiment_analyzer = MarketSentimentAnalyzer()
        self.feature_weights = {
            'return_weight': 0.25,
            'momentum_weight': 0.18,
            'volatility_weight': 0.12,
            'technical_weight': 0.12,
            'fundamental_weight': 0.08,
            'volume_weight': 0.08,
            'sentiment_weight': 0.17  # New sentiment weight
        }
        
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
        
        # Normalize features across portfolio
        normalized_features = self.normalize_features(features_list)
        
        # Generate recommendations
        for idx, (features, normalized, (_, holding)) in enumerate(zip(features_list, normalized_features, holdings_df.iterrows())):
            rec = self.create_enhanced_recommendation(
                holding['ticker'], holding, features, normalized
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
            
            # Market sentiment features (technical)
            features.update(self.calculate_sentiment_features(hist))
            
            # Real market sentiment analysis
            print(f"Analyzing market sentiment for {ticker}...")
            sentiment_data = self.sentiment_analyzer.get_comprehensive_sentiment(ticker)
            features.update(self.extract_sentiment_features(sentiment_data))
            
        except Exception as e:
            logging.error(f"Could not fetch comprehensive data for {ticker}: {e}")
            # Fill with default values
            features.update({
                'rsi': 50, 'sma_ratio': 1.0, 'bb_position': 0.5,
                'volatility': 20, 'momentum_5d': 0, 'momentum_20d': 0,
                'pe_ratio': 20, 'market_cap': 1e9, 'price_to_book': 2.0,
                'debt_to_equity': 0.5, 'volume_trend': 0, 'price_trend': 0,
                'beta': 1.0, 'profit_margin': 0.1,
                # Default sentiment values when no data available
                'news_sentiment': 0, 'social_sentiment': 0, 'market_fear_greed': 0,
                'analyst_upside': 0, 'analyst_rec_score': 0, 'composite_sentiment': 0,
                'sentiment_strength_score': 0, 'market_regime_score': 0, 'vix_level': 20
            })
        
        return features
    
    def calculate_technical_indicators(self, hist: pd.DataFrame) -> dict:
        """Calculate technical analysis indicators using custom implementations"""
        indicators = {}
        closes = hist['Close']
        current_price = closes.iloc[-1]
        
        try:
            # RSI (Relative Strength Index)
            deltas = closes.diff()
            gains = deltas.where(deltas > 0, 0)
            losses = -deltas.where(deltas < 0, 0)
            
            # Use simple moving average for RSI
            avg_gains = gains.rolling(window=14).mean()
            avg_losses = losses.rolling(window=14).mean()
            
            rs = avg_gains / avg_losses
            rsi = 100 - (100 / (1 + rs))
            indicators['rsi'] = rsi.iloc[-1] if not rsi.empty else 50
            
            # Simple Moving Average ratio
            sma_20 = closes.rolling(window=20).mean()
            indicators['sma_ratio'] = current_price / sma_20.iloc[-1] if sma_20.iloc[-1] > 0 else 1.0
            
            # Bollinger Bands position
            sma_20_val = sma_20.iloc[-1]
            std_20 = closes.rolling(window=20).std().iloc[-1]
            upper_band = sma_20_val + (2 * std_20)
            lower_band = sma_20_val - (2 * std_20)
            
            if upper_band != lower_band:
                indicators['bb_position'] = (current_price - lower_band) / (upper_band - lower_band)
            else:
                indicators['bb_position'] = 0.5
                
        except Exception as e:
            logging.error(f"Error calculating technical indicators: {e}")
            indicators = {
                'rsi': 50, 'sma_ratio': 1.0, 'bb_position': 0.5
            }
        
        return indicators
    
    def extract_fundamental_features(self, info: dict) -> dict:
        """Extract fundamental analysis features"""
        return {
            'pe_ratio': info.get('forwardPE', info.get('trailingPE', 20)) or 20,
            'market_cap': info.get('marketCap', 1e9) or 1e9,
            'price_to_book': info.get('priceToBook', 2.0) or 2.0,
            'debt_to_equity': (info.get('debtToEquity', 50) or 50) / 100,
            'profit_margin': info.get('profitMargins', 0.1) or 0.1,
            'beta': info.get('beta', 1.0) or 1.0
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
        if len(volumes) >= 20:
            recent_vol = volumes.iloc[-5:].mean()
            older_vol = volumes.iloc[-20:-5].mean()
            volume_trend = (recent_vol / older_vol - 1) * 100 if older_vol > 0 else 0
        else:
            volume_trend = 0
        
        # Price trend strength (correlation coefficient)
        if len(closes) > 1:
            x = np.arange(len(closes))
            price_trend = np.corrcoef(x, closes)[0, 1]
        else:
            price_trend = 0
        
        return {
            'volatility': volatility,
            'momentum_5d': momentum_5d,
            'momentum_20d': momentum_20d,
            'volume_trend': volume_trend,
            'price_trend': price_trend
        }
    
    def extract_sentiment_features(self, sentiment_data: Dict) -> Dict:
        """Extract features from comprehensive sentiment analysis"""
        return {
            'news_sentiment': sentiment_data['news_sentiment']['score'],
            'news_volume': sentiment_data['news_sentiment']['articles_count'],
            'social_sentiment': sentiment_data['social_sentiment']['score'],
            'social_mentions': sentiment_data['social_sentiment']['mentions_count'],
            'social_trending': 1 if sentiment_data['social_sentiment']['trending'] else 0,
            'market_fear_greed': (sentiment_data['market_indicators']['fear_greed_index'] - 50) / 50,
            'vix_level': sentiment_data['market_indicators']['vix_level'],
            'market_regime_score': self._market_regime_to_score(sentiment_data['market_indicators']['market_regime']),
            'analyst_upside': sentiment_data['analyst_sentiment']['upside_potential'],
            'analyst_rec_score': self._analyst_rec_to_score(sentiment_data['analyst_sentiment']['recommendation']),
            'composite_sentiment': sentiment_data['composite_score'],
            'sentiment_strength_score': self._sentiment_strength_to_score(sentiment_data['sentiment_strength']),
            'sentiment_summary': sentiment_data.get('sentiment_summary', '')
        }
    
    def _market_regime_to_score(self, regime: str) -> float:
        """Convert market regime to numerical score"""
        regime_scores = {
            'crisis': -1.0,
            'volatile': -0.5,
            'normal': 0.0,
            'complacent': 0.5,
            'euphoric': 0.3  # Slightly positive but risky
        }
        return regime_scores.get(regime, 0.0)
    
    def _analyst_rec_to_score(self, recommendation: str) -> float:
        """Convert analyst recommendation to numerical score"""
        rec_scores = {
            'strong_buy': 1.0,
            'buy': 0.5,
            'hold': 0.0,
            'sell': -0.5,
            'strong_sell': -1.0
        }
        return rec_scores.get(recommendation, 0.0)
    
    def _sentiment_strength_to_score(self, strength: str) -> float:
        """Convert sentiment strength to numerical score"""
        strength_scores = {
            'very_positive': 1.0,
            'positive': 0.5,
            'neutral': 0.0,
            'negative': -0.5,
            'very_negative': -1.0
        }
        return strength_scores.get(strength, 0.0)
    
    def normalize_features(self, features_list: List[dict]) -> List[dict]:
        """Normalize features across the portfolio for comparison"""
        if len(features_list) <= 1:
            return features_list
        
        # Extract numeric features for normalization
        numeric_features = ['current_return', 'volatility', 'momentum_5d', 'momentum_20d', 
                          'rsi', 'pe_ratio', 'market_cap', 'volume_trend',
                          'news_sentiment', 'social_sentiment', 'market_fear_greed', 
                          'analyst_upside', 'composite_sentiment']
        
        normalized_list = []
        
        for feature_key in numeric_features:
            values = [f.get(feature_key, 0) for f in features_list]
            if len(values) > 1:
                mean_val = np.mean(values)
                std_val = np.std(values)
                
                if std_val > 0:
                    for i, features in enumerate(features_list):
                        if i >= len(normalized_list):
                            normalized_list.append({})
                        normalized_list[i][f'{feature_key}_norm'] = (features.get(feature_key, 0) - mean_val) / std_val
                else:
                    for i, features in enumerate(features_list):
                        if i >= len(normalized_list):
                            normalized_list.append({})
                        normalized_list[i][f'{feature_key}_norm'] = 0
        
        return normalized_list
    
    def create_enhanced_recommendation(self, ticker: str, holding: dict, 
                                     features: dict, normalized: dict) -> dict:
        """Create recommendation using custom ML-like scoring"""
        
        return_pct = features['current_return']
        
        # Calculate composite ML score
        ml_score = self.calculate_ml_score(features, normalized)
        
        # Risk assessment
        risk_score = self.calculate_risk_score(features)
        
        # Market regime detection
        market_regime = self.detect_market_regime(features)
        
        # Debug logging
        print(f"{ticker}: ML Score={ml_score:.1f}, Return={return_pct:.1f}%, Risk={risk_score}")
        
        # Generate recommendation based on ML score
        recommendation = self.score_to_recommendation(ml_score, return_pct, risk_score)
        
        # Generate rationale
        rationale = self.generate_rationale(features, risk_score, market_regime, ml_score)
        
        # Calculate confidence
        confidence = self.calculate_confidence(features, risk_score, ml_score)
        
        return {
            'ticker': ticker,
            'current_value': round(holding['end_value'], 2),
            'return_percentage': round(return_pct, 2),
            'recommendation': recommendation['action'],
            'action': recommendation['label'],
            'rationale': rationale,
            'target_action': recommendation['target'],
            'confidence': confidence,
            'ml_score': round(ml_score, 1),
            'risk_score': risk_score,
            'market_regime': market_regime,
            'data_source': 'Enhanced ML' if features.get('has_live_data', False) else 'Portfolio + Defaults'
        }
    
    def calculate_ml_score(self, features: dict, normalized: dict) -> float:
        """Calculate ML-like composite score using weighted features"""
        score = 50  # Base score
        
        # Return component (30% weight)
        return_pct = features['current_return']
        if return_pct > 50:
            score += 30 * self.feature_weights['return_weight']
        elif return_pct > 20:
            score += 15 * self.feature_weights['return_weight']
        elif return_pct < -20:
            score -= 25 * self.feature_weights['return_weight']
        elif return_pct < -10:
            score -= 10 * self.feature_weights['return_weight']
        
        # Momentum component (20% weight)
        momentum_5d = features.get('momentum_5d', 0)
        momentum_20d = features.get('momentum_20d', 0)
        
        momentum_score = 0
        if momentum_5d > 5:
            momentum_score += 15
        elif momentum_5d < -5:
            momentum_score -= 15
            
        if momentum_20d > 10:
            momentum_score += 20
        elif momentum_20d < -10:
            momentum_score -= 20
            
        score += momentum_score * self.feature_weights['momentum_weight']
        
        # Technical component (15% weight)
        rsi = features.get('rsi', 50)
        sma_ratio = features.get('sma_ratio', 1.0)
        
        technical_score = 0
        if rsi > 70:
            technical_score -= 20  # Overbought
        elif rsi < 30:
            technical_score += 20  # Oversold
            
        if sma_ratio > 1.1:
            technical_score += 10  # Above moving average
        elif sma_ratio < 0.9:
            technical_score -= 10  # Below moving average
            
        score += technical_score * self.feature_weights['technical_weight']
        
        # Volatility component (15% weight)
        volatility = features.get('volatility', 20)
        if volatility > 40:
            score -= 15  # High volatility penalty
        elif volatility < 15:
            score += 10  # Low volatility bonus
            
        score += (30 - min(volatility, 60)) * self.feature_weights['volatility_weight']
        
        # Fundamental component (10% weight)
        pe_ratio = features.get('pe_ratio', 20)
        fundamental_score = 0
        if pe_ratio < 15:
            fundamental_score += 15  # Undervalued
        elif pe_ratio > 30:
            fundamental_score -= 15  # Overvalued
            
        score += fundamental_score * self.feature_weights['fundamental_weight']
        
        # Volume component (10% weight)
        volume_trend = features.get('volume_trend', 0)
        if volume_trend > 20:
            score += 10  # Increasing volume
        elif volume_trend < -20:
            score -= 10  # Decreasing volume
            
        score += min(max(volume_trend, -30), 30) * self.feature_weights['volume_weight']
        
        # Sentiment component (17% weight) - NEW!
        sentiment_score = 0
        
        # News sentiment
        news_sentiment = features.get('news_sentiment', 0)
        sentiment_score += news_sentiment * 15
        
        # Social sentiment  
        social_sentiment = features.get('social_sentiment', 0)
        sentiment_score += social_sentiment * 10
        
        # Market regime
        market_regime_score = features.get('market_regime_score', 0)
        sentiment_score += market_regime_score * 8
        
        # Analyst recommendations
        analyst_rec_score = features.get('analyst_rec_score', 0)
        sentiment_score += analyst_rec_score * 12
        
        # Fear/Greed index
        fear_greed = features.get('market_fear_greed', 0)
        sentiment_score += fear_greed * 5
        
        # Composite sentiment (master sentiment score)
        composite_sentiment = features.get('composite_sentiment', 0)
        sentiment_score += composite_sentiment * 20
        
        score += sentiment_score * self.feature_weights['sentiment_weight']
        
        return max(min(score, 100), 0)  # Clamp between 0-100
    
    def calculate_risk_score(self, features: dict) -> int:
        """Calculate risk score (0-100)"""
        risk_score = 30  # Base risk
        
        # Volatility risk
        volatility = features.get('volatility', 20)
        if volatility > 40:
            risk_score += 25
        elif volatility > 25:
            risk_score += 15
        elif volatility < 15:
            risk_score -= 10
        
        # Momentum risk
        momentum_5d = abs(features.get('momentum_5d', 0))
        if momentum_5d > 15:
            risk_score += 15
        elif momentum_5d > 8:
            risk_score += 8
        
        # Beta risk
        beta = features.get('beta', 1.0)
        if beta > 1.5:
            risk_score += 10
        elif beta < 0.8:
            risk_score += 5
        
        # Technical risk
        rsi = features.get('rsi', 50)
        if rsi > 80 or rsi < 20:
            risk_score += 15
        elif rsi > 70 or rsi < 30:
            risk_score += 8
        
        # Fundamental risk
        pe_ratio = features.get('pe_ratio', 20)
        if pe_ratio > 40:
            risk_score += 10
        elif pe_ratio < 5:
            risk_score += 15  # Too low might indicate problems
        
        return min(max(risk_score, 0), 100)
    
    def detect_market_regime(self, features: dict) -> str:
        """Detect current market regime"""
        momentum_20d = features.get('momentum_20d', 0)
        volatility = features.get('volatility', 20)
        volume_trend = features.get('volume_trend', 0)
        price_trend = features.get('price_trend', 0)
        
        if momentum_20d > 15 and volatility < 25 and price_trend > 0.3:
            return "Strong Bull"
        elif momentum_20d > 5 and volatility < 30:
            return "Bull Market"
        elif momentum_20d < -15 and volatility > 30:
            return "Bear Market"
        elif volatility > 40:
            return "High Volatility"
        elif abs(momentum_20d) < 5 and volatility < 20:
            return "Sideways"
        else:
            return "Transitional"
    
    def score_to_recommendation(self, ml_score: float, return_pct: float, risk_score: int) -> dict:
        """Convert ML score to recommendation with more dynamic thresholds"""
        
        # Exceptional opportunities (top 10%)
        if ml_score > 70:
            if return_pct > 40:
                return {'action': 'SELL', 'label': 'Take Profits', 'target': 'Sell 30-50% of position'}
            else:
                return {'action': 'BUY', 'label': 'Strong Buy', 'target': 'Consider adding to position'}
        
        # Good opportunities (above average)
        elif ml_score > 55:
            if return_pct > 25:
                return {'action': 'HOLD', 'label': 'Strong Hold', 'target': 'Set trailing stop at 15%'}
            elif return_pct < -15:
                return {'action': 'BUY', 'label': 'Buy the Dip', 'target': 'Dollar-cost average'}
            else:
                return {'action': 'BUY', 'label': 'Buy Signal', 'target': 'Consider entry'}
        
        # Above neutral (slightly positive)
        elif ml_score > 45:
            if return_pct > 20:
                return {'action': 'HOLD', 'label': 'Hold with Caution', 'target': 'Monitor for exit signals'}
            elif return_pct < -10:
                return {'action': 'BUY', 'label': 'Potential Entry', 'target': 'Small position'}
            else:
                return {'action': 'HOLD', 'label': 'Neutral Hold', 'target': 'Monitor position'}
        
        # Below average performance
        elif ml_score > 35:
            if risk_score > 65 or return_pct < -20:
                return {'action': 'SELL', 'label': 'Risk Management', 'target': 'Reduce position by 30-50%'}
            else:
                return {'action': 'HOLD', 'label': 'Weak Hold', 'target': 'Consider exit strategy'}
        
        # Poor performance (bottom 20%)
        else:
            if return_pct > 10:  # Still profitable despite poor score
                return {'action': 'SELL', 'label': 'Take Some Profits', 'target': 'Sell 50% of position'}
            else:
                return {'action': 'SELL', 'label': 'Strong Sell', 'target': 'Exit position'}
    
    def generate_rationale(self, features: dict, risk_score: int, 
                          market_regime: str, ml_score: float) -> str:
        """Generate detailed rationale"""
        parts = []
        
        return_pct = features['current_return']
        parts.append(f"Return: {return_pct:.1f}%")
        parts.append(f"ML Score: {ml_score:.0f}/100")
        
        if features.get('has_live_data', False):
            rsi = features.get('rsi', 50)
            if rsi > 70:
                parts.append(f"Overbought (RSI: {rsi:.0f})")
            elif rsi < 30:
                parts.append(f"Oversold (RSI: {rsi:.0f})")
            
            momentum = features.get('momentum_5d', 0)
            if abs(momentum) > 5:
                parts.append(f"5d momentum: {momentum:+.1f}%")
                
            volatility = features.get('volatility', 20)
            if volatility > 30:
                parts.append(f"High volatility: {volatility:.0f}%")
        
        parts.append(f"Risk: {risk_score}/100")
        parts.append(f"Regime: {market_regime}")
        
        # Add sentiment insights
        if features.get('composite_sentiment') is not None:
            sentiment = features['composite_sentiment']
            sentiment_strength = features.get('sentiment_strength_score', 0)
            
            if abs(sentiment) > 0.3:
                sentiment_desc = "Very Positive" if sentiment > 0.6 else "Positive" if sentiment > 0.2 else "Very Negative" if sentiment < -0.6 else "Negative"
                parts.append(f"Sentiment: {sentiment_desc}")
            
            # News sentiment
            news_sentiment = features.get('news_sentiment', 0)
            if abs(news_sentiment) > 0.2:
                news_desc = "Positive News" if news_sentiment > 0 else "Negative News"
                parts.append(news_desc)
            
            # Social trending
            if features.get('social_trending', 0) == 1:
                parts.append("Trending")
            
            # Analyst recommendations
            analyst_upside = features.get('analyst_upside', 0)
            if abs(analyst_upside) > 10:
                parts.append(f"Analyst Target: {analyst_upside:+.0f}%")
        
        return " | ".join(parts)
    
    def calculate_confidence(self, features: dict, risk_score: int, ml_score: float) -> int:
        """Calculate final confidence score"""
        base_confidence = 50
        
        # Data quality boost
        if features.get('has_live_data', False):
            base_confidence += 20
        
        # ML score confidence boost
        score_deviation = abs(ml_score - 50)
        base_confidence += min(score_deviation / 2, 20)
        
        # Risk-adjusted confidence
        if risk_score > 70:
            base_confidence -= 15
        elif risk_score < 40:
            base_confidence += 10
        
        # Return magnitude boost
        return_pct = abs(features['current_return'])
        if return_pct > 50:
            base_confidence += 10
        elif return_pct > 30:
            base_confidence += 5
        
        return min(max(base_confidence, 30), 95)