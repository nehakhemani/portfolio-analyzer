"""
Currency Converter Service
Handles currency conversion with real-time exchange rates
"""

import requests
import time
import logging
from typing import Dict, Optional
import json

class CurrencyConverter:
    """Real-time currency converter with caching"""
    
    def __init__(self):
        self.cache = {}
        self.cache_duration = 3600  # 1 hour cache
        self.base_currency = 'USD'
        
        # Common exchange rates (fallback if API fails)
        self.fallback_rates = {
            'USD': 1.0,
            'EUR': 0.85,
            'GBP': 0.73,
            'JPY': 110.0,
            'CAD': 1.25,
            'AUD': 1.35,
            'CHF': 0.92,
            'CNY': 6.45,
            'INR': 74.5,
            'KRW': 1180.0,
            'BRL': 5.2,
            'RUB': 74.0,
            'SGD': 1.35,
            'HKD': 7.8,
            'SEK': 8.5,
            'NOK': 8.6,
            'DKK': 6.3,
            'PLN': 3.9,
            'CZK': 21.5,
            'HUF': 295.0
        }
    
    def get_exchange_rates(self) -> Dict[str, float]:
        """Get current exchange rates (USD as base)"""
        cache_key = "exchange_rates"
        
        # Check cache
        if cache_key in self.cache:
            cache_time, rates = self.cache[cache_key]
            if time.time() - cache_time < self.cache_duration:
                return rates
        
        # Try to get real-time rates
        rates = self._fetch_real_time_rates()
        
        # If failed, use fallback rates
        if not rates:
            print("Using fallback exchange rates")
            rates = self.fallback_rates.copy()
        
        # Cache the rates
        self.cache[cache_key] = (time.time(), rates)
        return rates
    
    def _fetch_real_time_rates(self) -> Optional[Dict[str, float]]:
        """Fetch real-time exchange rates from free API"""
        try:
            # Using exchangerate-api.com (free tier: 1500 requests/month)
            url = "https://api.exchangerate-api.com/v4/latest/USD"
            
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                rates = data.get('rates', {})
                
                # Add USD as base
                rates['USD'] = 1.0
                
                print(f"Fetched real-time rates for {len(rates)} currencies")
                return rates
            else:
                print(f"Exchange rate API returned status: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching exchange rates: {e}")
            return None
        except Exception as e:
            print(f"Error parsing exchange rates: {e}")
            return None
    
    def convert(self, amount: float, from_currency: str, to_currency: str = 'USD') -> Dict:
        """Convert amount from one currency to another"""
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()
        
        # If same currency, no conversion needed
        if from_currency == to_currency:
            return {
                'original_amount': amount,
                'converted_amount': amount,
                'from_currency': from_currency,
                'to_currency': to_currency,
                'exchange_rate': 1.0,
                'conversion_time': time.time()
            }
        
        try:
            rates = self.get_exchange_rates()
            
            # Check if currencies are supported
            if from_currency not in rates:
                raise ValueError(f"Currency {from_currency} not supported")
            if to_currency not in rates:
                raise ValueError(f"Currency {to_currency} not supported")
            
            # Convert via USD (base currency)
            if from_currency == 'USD':
                usd_amount = amount
            else:
                usd_amount = amount / rates[from_currency]
            
            if to_currency == 'USD':
                converted_amount = usd_amount
                exchange_rate = 1.0 / rates[from_currency] if from_currency != 'USD' else 1.0
            else:
                converted_amount = usd_amount * rates[to_currency]
                exchange_rate = rates[to_currency] / rates[from_currency]
            
            return {
                'original_amount': amount,
                'converted_amount': round(converted_amount, 2),
                'from_currency': from_currency,
                'to_currency': to_currency,
                'exchange_rate': round(exchange_rate, 4),
                'conversion_time': time.time()
            }
            
        except Exception as e:
            logging.error(f"Currency conversion error: {e}")
            # Return original amount if conversion fails
            return {
                'original_amount': amount,
                'converted_amount': amount,
                'from_currency': from_currency,
                'to_currency': to_currency,
                'exchange_rate': 1.0,
                'conversion_time': time.time(),
                'error': str(e)
            }
    
    def convert_to_usd(self, amount: float, from_currency: str) -> float:
        """Quick conversion to USD (returns just the amount)"""
        result = self.convert(amount, from_currency, 'USD')
        return result['converted_amount']
    
    def get_supported_currencies(self) -> Dict[str, str]:
        """Get list of supported currencies with names"""
        currency_names = {
            'USD': 'US Dollar',
            'EUR': 'Euro',
            'GBP': 'British Pound',
            'JPY': 'Japanese Yen',
            'CAD': 'Canadian Dollar',
            'AUD': 'Australian Dollar',
            'CHF': 'Swiss Franc',
            'CNY': 'Chinese Yuan',
            'INR': 'Indian Rupee',
            'KRW': 'South Korean Won',
            'BRL': 'Brazilian Real',
            'RUB': 'Russian Ruble',
            'SGD': 'Singapore Dollar',
            'HKD': 'Hong Kong Dollar',
            'SEK': 'Swedish Krona',
            'NOK': 'Norwegian Krone',
            'DKK': 'Danish Krone',
            'PLN': 'Polish Zloty',
            'CZK': 'Czech Koruna',
            'HUF': 'Hungarian Forint'
        }
        
        rates = self.get_exchange_rates()
        supported = {}
        
        for code in rates.keys():
            if code in currency_names:
                supported[code] = currency_names[code]
            else:
                supported[code] = code  # Use code as name if name not available
        
        return supported
    
    def format_currency(self, amount: float, currency: str) -> str:
        """Format currency amount with proper symbol"""
        currency_symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥',
            'CAD': 'C$',
            'AUD': 'A$',
            'CHF': 'CHF',
            'CNY': '¥',
            'INR': '₹',
            'KRW': '₩',
            'BRL': 'R$',
            'RUB': '₽',
            'SGD': 'S$',
            'HKD': 'HK$',
            'SEK': 'kr',
            'NOK': 'kr',
            'DKK': 'kr',
            'PLN': 'zł',
            'CZK': 'Kč',
            'HUF': 'Ft'
        }
        
        symbol = currency_symbols.get(currency.upper(), currency.upper())
        
        # Format based on currency (some currencies don't use decimals)
        if currency.upper() in ['JPY', 'KRW', 'HUF']:
            return f"{symbol}{amount:,.0f}"
        else:
            return f"{symbol}{amount:,.2f}"
    
    def get_conversion_summary(self, amounts: Dict[str, float]) -> Dict:
        """Convert multiple currency amounts to USD and provide summary"""
        conversions = {}
        total_usd = 0
        
        for currency, amount in amounts.items():
            if amount > 0:
                conversion = self.convert(amount, currency, 'USD')
                conversions[currency] = conversion
                total_usd += conversion['converted_amount']
        
        return {
            'conversions': conversions,
            'total_usd': round(total_usd, 2),
            'base_currency': 'USD',
            'conversion_time': time.time()
        }