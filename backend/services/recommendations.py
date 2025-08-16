import pandas as pd
from typing import Dict, List

class RecommendationEngine:
    def __init__(self):
        self.thresholds = {
            'strong_buy': -20,
            'buy': -10,
            'hold_low': 10,
            'hold_high': 30,
            'sell': 50,
            'strong_sell': 100
        }
    
    def generate_recommendations(self, holdings_df: pd.DataFrame) -> List[Dict]:
        """Generate buy/hold/sell recommendations for each holding"""
        recommendations = []
        
        for _, holding in holdings_df.iterrows():
            ticker = holding['ticker']
            
            # Handle both old and new data formats for backward compatibility
            if 'current_value' in holding:
                # New simplified workflow format
                current_value = holding.get('current_value', 0) or 0
                cost_basis = holding.get('cost_basis', 0) or 0
                return_pct = holding.get('return_percentage', 0) or 0
            else:
                # Legacy format
                current_value = holding.get('end_value', 0) or 0
                cost_basis = holding.get('start_value', 0) or 0
                # Calculate return
                if cost_basis > 0:
                    return_pct = ((current_value - cost_basis) / cost_basis) * 100
                else:
                    return_pct = 0 if current_value == 0 else 100
            
            # Generate recommendation
            rec = self._get_recommendation(
                ticker, return_pct, cost_basis, current_value, holding
            )
            
            recommendations.append({
                'ticker': ticker,
                'current_value': round(current_value, 2),
                'return_percentage': round(return_pct, 2),
                'recommendation': rec['recommendation'],
                'action': rec['action'],
                'rationale': rec['rationale'],
                'target_action': rec['target_action'],
                'confidence': rec['confidence']
            })
        
        return recommendations
    
    def _get_recommendation(self, ticker, return_pct, cost_basis, current_value, holding):
        """Generate specific recommendation for a holding"""
        
        # Handle closed positions
        if current_value == 0 and cost_basis > 0:
            return {
                'recommendation': 'CLOSED',
                'action': 'Position Closed',
                'rationale': 'Position has been exited',
                'target_action': 'No action needed',
                'confidence': 100
            }
        
        # Special rules for specific stocks
        special_rules = {
            'SMH': {'threshold': 100, 'action': 'Take Profits'},
            'QQQ': {'threshold': 60, 'action': 'Reduce Position'},
            'SPK': {'threshold': -30, 'action': 'Cut Losses'},
            'INTC': {'threshold': -20, 'action': 'Tax Loss Harvest'},
            'NVDA': {'action': 'Monitor AI Play'},
            'META': {'action': 'Monitor AI Play'},
            'MSFT': {'action': 'Core Holding'},
            'AAPL': {'action': 'Core Holding'}
        }
        
        if ticker in special_rules:
            rule = special_rules[ticker]
            
            # Check thresholds
            if 'threshold' in rule:
                if return_pct > 0 and return_pct > rule['threshold']:
                    return {
                        'recommendation': 'SELL',
                        'action': rule['action'],
                        'rationale': f'Exceptional gain of {return_pct:.1f}%. Lock in profits',
                        'target_action': f'Sell 50-70% of position',
                        'confidence': 90
                    }
                elif return_pct < 0 and return_pct < rule['threshold']:
                    return {
                        'recommendation': 'SELL',
                        'action': rule['action'],
                        'rationale': f'Significant loss of {abs(return_pct):.1f}%',
                        'target_action': 'Exit entire position',
                        'confidence': 85
                    }
            
            # Default actions for special stocks
            if ticker in ['NVDA', 'META']:
                return {
                    'recommendation': 'HOLD',
                    'action': 'Monitor Closely',
                    'rationale': 'AI growth story intact, watch valuation',
                    'target_action': 'Set 15% trailing stop',
                    'confidence': 75
                }
            elif ticker in ['MSFT', 'AAPL']:
                return {
                    'recommendation': 'HOLD',
                    'action': 'Core Holding',
                    'rationale': 'Quality company with strong fundamentals',
                    'target_action': 'Maintain position',
                    'confidence': 80
                }
        
        # General rules based on return percentage
        if return_pct > self.thresholds['strong_sell']:
            return {
                'recommendation': 'SELL',
                'action': 'Extreme Overvaluation',
                'rationale': f'Up {return_pct:.1f}%. Take substantial profits',
                'target_action': 'Sell 70-80% of position',
                'confidence': 95
            }
        elif return_pct > self.thresholds['sell']:
            return {
                'recommendation': 'SELL',
                'action': 'Take Profits',
                'rationale': f'Strong gain of {return_pct:.1f}%',
                'target_action': 'Sell 40-50% of position',
                'confidence': 80
            }
        elif return_pct > self.thresholds['hold_high']:
            return {
                'recommendation': 'HOLD',
                'action': 'Monitor Winner',
                'rationale': f'Good gain of {return_pct:.1f}%. Let winner run',
                'target_action': 'Set trailing stop at 15%',
                'confidence': 70
            }
        elif return_pct < self.thresholds['strong_buy']:
            return {
                'recommendation': 'REVIEW',
                'action': 'Assess Position',
                'rationale': f'Down {abs(return_pct):.1f}%. Review investment thesis',
                'target_action': 'Consider exit or averaging down',
                'confidence': 60
            }
        elif return_pct < self.thresholds['buy']:
            return {
                'recommendation': 'HOLD',
                'action': 'Monitor',
                'rationale': f'Moderate loss of {abs(return_pct):.1f}%',
                'target_action': 'Set stop loss at -15%',
                'confidence': 65
            }
        else:
            return {
                'recommendation': 'HOLD',
                'action': 'Maintain',
                'rationale': 'Position within normal range',
                'target_action': 'Monitor quarterly',
                'confidence': 70
            }