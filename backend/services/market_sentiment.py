"""
Market Sentiment Analysis Service
Provides real-time sentiment data from multiple sources
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
import logging
from typing import Dict, List, Optional
import json
import re
import os
from textblob import TextBlob
import yfinance as yf

# Reddit API imports
try:
    import praw
    REDDIT_AVAILABLE = True
except ImportError:
    REDDIT_AVAILABLE = False
    praw = None

class MarketSentimentAnalyzer:
    """Analyze market sentiment from multiple sources"""
    
    def __init__(self):
        self.request_delay = 0.5
        self.cache = {}
        self.cache_duration = 300  # 5 minutes cache
        
        # Initialize Reddit API if available and configured
        self.reddit = None
        self.reddit_enabled = False
        
        if REDDIT_AVAILABLE:
            self._setup_reddit_api()
        
    def get_comprehensive_sentiment(self, ticker: str) -> Dict:
        """Get comprehensive sentiment analysis for a stock"""
        cache_key = f"sentiment_{ticker}"
        
        # Check cache
        if cache_key in self.cache:
            cache_time, data = self.cache[cache_key]
            if time.time() - cache_time < self.cache_duration:
                return data
        
        sentiment_data = {
            'ticker': ticker,
            'timestamp': datetime.now().isoformat(),
            'news_sentiment': self.get_news_sentiment(ticker),
            'social_sentiment': self.get_social_sentiment(ticker),
            'market_indicators': self.get_market_indicators(),
            'analyst_sentiment': self.get_analyst_sentiment(ticker),
            'composite_score': 0,
            'sentiment_strength': 'neutral'
        }
        
        # Calculate composite sentiment score
        sentiment_data['composite_score'] = self.calculate_composite_sentiment(sentiment_data)
        sentiment_data['sentiment_strength'] = self.get_sentiment_strength(sentiment_data['composite_score'])
        
        # Cache the result
        self.cache[cache_key] = (time.time(), sentiment_data)
        
        return sentiment_data
    
    def _setup_reddit_api(self):
        """Setup Reddit API connection"""
        try:
            # Try to get credentials from environment variables
            reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
            reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
            reddit_user_agent = os.getenv('REDDIT_USER_AGENT', 'portfolio_analyzer_1.0')
            
            if reddit_client_id and reddit_client_secret:
                self.reddit = praw.Reddit(
                    client_id=reddit_client_id,
                    client_secret=reddit_client_secret,
                    user_agent=reddit_user_agent
                )
                self.reddit_enabled = True
                print("Reddit API initialized successfully")
            else:
                print("Reddit API credentials not found in environment variables")
                print("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to enable real social sentiment")
                
        except Exception as e:
            print(f"Error initializing Reddit API: {e}")
            self.reddit_enabled = False
    
    def get_news_sentiment(self, ticker: str) -> Dict:
        """Analyze news sentiment for a stock with enhanced time-weighting"""
        try:
            # Get recent news from Yahoo Finance
            stock = yf.Ticker(ticker)
            news = stock.news
            
            if not news:
                return {
                    'score': 0,
                    'articles_count': 0,
                    'positive_count': 0,
                    'negative_count': 0,
                    'recent_headlines': [],
                    'weighted_score': 0,
                    'sentiment_velocity': 0
                }
            
            # Analyze sentiment of headlines and summaries with time weighting
            sentiments = []
            weighted_sentiments = []
            headlines = []
            current_time = time.time()
            
            for article in news[:15]:  # Analyze more articles for better accuracy
                title = article.get('title', '')
                summary = article.get('summary', '')
                published_time = article.get('providerPublishTime', current_time)
                
                # Combine title and summary for analysis
                text = f"{title}. {summary}"
                
                if text.strip():
                    blob = TextBlob(text)
                    sentiment_score = blob.sentiment.polarity
                    
                    # Calculate time decay weight (exponential decay)
                    hours_old = (current_time - published_time) / 3600
                    time_weight = np.exp(-0.05 * hours_old)  # Decay over time
                    
                    # Apply source credibility weight (simple heuristic)
                    credibility_weight = self._get_source_credibility_weight(article)
                    
                    # Combined weight
                    total_weight = time_weight * credibility_weight
                    weighted_sentiment = sentiment_score * total_weight
                    
                    sentiments.append(sentiment_score)
                    weighted_sentiments.append(weighted_sentiment)
                    headlines.append({
                        'title': title,
                        'sentiment': sentiment_score,
                        'published': published_time,
                        'weight': total_weight,
                        'hours_old': hours_old
                    })
            
            if sentiments:
                avg_sentiment = np.mean(sentiments)
                weighted_avg_sentiment = np.sum(weighted_sentiments) / np.sum([h['weight'] for h in headlines])
                positive_count = sum(1 for s in sentiments if s > 0.1)
                negative_count = sum(1 for s in sentiments if s < -0.1)
                
                # Calculate sentiment velocity (rate of change)
                sentiment_velocity = self._calculate_sentiment_velocity(headlines)
            else:
                avg_sentiment = 0
                weighted_avg_sentiment = 0
                positive_count = 0
                negative_count = 0
                sentiment_velocity = 0
            
            return {
                'score': avg_sentiment,
                'weighted_score': weighted_avg_sentiment,
                'articles_count': len(sentiments),
                'positive_count': positive_count,
                'negative_count': negative_count,
                'recent_headlines': sorted(headlines, key=lambda x: x['published'], reverse=True)[:5],
                'sentiment_velocity': sentiment_velocity
            }
            
        except Exception as e:
            logging.error(f"Error getting news sentiment for {ticker}: {e}")
            return {
                'score': 0,
                'articles_count': 0,
                'positive_count': 0,
                'negative_count': 0,
                'recent_headlines': []
            }
    
    def get_social_sentiment(self, ticker: str) -> Dict:
        """Analyze social media sentiment from Reddit"""
        
        # If Reddit is enabled, get real sentiment data
        if self.reddit_enabled and self.reddit:
            try:
                return self._get_reddit_sentiment(ticker)
            except Exception as e:
                logging.error(f"Error getting Reddit sentiment for {ticker}: {e}")
                print(f"Reddit sentiment failed, falling back to simulated data: {e}")
        
        # Fallback to simulated sentiment if Reddit not available
        return self._get_simulated_sentiment(ticker)
    
    def _get_reddit_sentiment(self, ticker: str, days: int = 7) -> Dict:
        """Get real Reddit sentiment for a stock ticker"""
        
        # Subreddits to search for financial discussions
        subreddits = ['investing', 'stocks', 'SecurityAnalysis', 'StockMarket', 'ValueInvesting']
        
        # Search terms for the ticker
        search_terms = [f"${ticker}", ticker, f"#{ticker}"]
        
        posts_data = []
        cutoff_date = datetime.now() - timedelta(days=days)
        
        for subreddit_name in subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                
                # Search recent posts mentioning the ticker
                for term in search_terms:
                    for post in subreddit.search(term, time_filter='week', limit=10):
                        # Check if post is recent enough
                        post_date = datetime.fromtimestamp(post.created_utc)
                        if post_date > cutoff_date:
                            
                            # Analyze sentiment of title and body
                            text = f"{post.title}. {post.selftext}"
                            if len(text.strip()) > 10:  # Only analyze substantial content
                                blob = TextBlob(text)
                                
                                posts_data.append({
                                    'title': post.title,
                                    'score': post.score,  # Reddit upvotes
                                    'num_comments': post.num_comments,
                                    'sentiment': blob.sentiment.polarity,
                                    'subjectivity': blob.sentiment.subjectivity,
                                    'subreddit': subreddit_name,
                                    'created': post_date,
                                    'url': f'https://reddit.com{post.permalink}'
                                })
                        
                        # Rate limiting
                        time.sleep(0.1)
                        
            except Exception as e:
                logging.warning(f"Error accessing r/{subreddit_name}: {e}")
                continue
        
        return self._analyze_reddit_data(posts_data, ticker)
    
    def _analyze_reddit_data(self, posts_data: list, ticker: str) -> Dict:
        """Analyze collected Reddit data"""
        
        if not posts_data:
            return self._default_social_sentiment()
        
        # Calculate sentiment metrics
        sentiments = [post['sentiment'] for post in posts_data]
        scores = [post['score'] for post in posts_data]
        comments = [post['num_comments'] for post in posts_data]
        
        avg_sentiment = np.mean(sentiments)
        total_mentions = len(posts_data)
        avg_upvotes = np.mean(scores) if scores else 0
        total_engagement = sum(scores) + sum(comments)
        
        # Determine momentum based on sentiment distribution
        positive_posts = len([s for s in sentiments if s > 0.1])
        negative_posts = len([s for s in sentiments if s < -0.1])
        
        if positive_posts > negative_posts * 1.5:
            momentum = 'bullish'
        elif negative_posts > positive_posts * 1.5:
            momentum = 'bearish'
        else:
            momentum = 'neutral'
        
        # Check if trending (high engagement + mentions)
        trending = total_mentions >= 5 and avg_upvotes > 10
        volume_buzz = total_engagement > 100
        
        # Get top posts for context
        top_posts = sorted(posts_data, key=lambda x: x['score'], reverse=True)[:3]
        top_posts_info = [{
            'title': post['title'][:100] + '...' if len(post['title']) > 100 else post['title'],
            'score': post['score'],
            'sentiment': round(post['sentiment'], 2),
            'subreddit': post['subreddit']
        } for post in top_posts]
        
        return {
            'score': float(avg_sentiment),
            'mentions_count': total_mentions,
            'trending': trending,
            'momentum': momentum,
            'volume_buzz': volume_buzz,
            'avg_upvotes': float(avg_upvotes),
            'total_engagement': int(total_engagement),
            'positive_posts': positive_posts,
            'negative_posts': negative_posts,
            'top_posts': top_posts_info,
            'data_source': 'reddit_api'
        }
    
    def _get_simulated_sentiment(self, ticker: str) -> Dict:
        """Fallback simulated sentiment based on stock performance"""
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5d")
            
            if hist.empty:
                return self._default_social_sentiment()
            
            # Calculate momentum and volatility for sentiment simulation
            recent_return = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
            volatility = hist['Close'].pct_change().std() * 100
            volume_change = ((hist['Volume'].iloc[-1] - hist['Volume'].mean()) / hist['Volume'].mean()) * 100
            
            # Simulate sentiment based on performance
            base_sentiment = min(max(recent_return / 10, -1), 1)  # Scale to -1 to 1
            
            # Adjust for volatility (high volatility = more extreme sentiment)
            volatility_factor = min(volatility / 5, 2)
            social_sentiment = base_sentiment * (1 + volatility_factor / 4)
            
            # Simulate mention counts
            mentions = max(int(50 + volume_change), 10)
            
            result = {
                'score': social_sentiment,
                'mentions_count': mentions,
                'trending': abs(social_sentiment) > 0.3,
                'momentum': 'bullish' if social_sentiment > 0.2 else 'bearish' if social_sentiment < -0.2 else 'neutral',
                'volume_buzz': volume_change > 20,
                'data_source': 'simulated'
            }
            
            return result
            
        except Exception as e:
            logging.error(f"Error getting simulated sentiment for {ticker}: {e}")
            return self._default_social_sentiment()
    
    def get_market_indicators(self) -> Dict:
        """Get general market sentiment indicators"""
        try:
            # Get VIX (Fear & Greed Index)
            vix = yf.Ticker("^VIX")
            vix_hist = vix.history(period="5d")
            
            # Get SPY for market trend
            spy = yf.Ticker("SPY")
            spy_hist = spy.history(period="1mo")
            
            indicators = {
                'vix_level': 20,  # Default
                'vix_trend': 'stable',
                'market_trend': 'neutral',
                'fear_greed_index': 50,
                'market_regime': 'normal'
            }
            
            if not vix_hist.empty:
                current_vix = vix_hist['Close'].iloc[-1]
                indicators['vix_level'] = current_vix
                
                # VIX interpretation
                if current_vix < 15:
                    indicators['fear_greed_index'] = 80  # Greed
                    indicators['market_regime'] = 'complacent'
                elif current_vix < 25:
                    indicators['fear_greed_index'] = 60  # Neutral-Greed
                    indicators['market_regime'] = 'normal'
                elif current_vix < 35:
                    indicators['fear_greed_index'] = 30  # Fear
                    indicators['market_regime'] = 'volatile'
                else:
                    indicators['fear_greed_index'] = 10  # Extreme Fear
                    indicators['market_regime'] = 'crisis'
            
            if not spy_hist.empty:
                spy_return = ((spy_hist['Close'].iloc[-1] - spy_hist['Close'].iloc[-21]) / spy_hist['Close'].iloc[-21]) * 100
                indicators['market_trend'] = 'bullish' if spy_return > 2 else 'bearish' if spy_return < -2 else 'neutral'
            
            return indicators
            
        except Exception as e:
            logging.error(f"Error getting market indicators: {e}")
            return {
                'vix_level': 20,
                'vix_trend': 'stable',
                'market_trend': 'neutral',
                'fear_greed_index': 50,
                'market_regime': 'normal'
            }
    
    def get_analyst_sentiment(self, ticker: str) -> Dict:
        """Get analyst sentiment and recommendations"""
        try:
            stock = yf.Ticker(ticker)
            
            # Get analyst recommendations
            recommendations = stock.recommendations
            info = stock.info
            
            analyst_data = {
                'target_price': None,
                'current_price': None,
                'upside_potential': 0,
                'recommendation': 'hold',
                'analyst_count': 0,
                'upgrade_trend': 'stable'
            }
            
            # Get target price from info
            if info:
                analyst_data['target_price'] = info.get('targetMeanPrice')
                analyst_data['current_price'] = info.get('currentPrice')
                
                if analyst_data['target_price'] and analyst_data['current_price']:
                    analyst_data['upside_potential'] = ((analyst_data['target_price'] - analyst_data['current_price']) / analyst_data['current_price']) * 100
            
            # Analyze recent recommendations if available
            if recommendations is not None and not recommendations.empty:
                recent_recs = recommendations.tail(10)
                
                # Count recommendation types
                buy_count = len(recent_recs[recent_recs['To Grade'].str.contains('Buy|Strong Buy', case=False, na=False)])
                hold_count = len(recent_recs[recent_recs['To Grade'].str.contains('Hold', case=False, na=False)])
                sell_count = len(recent_recs[recent_recs['To Grade'].str.contains('Sell', case=False, na=False)])
                
                total_recs = len(recent_recs)
                analyst_data['analyst_count'] = total_recs
                
                if total_recs > 0:
                    if buy_count / total_recs > 0.6:
                        analyst_data['recommendation'] = 'strong_buy'
                    elif buy_count / total_recs > 0.4:
                        analyst_data['recommendation'] = 'buy'
                    elif sell_count / total_recs > 0.4:
                        analyst_data['recommendation'] = 'sell'
                    else:
                        analyst_data['recommendation'] = 'hold'
            
            return analyst_data
            
        except Exception as e:
            logging.error(f"Error getting analyst sentiment for {ticker}: {e}")
            return {
                'target_price': None,
                'current_price': None,
                'upside_potential': 0,
                'recommendation': 'hold',
                'analyst_count': 0,
                'upgrade_trend': 'stable'
            }
    
    def calculate_composite_sentiment(self, sentiment_data: Dict) -> float:
        """Calculate composite sentiment score from all sources"""
        weights = {
            'news': 0.3,
            'social': 0.25,
            'market': 0.25,
            'analyst': 0.2
        }
        
        # News sentiment
        news_score = sentiment_data['news_sentiment']['score']
        
        # Social sentiment
        social_score = sentiment_data['social_sentiment']['score']
        
        # Market sentiment (based on fear/greed index)
        market_score = (sentiment_data['market_indicators']['fear_greed_index'] - 50) / 50
        
        # Analyst sentiment
        analyst_rec = sentiment_data['analyst_sentiment']['recommendation']
        analyst_score = {
            'strong_buy': 1.0,
            'buy': 0.5,
            'hold': 0.0,
            'sell': -0.5,
            'strong_sell': -1.0
        }.get(analyst_rec, 0.0)
        
        # Calculate weighted composite score
        composite = (
            news_score * weights['news'] +
            social_score * weights['social'] +
            market_score * weights['market'] +
            analyst_score * weights['analyst']
        )
        
        return max(min(composite, 1.0), -1.0)  # Clamp to [-1, 1]
    
    def get_sentiment_strength(self, score: float) -> str:
        """Convert sentiment score to human-readable strength"""
        if score > 0.6:
            return 'very_positive'
        elif score > 0.2:
            return 'positive'
        elif score > -0.2:
            return 'neutral'
        elif score > -0.6:
            return 'negative'
        else:
            return 'very_negative'
    
    def _default_social_sentiment(self) -> Dict:
        """Default social sentiment data"""
        return {
            'score': 0,
            'mentions_count': 25,
            'trending': False,
            'momentum': 'neutral',
            'volume_buzz': False,
            'data_source': 'default'
        }
    
    def get_sentiment_summary(self, ticker: str) -> str:
        """Get human-readable sentiment summary"""
        sentiment = self.get_comprehensive_sentiment(ticker)
        
        news = sentiment['news_sentiment']
        social = sentiment['social_sentiment']
        market = sentiment['market_indicators']
        
        summary_parts = []
        
        # News sentiment
        if news['articles_count'] > 0:
            if news['score'] > 0.2:
                summary_parts.append(f"Positive news coverage ({news['positive_count']} positive articles)")
            elif news['score'] < -0.2:
                summary_parts.append(f"Negative news coverage ({news['negative_count']} negative articles)")
        
        # Social sentiment
        if social['trending']:
            summary_parts.append(f"Trending on social media ({social['mentions_count']} mentions)")
        
        # Market conditions
        summary_parts.append(f"Market regime: {market['market_regime']} (VIX: {market['vix_level']:.1f})")
        
        return "; ".join(summary_parts) if summary_parts else "Neutral sentiment across all sources"
    
    def _get_source_credibility_weight(self, article: dict) -> float:
        """Assign credibility weight based on news source"""
        source = article.get('publisher', '').lower()
        
        # High credibility sources
        high_credibility = ['reuters', 'bloomberg', 'wsj', 'financial times', 'marketwatch', 'cnbc']
        # Medium credibility sources  
        medium_credibility = ['yahoo finance', 'seeking alpha', 'motley fool', 'benzinga']
        # Low credibility (default)
        
        if any(trusted in source for trusted in high_credibility):
            return 1.2  # 20% boost for trusted sources
        elif any(medium in source for medium in medium_credibility):
            return 1.0  # Normal weight
        else:
            return 0.8  # Slight discount for unknown sources
    
    def _calculate_sentiment_velocity(self, headlines: list) -> float:
        """Calculate rate of sentiment change over time"""
        if len(headlines) < 3:
            return 0
        
        # Sort by publication time
        sorted_headlines = sorted(headlines, key=lambda x: x['published'])
        
        # Calculate sentiment trend using linear regression
        times = [h['published'] for h in sorted_headlines]
        sentiments = [h['sentiment'] for h in sorted_headlines]
        
        if len(times) > 1:
            # Simple slope calculation
            time_span = (times[-1] - times[0]) / 3600  # Convert to hours
            if time_span > 0:
                sentiment_change = sentiments[-1] - sentiments[0]
                velocity = sentiment_change / time_span  # Sentiment change per hour
                return velocity
        
        return 0