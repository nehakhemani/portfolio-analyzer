# Reddit API Setup for Social Sentiment Analysis

Your portfolio analyzer now includes real Reddit sentiment analysis! Follow these steps to enable it:

## 1. Create Reddit App

1. Go to https://www.reddit.com/prefs/apps
2. Click "Create App" or "Create Another App"
3. Fill in the form:
   - **Name**: Portfolio Analyzer
   - **App type**: Select "script"
   - **Description**: Portfolio sentiment analysis
   - **About URL**: Leave empty
   - **Redirect URI**: http://localhost:8080 (required but not used)
4. Click "Create app"

## 2. Get Your Credentials

After creating the app, you'll see:
- **Client ID**: The string under your app name (e.g., `AbCdEf123456`)
- **Client Secret**: The "secret" field (e.g., `XyZ789AbCdEf123456789`)

## 3. Configure Environment Variables

1. Copy the example environment file:
   ```bash
   copy backend\.env.example backend\.env
   ```

2. Edit `backend\.env` and add your credentials:
   ```
   REDDIT_CLIENT_ID=your_client_id_here
   REDDIT_CLIENT_SECRET=your_client_secret_here
   REDDIT_USER_AGENT=portfolio_analyzer_1.0
   REDDIT_SENTIMENT_ENABLED=true
   ```

## 4. Test the Integration

Run the test script to verify everything works:
```bash
python test_reddit_sentiment.py
```

You should see "Reddit API Available: True" and real Reddit data.

## 5. Restart Your Server

After configuring Reddit API:
```bash
python backend/restart_server.py
python backend/app.py
```

## What You Get

With Reddit integration enabled:
- **Real sentiment data** from r/investing, r/stocks, r/SecurityAnalysis, and more
- **Actual mention counts** from Reddit posts
- **Top posts** with sentiment scores
- **Engagement metrics** (upvotes, comments)
- **Trending detection** based on real social activity

## Free Tier Limits

Reddit API is completely free for personal use:
- 60 requests per minute
- No monthly limits
- No registration fees

## Troubleshooting

**"Invalid credentials"**: Double-check your client ID and secret
**"403 Forbidden"**: Make sure you selected "script" type app
**"Rate limited"**: Wait a minute and try again
**Unicode errors**: Your system doesn't support emojis (functionality still works)

## Subreddits Analyzed

The system searches these investing subreddits:
- r/investing
- r/stocks  
- r/SecurityAnalysis
- r/StockMarket
- r/ValueInvesting

## Privacy & Security

- Your Reddit credentials stay on your local machine
- No data is sent to third parties
- Read-only access to public Reddit posts
- No access to your personal Reddit account