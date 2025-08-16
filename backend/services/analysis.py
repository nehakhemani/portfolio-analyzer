import pandas as pd
import numpy as np
from typing import Dict, Any

class PortfolioAnalyzer:
    def analyze_portfolio(self, holdings_df: pd.DataFrame) -> Dict[str, Any]:
        """Perform comprehensive portfolio analysis"""
        
        # Handle both old and new data formats for backward compatibility
        if 'current_value' in holdings_df.columns:
            # New simplified workflow format
            value_col = 'current_value'
            cost_col = 'cost_basis'
        else:
            # Legacy format
            value_col = 'end_value'
            cost_col = 'start_value'
        
        # Basic metrics
        total_value = holdings_df[value_col].sum()
        total_start_value = holdings_df[cost_col].sum()
        total_return = total_value - total_start_value
        return_pct = (total_return / total_start_value * 100) if total_start_value > 0 else 0
        
        # Exchange allocation (using exchange as proxy for geographic/market allocation)
        exchange_allocation = holdings_df.groupby('exchange')[value_col].sum().to_dict()
        
        # Risk metrics
        returns = []
        for _, holding in holdings_df.iterrows():
            cost_basis = holding.get(cost_col, 0) or 0
            current_value = holding.get(value_col, 0) or 0
            if cost_basis > 0:
                ret = ((current_value - cost_basis) / cost_basis)
                returns.append(ret)
        
        returns_array = np.array(returns)
        volatility = np.std(returns_array) * 100 if len(returns) > 0 else 0
        
        # Concentration risk
        if total_value > 0:
            holdings_pct = (holdings_df[value_col] / total_value * 100)
            max_concentration = holdings_pct.max() if len(holdings_pct) > 0 else 0
        else:
            max_concentration = 0
        
        # Winners and losers - create a copy to avoid modifying original DataFrame
        holdings_copy = holdings_df.copy()
        holdings_copy['return_pct'] = holdings_copy.apply(
            lambda x: ((x.get(value_col, 0) - x.get(cost_col, 0)) / x.get(cost_col, 1) * 100) 
            if x.get(cost_col, 0) > 0 else 0, axis=1
        )
        
        top_performers = holdings_copy.nlargest(5, 'return_pct')[['ticker', 'return_pct']].to_dict('records')
        worst_performers = holdings_copy.nsmallest(5, 'return_pct')[['ticker', 'return_pct']].to_dict('records')
        
        return {
            'metrics': {
                'total_value': round(total_value, 2),
                'total_return': round(total_return, 2),
                'return_percentage': round(return_pct, 2),
                'volatility': round(volatility, 2),
                'max_concentration': round(max_concentration, 2)
            },
            'exchange_allocation': exchange_allocation,
            'top_performers': top_performers,
            'worst_performers': worst_performers,
            'risk_assessment': self._assess_risk(volatility, max_concentration, return_pct)
        }
    
    def _assess_risk(self, volatility: float, max_concentration: float, return_pct: float) -> Dict[str, Any]:
        """Assess portfolio risk"""
        risk_score = 0
        risk_factors = []
        
        # Volatility risk
        if volatility > 30:
            risk_score += 3
            risk_factors.append("High volatility")
        elif volatility > 20:
            risk_score += 2
            risk_factors.append("Moderate volatility")
        
        # Concentration risk
        if max_concentration > 20:
            risk_score += 3
            risk_factors.append("High concentration in single holding")
        elif max_concentration > 15:
            risk_score += 2
            risk_factors.append("Moderate concentration risk")
        
        # Performance risk
        if return_pct < -10:
            risk_score += 2
            risk_factors.append("Significant losses")
        
        risk_level = "Low"
        if risk_score >= 6:
            risk_level = "High"
        elif risk_score >= 4:
            risk_level = "Medium"
        
        return {
            'risk_level': risk_level,
            'risk_score': risk_score,
            'risk_factors': risk_factors
        }