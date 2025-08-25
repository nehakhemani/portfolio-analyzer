#!/usr/bin/env python3
"""
Statistical Analysis Service for Portfolio
Advanced portfolio analytics, risk metrics, and performance analysis
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import sqlite3
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

class StatisticalAnalysisService:
    """Comprehensive portfolio statistical analysis"""
    
    def __init__(self, db_path='data/portfolio.db'):
        self.db_path = db_path
    
    def analyze_portfolio(self, holdings_data: List[Dict]) -> Dict:
        """
        STEP 6: Complete statistical analysis of portfolio
        Only analyze holdings that have valid price and return data
        """
        try:
            print("=== STATISTICAL ANALYSIS STARTED ===")
            
            # Filter holdings that have complete data
            valid_holdings = self._filter_valid_holdings(holdings_data)
            
            if len(valid_holdings) < 2:
                return {
                    'error': f'Insufficient data for analysis. Need at least 2 holdings with prices, found {len(valid_holdings)}',
                    'holdings_analyzed': len(valid_holdings),
                    'total_holdings': len(holdings_data),
                    'recommendation': 'Add manual prices for more holdings to enable statistical analysis'
                }
            
            print(f"Analyzing {len(valid_holdings)} holdings with complete data...")
            
            # Core statistical analysis
            analysis = {
                'analysis_timestamp': datetime.now().isoformat(),
                'holdings_analyzed': len(valid_holdings),
                'total_holdings': len(holdings_data),
                'analysis_coverage': f"{len(valid_holdings)}/{len(holdings_data)} ({len(valid_holdings)/len(holdings_data)*100:.1f}%)"
            }
            
            # 1. Portfolio Overview Statistics
            analysis['portfolio_overview'] = self._calculate_portfolio_overview(valid_holdings)
            
            # 2. Return Distribution Analysis  
            analysis['return_distribution'] = self._analyze_return_distribution(valid_holdings)
            
            # 3. Risk Analysis
            analysis['risk_analysis'] = self._calculate_risk_metrics(valid_holdings)
            
            # 4. Concentration Analysis
            analysis['concentration_analysis'] = self._analyze_concentration(valid_holdings)
            
            # 5. Performance Metrics
            analysis['performance_metrics'] = self._calculate_performance_metrics(valid_holdings)
            
            # 6. Correlation Analysis (if enough holdings)
            if len(valid_holdings) >= 3:
                analysis['correlation_analysis'] = self._analyze_correlations(valid_holdings)
            
            # 7. Sector/Asset Allocation (if data available)
            analysis['allocation_analysis'] = self._analyze_allocation(valid_holdings)
            
            # 8. Risk-Adjusted Returns
            analysis['risk_adjusted_returns'] = self._calculate_risk_adjusted_returns(valid_holdings)
            
            # 9. Portfolio Recommendations
            analysis['recommendations'] = self._generate_statistical_recommendations(analysis, valid_holdings)
            
            print("=== STATISTICAL ANALYSIS COMPLETED ===")
            return analysis
            
        except Exception as e:
            print(f"Statistical analysis error: {e}")
            return {
                'error': f'Statistical analysis failed: {str(e)}',
                'holdings_analyzed': 0
            }
    
    def _filter_valid_holdings(self, holdings_data: List[Dict]) -> List[Dict]:
        """Filter holdings that have complete data for analysis"""
        valid_holdings = []
        
        for holding in holdings_data:
            # Must have current price, return data, and valid cost basis
            if (holding.get('current_price') is not None and 
                holding.get('return_percentage') is not None and
                holding.get('current_value') is not None and
                holding.get('cost_basis', 0) > 0):
                valid_holdings.append(holding)
        
        return valid_holdings
    
    def _calculate_portfolio_overview(self, holdings: List[Dict]) -> Dict:
        """Calculate basic portfolio statistics"""
        
        total_value = sum(h['current_value'] for h in holdings)
        total_cost = sum(h['cost_basis'] for h in holdings)
        
        returns = [h['return_percentage'] for h in holdings]
        weights = [h['current_value'] / total_value for h in holdings]
        
        # Weighted portfolio return
        portfolio_return = sum(ret * weight for ret, weight in zip(returns, weights))
        
        return {
            'total_current_value': round(total_value, 2),
            'total_cost_basis': round(total_cost, 2),
            'total_return_amount': round(total_value - total_cost, 2),
            'portfolio_return_percentage': round(portfolio_return, 2),
            'number_of_positions': len(holdings),
            'average_position_size': round(total_value / len(holdings), 2),
            'largest_position': round(max(h['current_value'] for h in holdings), 2),
            'smallest_position': round(min(h['current_value'] for h in holdings), 2)
        }
    
    def _analyze_return_distribution(self, holdings: List[Dict]) -> Dict:
        """Analyze the distribution of returns across holdings"""
        
        returns = [h['return_percentage'] for h in holdings]
        
        return {
            'mean_return': round(np.mean(returns), 2),
            'median_return': round(np.median(returns), 2),
            'return_std': round(np.std(returns), 2),
            'min_return': round(min(returns), 2),
            'max_return': round(max(returns), 2),
            'return_range': round(max(returns) - min(returns), 2),
            'positive_returns_count': sum(1 for r in returns if r > 0),
            'negative_returns_count': sum(1 for r in returns if r < 0),
            'win_rate': round(sum(1 for r in returns if r > 0) / len(returns) * 100, 1),
            'return_quartiles': {
                'q1': round(np.percentile(returns, 25), 2),
                'q2': round(np.percentile(returns, 50), 2),
                'q3': round(np.percentile(returns, 75), 2)
            }
        }
    
    def _calculate_risk_metrics(self, holdings: List[Dict]) -> Dict:
        """Calculate portfolio risk metrics"""
        
        returns = [h['return_percentage'] for h in holdings]
        values = [h['current_value'] for h in holdings]
        total_value = sum(values)
        weights = [v / total_value for v in values]
        
        # Portfolio volatility (weighted standard deviation)
        portfolio_volatility = np.sqrt(sum(w * w * (r - np.mean(returns))**2 for w, r in zip(weights, returns)))
        
        # Value at Risk (VaR) - 5th percentile
        var_5 = np.percentile(returns, 5)
        
        # Maximum drawdown simulation
        max_loss = min(returns)
        
        return {
            'portfolio_volatility': round(portfolio_volatility, 2),
            'value_at_risk_5pct': round(var_5, 2),
            'maximum_single_loss': round(max_loss, 2),
            'risk_level': self._classify_risk_level(portfolio_volatility),
            'volatility_interpretation': self._interpret_volatility(portfolio_volatility),
            'diversification_score': self._calculate_diversification_score(holdings)
        }
    
    def _analyze_concentration(self, holdings: List[Dict]) -> Dict:
        """Analyze portfolio concentration"""
        
        values = [h['current_value'] for h in holdings]
        total_value = sum(values)
        weights = [v / total_value * 100 for v in values]
        weights.sort(reverse=True)
        
        # Herfindahl-Hirschman Index (concentration measure)
        hhi = sum(w**2 for w in weights) / 100
        
        # Top positions concentration
        top_3_concentration = sum(weights[:3]) if len(weights) >= 3 else sum(weights)
        top_5_concentration = sum(weights[:5]) if len(weights) >= 5 else sum(weights)
        
        return {
            'herfindahl_index': round(hhi, 2),
            'concentration_level': self._classify_concentration(hhi),
            'top_position_weight': round(weights[0], 1),
            'top_3_concentration': round(top_3_concentration, 1),
            'top_5_concentration': round(top_5_concentration, 1),
            'position_weights': [round(w, 1) for w in weights[:10]],  # Top 10
            'concentration_risk': self._assess_concentration_risk(hhi, weights[0])
        }
    
    def _calculate_performance_metrics(self, holdings: List[Dict]) -> Dict:
        """Calculate performance metrics"""
        
        returns = [h['return_percentage'] for h in holdings]
        values = [h['current_value'] for h in holdings]
        
        # Calculate Sharpe ratio approximation (assuming risk-free rate = 0)
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        sharpe_ratio = mean_return / std_return if std_return > 0 else 0
        
        # Calculate Sortino ratio (downside deviation)
        negative_returns = [r for r in returns if r < 0]
        downside_std = np.std(negative_returns) if negative_returns else 0
        sortino_ratio = mean_return / downside_std if downside_std > 0 else float('inf')
        
        return {
            'sharpe_ratio': round(sharpe_ratio, 3),
            'sortino_ratio': round(min(sortino_ratio, 999), 3),  # Cap at 999 for display
            'calmar_ratio': self._calculate_calmar_ratio(returns),
            'information_ratio': self._calculate_information_ratio(returns),
            'treynor_ratio': 'N/A',  # Would need beta calculation
            'performance_ranking': self._rank_performance(mean_return, std_return)
        }
    
    def _analyze_correlations(self, holdings: List[Dict]) -> Dict:
        """Analyze correlations between holdings (simplified)"""
        
        # This is a simplified correlation analysis
        # In a real implementation, you'd need historical price data
        
        returns = [h['return_percentage'] for h in holdings]
        tickers = [h['ticker'] for h in holdings]
        
        # Estimate correlation based on return similarity (proxy)
        return {
            'average_correlation': 'N/A (requires historical data)',
            'diversification_benefit': self._estimate_diversification_benefit(holdings),
            'correlation_risk': 'Medium',
            'recommendation': 'Consider adding assets from different sectors/geographies'
        }
    
    def _analyze_allocation(self, holdings: List[Dict]) -> Dict:
        """Analyze asset allocation"""
        
        values = [h['current_value'] for h in holdings]
        total_value = sum(values)
        
        # Classify by ticker characteristics (basic classification)
        classifications = self._classify_assets(holdings)
        
        allocation = {}
        for category, holdings_in_category in classifications.items():
            category_value = sum(h['current_value'] for h in holdings_in_category)
            allocation[category] = {
                'value': round(category_value, 2),
                'percentage': round(category_value / total_value * 100, 1),
                'count': len(holdings_in_category)
            }
        
        return {
            'asset_allocation': allocation,
            'diversification_score': len(classifications),
            'allocation_balance': self._assess_allocation_balance(allocation)
        }
    
    def _calculate_risk_adjusted_returns(self, holdings: List[Dict]) -> Dict:
        """Calculate risk-adjusted return metrics"""
        
        returns = [h['return_percentage'] for h in holdings]
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        
        # Risk-adjusted return = return per unit of risk
        risk_adjusted_return = mean_return / std_return if std_return > 0 else 0
        
        return {
            'risk_adjusted_return': round(risk_adjusted_return, 3),
            'return_to_risk_ratio': round(risk_adjusted_return, 3),
            'efficiency_score': self._calculate_efficiency_score(mean_return, std_return),
            'risk_premium': round(mean_return, 2)  # Assuming risk-free rate = 0
        }
    
    def _generate_statistical_recommendations(self, analysis: Dict, holdings: List[Dict]) -> List[Dict]:
        """Generate individual holding recommendations based on statistical analysis"""
        
        recommendations = []
        
        # Calculate percentiles for relative performance ranking
        returns = [h['return_percentage'] for h in holdings]
        values = [h['current_value'] for h in holdings]
        total_value = sum(values)
        
        # Calculate performance percentiles
        return_percentiles = {
            'q1': np.percentile(returns, 25),
            'median': np.percentile(returns, 50), 
            'q3': np.percentile(returns, 75)
        }
        
        # Generate recommendations for each holding
        for holding in holdings:
            ticker = holding['ticker']
            return_pct = holding['return_percentage']
            current_value = holding['current_value']
            weight = current_value / total_value * 100
            
            # Determine recommendation based on multiple factors
            recommendation = self._determine_holding_recommendation(
                return_pct, weight, return_percentiles, analysis
            )
            
            # Generate rationale
            rationale = self._generate_holding_rationale(
                holding, return_pct, weight, return_percentiles, analysis
            )
            
            # Calculate confidence based on data quality and return magnitude
            confidence = self._calculate_recommendation_confidence(
                return_pct, weight, holding
            )
            
            recommendations.append({
                'ticker': ticker,
                'current_value': current_value,
                'return_percentage': return_pct,
                'portfolio_weight': weight,
                'recommendation': recommendation,
                'action': self._get_action_description(recommendation),
                'rationale': rationale,
                'confidence': confidence,
                'ml_score': round(abs(return_pct) / 10 + weight / 5, 1),  # Simple scoring
                'technical_indicators': {
                    'return_rank': self._get_performance_rank(return_pct, return_percentiles),
                    'weight_category': self._get_weight_category(weight),
                    'risk_level': self._assess_holding_risk(return_pct, weight)
                }
            })
        
        # Sort by confidence and return for better display
        recommendations.sort(key=lambda x: (-x['confidence'], -x['return_percentage']))
        
        return recommendations
    
    def _determine_holding_recommendation(self, return_pct: float, weight: float, 
                                        return_percentiles: Dict, analysis: Dict) -> str:
        """Determine BUY/HOLD/SELL recommendation for a holding"""
        
        # Strong performance indicators
        if return_pct > return_percentiles['q3'] and return_pct > 15:
            if weight < 15:  # Not over-concentrated
                return 'BUY'
            else:
                return 'HOLD'  # Good performer but already large position
        
        # Poor performance indicators  
        elif return_pct < return_percentiles['q1'] and return_pct < -20:
            return 'SELL'
        
        # Over-concentration risk
        elif weight > 25:
            if return_pct < 0:
                return 'SELL'  # Large losing position
            else:
                return 'HOLD'  # Large winning position - hold but don't add
        
        # Moderate performers
        elif return_percentiles['q1'] <= return_pct <= return_percentiles['q3']:
            if weight < 5:
                return 'BUY'  # Small position in decent performer
            else:
                return 'HOLD'
        
        # Default to HOLD for edge cases
        else:
            return 'HOLD'
    
    def _generate_holding_rationale(self, holding: Dict, return_pct: float, weight: float,
                                  return_percentiles: Dict, analysis: Dict) -> str:
        """Generate detailed rationale for the recommendation"""
        
        rationale_parts = []
        
        # Performance analysis
        if return_pct > return_percentiles['q3']:
            rationale_parts.append(f"Top quartile performer (+{return_pct:.1f}%)")
        elif return_pct < return_percentiles['q1']:
            rationale_parts.append(f"Bottom quartile performer ({return_pct:.1f}%)")
        else:
            rationale_parts.append(f"Moderate performer ({return_pct:.1f}%)")
        
        # Position size analysis
        if weight > 20:
            rationale_parts.append(f"Large position ({weight:.1f}% of portfolio)")
        elif weight < 5:
            rationale_parts.append(f"Small position ({weight:.1f}% of portfolio)")
        else:
            rationale_parts.append(f"Balanced position ({weight:.1f}% of portfolio)")
        
        # Add risk context
        if abs(return_pct) > 30:
            rationale_parts.append("High volatility asset")
        elif abs(return_pct) < 5:
            rationale_parts.append("Stable performer")
        
        return ". ".join(rationale_parts) + "."
    
    def _calculate_recommendation_confidence(self, return_pct: float, weight: float, 
                                          holding: Dict) -> int:
        """Calculate confidence score (0-100) for the recommendation"""
        
        confidence = 70  # Base confidence
        
        # Higher confidence for clear winners/losers
        if abs(return_pct) > 20:
            confidence += 15
        elif abs(return_pct) > 10:
            confidence += 10
        
        # Higher confidence for appropriately sized positions
        if 5 <= weight <= 15:
            confidence += 10
        elif weight > 25 or weight < 2:
            confidence += 15  # Clear over/under weight
        
        # Adjust for extreme cases
        if return_pct < -30:
            confidence += 10  # Clear sell signal
        elif return_pct > 50:
            confidence += 10  # Clear winner
        
        return min(95, confidence)  # Cap at 95%
    
    def _get_action_description(self, recommendation: str) -> str:
        """Get action description for recommendation"""
        actions = {
            'BUY': 'Consider increasing position size',
            'SELL': 'Consider reducing or closing position', 
            'HOLD': 'Maintain current position size'
        }
        return actions.get(recommendation, 'Monitor closely')
    
    def _get_performance_rank(self, return_pct: float, percentiles: Dict) -> str:
        """Get performance ranking description"""
        if return_pct > percentiles['q3']:
            return 'Top Quartile'
        elif return_pct > percentiles['median']:
            return 'Above Average'
        elif return_pct > percentiles['q1']:
            return 'Below Average'
        else:
            return 'Bottom Quartile'
    
    def _get_weight_category(self, weight: float) -> str:
        """Categorize position weight"""
        if weight > 20:
            return 'Overweight'
        elif weight < 3:
            return 'Underweight'
        else:
            return 'Balanced'
    
    def _assess_holding_risk(self, return_pct: float, weight: float) -> str:
        """Assess individual holding risk level"""
        if abs(return_pct) > 30 and weight > 15:
            return 'High'
        elif abs(return_pct) > 20 or weight > 25:
            return 'Medium'
        else:
            return 'Low'
    
    # Helper methods for classifications and calculations
    
    def _classify_risk_level(self, volatility: float) -> str:
        if volatility < 10:
            return 'Low'
        elif volatility < 20:
            return 'Medium'
        else:
            return 'High'
    
    def _interpret_volatility(self, volatility: float) -> str:
        if volatility < 10:
            return 'Conservative portfolio with stable returns'
        elif volatility < 20:
            return 'Moderate risk portfolio with balanced approach'
        else:
            return 'Aggressive portfolio with high return potential and risk'
    
    def _calculate_diversification_score(self, holdings: List[Dict]) -> float:
        # Simple diversification score based on number of holdings and concentration
        num_holdings = len(holdings)
        if num_holdings >= 10:
            return min(8.5, 5 + (num_holdings - 10) * 0.2)
        else:
            return num_holdings * 0.5
    
    def _classify_concentration(self, hhi: float) -> str:
        if hhi < 10:
            return 'Well Diversified'
        elif hhi < 25:
            return 'Moderately Concentrated'
        else:
            return 'Highly Concentrated'
    
    def _assess_concentration_risk(self, hhi: float, top_weight: float) -> str:
        if hhi > 25 or top_weight > 30:
            return 'High'
        elif hhi > 15 or top_weight > 20:
            return 'Medium'
        else:
            return 'Low'
    
    def _calculate_calmar_ratio(self, returns: List[float]) -> float:
        mean_return = np.mean(returns)
        max_drawdown = abs(min(returns)) if min(returns) < 0 else 1
        return round(mean_return / max_drawdown, 3)
    
    def _calculate_information_ratio(self, returns: List[float]) -> float:
        # Simplified information ratio
        mean_return = np.mean(returns)
        tracking_error = np.std(returns)
        return round(mean_return / tracking_error if tracking_error > 0 else 0, 3)
    
    def _rank_performance(self, mean_return: float, std_return: float) -> str:
        risk_adjusted = mean_return / std_return if std_return > 0 else 0
        if risk_adjusted > 1.0:
            return 'Excellent'
        elif risk_adjusted > 0.5:
            return 'Good'
        elif risk_adjusted > 0:
            return 'Fair'
        else:
            return 'Poor'
    
    def _estimate_diversification_benefit(self, holdings: List[Dict]) -> str:
        # Simple estimation based on number of holdings
        num_holdings = len(holdings)
        if num_holdings >= 10:
            return 'Good diversification benefit'
        elif num_holdings >= 5:
            return 'Moderate diversification benefit'
        else:
            return 'Limited diversification benefit'
    
    def _classify_assets(self, holdings: List[Dict]) -> Dict:
        """Basic asset classification based on ticker patterns"""
        classifications = {'Stocks': [], 'ETFs': [], 'International': [], 'Other': []}
        
        for holding in holdings:
            ticker = holding['ticker'].upper()
            
            # ETF patterns
            if any(etf in ticker for etf in ['SPY', 'QQQ', 'IWM', 'VTI', 'IVV', 'VOO', 'IXJ', 'IXUS', 'SMH']):
                classifications['ETFs'].append(holding)
            # International patterns (exchanges or suffixes)
            elif any(suffix in ticker for suffix in ['.AX', '.NZ', '.L', '.TO']) or holding.get('exchange') in ['NZX', 'ASX', 'LSE', 'TSX']:
                classifications['International'].append(holding)
            # Regular stocks
            elif len(ticker) <= 5 and ticker.isalpha():
                classifications['Stocks'].append(holding)
            else:
                classifications['Other'].append(holding)
        
        # Remove empty categories
        return {k: v for k, v in classifications.items() if v}
    
    def _assess_allocation_balance(self, allocation: Dict) -> str:
        percentages = [cat['percentage'] for cat in allocation.values()]
        max_pct = max(percentages)
        
        if max_pct > 80:
            return 'Unbalanced - heavily concentrated in one category'
        elif max_pct > 60:
            return 'Moderately concentrated'
        else:
            return 'Well balanced across categories'
    
    def _calculate_efficiency_score(self, mean_return: float, std_return: float) -> float:
        # Portfolio efficiency score (0-10 scale)
        if std_return == 0:
            return 10 if mean_return > 0 else 0
        
        sharpe = mean_return / std_return
        # Convert Sharpe ratio to 0-10 scale
        score = min(10, max(0, 5 + sharpe * 2))
        return round(score, 1)