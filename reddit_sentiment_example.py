#!/usr/bin/env python3
"""
Example: Real Reddit Sentiment Integration (Free)
This shows how to get actual social media sentiment from Reddit
"""

import praw
import pandas as pd
from textblob import TextBlob
import time
from datetime import datetime, timedelta

class RedditSentimentAnalyzer:
    """Get real sentiment data from Reddit - completely free"""
    
    def __init__(self):
        # You need to register a Reddit app at https://www.reddit.com/prefs/apps
        # Then replace these with your credentials
        self.reddit = praw.Reddit(
            client_id="YOUR_CLIENT_ID",
            client_secret="YOUR_CLIENT_SECRET", 
            user_agent="portfolio_analyzer_1.0"
        )
        
    def get_reddit_sentiment(self, ticker: str, days: int = 7) -> dict:
        """Get real Reddit sentiment for a stock ticker"""
        
        # Subreddits to search
        subreddits = ['investing', 'stocks', 'SecurityAnalysis', 'StockMarket']
        
        # Search terms
        search_terms = [f"${ticker}", ticker, f"#{ticker}"]
        
        posts_data = []
        
        for subreddit_name in subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                
                # Search recent posts mentioning the ticker
                for term in search_terms:
                    for post in subreddit.search(term, time_filter='week', limit=20):
                        # Check if post is recent enough
                        post_date = datetime.fromtimestamp(post.created_utc)
                        if post_date > datetime.now() - timedelta(days=days):
                            
                            # Analyze sentiment of title and body
                            text = f"{post.title}. {post.selftext}"
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
                            
                    time.sleep(0.1)  # Rate limiting
                    
            except Exception as e:
                print(f"Error accessing r/{subreddit_name}: {e}")
        
        return self._analyze_reddit_data(posts_data, ticker)
    
    def _analyze_reddit_data(self, posts_data: list, ticker: str) -> dict:
        """Analyze collected Reddit data"""
        
        if not posts_data:
            return {
                'score': 0,
                'mentions_count': 0,
                'trending': False,
                'momentum': 'neutral',
                'volume_buzz': False,
                'top_posts': []
            }
        
        df = pd.DataFrame(posts_data)
        
        # Calculate metrics
        avg_sentiment = df['sentiment'].mean()
        total_mentions = len(df)
        avg_upvotes = df['score'].mean()
        total_engagement = df['score'].sum() + df['num_comments'].sum()
        
        # Determine momentum
        momentum = 'bullish' if avg_sentiment > 0.1 else 'bearish' if avg_sentiment < -0.1 else 'neutral'
        
        # Check if trending (high engagement + mentions)
        trending = total_mentions > 10 and avg_upvotes > 20
        
        # Top posts by engagement
        top_posts = df.nlargest(3, 'score')[['title', 'score', 'sentiment', 'url']].to_dict('records')
        
        return {
            'score': float(avg_sentiment),
            'mentions_count': total_mentions,
            'trending': trending,
            'momentum': momentum,
            'volume_buzz': total_engagement > 500,
            'avg_upvotes': float(avg_upvotes),
            'total_engagement': int(total_engagement),
            'top_posts': top_posts,
            'data_source': 'reddit_api'
        }

# Example usage
if __name__ == '__main__':
    # Note: You need to set up Reddit API credentials first
    print("Reddit Sentiment Analysis Example")
    print("1. Go to https://www.reddit.com/prefs/apps")
    print("2. Create a new app (script type)")
    print("3. Replace YOUR_CLIENT_ID and YOUR_CLIENT_SECRET above")
    print("4. Install: pip install praw textblob pandas")
    
    # Example call (won't work without credentials):
    # analyzer = RedditSentimentAnalyzer()
    # sentiment = analyzer.get_reddit_sentiment('AAPL')
    # print(sentiment)