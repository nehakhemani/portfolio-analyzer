#!/usr/bin/env python3
"""
Test Reddit Sentiment Integration
Run this to test if Reddit API is working correctly
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from services.market_sentiment import MarketSentimentAnalyzer
import json

def test_reddit_sentiment():
    """Test Reddit sentiment analysis"""
    
    print("Testing Reddit Sentiment Integration")
    print("=" * 50)
    
    # Initialize analyzer
    analyzer = MarketSentimentAnalyzer()
    
    # Check if Reddit is enabled
    print(f"Reddit API Available: {analyzer.reddit_enabled}")
    
    if not analyzer.reddit_enabled:
        print("\n! Reddit API not configured")
        print("To enable Reddit sentiment:")
        print("1. Go to https://www.reddit.com/prefs/apps")
        print("2. Create a new app (script type)")
        print("3. Copy .env.example to .env")
        print("4. Add your Reddit credentials to .env")
        print("\nTesting will use simulated data...")
    
    # Test stocks
    test_tickers = ['AAPL', 'TSLA', 'NVDA']
    
    for ticker in test_tickers:
        print(f"\nTesting {ticker}...")
        
        try:
            # Get social sentiment
            social_sentiment = analyzer.get_social_sentiment(ticker)
            
            print(f"Data Source: {social_sentiment.get('data_source', 'unknown')}")
            print(f"Sentiment Score: {social_sentiment['score']:.3f}")
            print(f"Mentions: {social_sentiment['mentions_count']}")
            print(f"Momentum: {social_sentiment['momentum']}")
            print(f"Trending: {social_sentiment['trending']}")
            
            # If Reddit data, show additional info
            if social_sentiment.get('data_source') == 'reddit_api':
                print(f"Avg Upvotes: {social_sentiment.get('avg_upvotes', 0):.1f}")
                print(f"Total Engagement: {social_sentiment.get('total_engagement', 0)}")
                print(f"Positive Posts: {social_sentiment.get('positive_posts', 0)}")
                print(f"Negative Posts: {social_sentiment.get('negative_posts', 0)}")
                
                top_posts = social_sentiment.get('top_posts', [])
                if top_posts:
                    print("\nTop Reddit Posts:")
                    for i, post in enumerate(top_posts[:2], 1):
                        print(f"  {i}. {post['title']} (Score: {post['score']}, Sentiment: {post['sentiment']})")
            
        except Exception as e:
            print(f"X Error testing {ticker}: {e}")
    
    print("\n" + "=" * 50)
    print("Testing completed!")

if __name__ == '__main__':
    test_reddit_sentiment()