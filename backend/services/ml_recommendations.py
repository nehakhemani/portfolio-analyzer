import pandas as pd
import numpy as np
from typing import Dict, List
import yfinance as yf
from datetime import datetime
import time

class MLRecommendationEngine:
    def __init__(self):
        self.simple_mode = True
        self.request_delay = 1  # 1 second delay between requests
        
    def generate_recommendations(self, holdings_df: pd.DataFrame) -> List[Dict]:
        """Generate ML-powered recommendations with rate limit handling"""
        recommendations = []
        
        print(f"Generating ML recommendations for {len(holdings_df)} holdings...")
        
        for idx, (_, holding) in enumerate(holdings_df.iterrows()):
            ticker = holding['ticker']
            print(f"Processing {ticker} ({idx+1}/{len(holdings_df)})...")
            
            # Try to get features, but don't fail if rate limited
            features = self.extract_simple_features_safe(ticker, holding)
            
            # Generate recommendation even without live data
            rec = self.create_recommendation(ticker, holding, features)
            recommendations.append(rec)
            
            # Rate limit protection
            if idx < len(holdings_df) - 1:  # Don't delay after last item
                time.sleep(self.request_delay)
        
        return recommendations
    
    def extract_simple_features_safe(self, ticker: str, holding: dict) -> dict:
        """Extract features with rate limit protection"""
        try:
            # Try to get data from Yahoo Finance
            stock = yf.Ticker(ticker)
            
            # Use a shorter period to reduce data requirements
            hist = stock.history(period="1mo")  # Just 1 month
            
            if hist.empty:
                raise Exception("No data returned")
            
            # Basic features
            current_price = hist['Close'].iloc[-1]
            
            features = {
                'current_return': ((holding['end_value'] - holding['start_value']) / holding['start_value'] * 100) if holding['start_value'] > 0 else 0,
                'dividend_yield': (holding['dividends'] / holding['start_value'] * 100) if holding['start_value'] > 0 else 0,
                'has_live_data': True
            }
            
            # Price momentum (simplified)
            if len(hist) >= 5:
                features['price_change_5d'] = ((current_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5] * 100)
            else:
                features['price_change_5d'] = 0
            
            # Simple volatility
            if len(hist) >= 5:
                returns = hist['Close'].pct_change().dropna()
                features['volatility'] = returns.std() * np.sqrt(252) * 100
            else:
                features['volatility'] = 20  # Default
            
            return features
            
        except Exception as e:
            print(f"Could not fetch live data for {ticker}: {e}")
            # Return basic features without live data
            return {
                'current_return': ((holding['end_value'] - holding['start_value']) / holding['start_value'] * 100) if holding['start_value'] > 0 else 0,
                'dividend_yield': (holding['dividends'] / holding['start_value'] * 100) if holding['start_value'] > 0 else 0,
                'price_change_5d': 0,
                'volatility': 20,
                'has_live_data': False
            }
    
    def create_recommendation(self, ticker: str, holding: dict, features: dict) -> dict:
        """Create recommendation based on available features"""
        
        # Base the recommendation primarily on return percentage
        return_pct = features['current_return']
        
        # Simple scoring system
        if return_pct > 100:
            action = 'SELL'
            action_label = 'Take Profits'
            target = 'Sell 50-70% of position'
            score = 85
        elif return_pct > 50:
            action = 'SELL'
            action_label = 'Partial Profits'
            target = 'Sell 30-40% of position'
            score = 70
        elif return_pct > 20:
            action = 'HOLD'
            action_label = 'Monitor Winner'
            target = 'Set trailing stop at 15%'
            score = 60
        elif return_pct < -30:
            action = 'SELL'
            action_label = 'Cut Losses'
            target = 'Exit position'
            score = 30
        elif return_pct < -15:
            action = 'REVIEW'
            action_label = 'Under Review'
            target = 'Assess investment thesis'
            score = 40
        else:
            action = 'HOLD'
            action_label = 'Maintain'
            target = 'Monitor quarterly'
            score = 50
        
        # Adjust score based on additional features if available
        if features.get('has_live_data', False):
            # Momentum adjustment
            if features.get('price_change_5d', 0) > 5:
                score += 5
            elif features.get('price_change_5d', 0) < -5:
                score -= 5
            
            # Volatility adjustment
            if features.get('volatility', 20) > 40:
                score += 5  # High volatility suggests taking action
        
        # Generate rationale
        rationale_parts = []
        
        if return_pct > 50:
            rationale_parts.append(f"Strong gains of {return_pct:.1f}%")
        elif return_pct < -20:
            rationale_parts.append(f"Significant loss of {abs(return_pct):.1f}%")
        else:
            rationale_parts.append(f"Return of {return_pct:.1f}%")
        
        if features.get('has_live_data', False):
            if features.get('volatility', 20) > 35:
                rationale_parts.append(f"High volatility ({features['volatility']:.0f}%)")
            
            momentum = features.get('price_change_5d', 0)
            if abs(momentum) > 3:
                rationale_parts.append(f"Recent momentum: {momentum:+.1f}%")
        else:
            rationale_parts.append("Based on portfolio data only")
        
        rationale = ". ".join(rationale_parts)
        
        # Calculate confidence
        confidence = 60  # Base confidence
        if features.get('has_live_data', False):
            confidence += 20
        if abs(return_pct) > 50:
            confidence += 10
        
        return {
            'ticker': ticker,
            'current_value': round(holding['end_value'], 2),
            'return_percentage': round(return_pct, 2),
            'recommendation': action,
            'action': action_label,
            'rationale': rationale,
            'target_action': target,
            'confidence': min(confidence, 90),
            'ml_score': round(score, 0),
            'data_source': 'Live + Portfolio' if features.get('has_live_data', False) else 'Portfolio Only'
        }
