# 🎨 Deploy to Render (Free - 750 hours/month)

Render offers 750 free hours per month, which is perfect for personal projects. The app sleeps after 15 minutes of inactivity but wakes up quickly.

## ✅ Why Render?
- **Completely free** - 750 hours/month (31 days = 744 hours)
- **Auto-sleep** - saves resources, wakes in ~30 seconds
- **GitHub integration** - auto-deploy on push
- **Free SSL** - HTTPS included
- **PostgreSQL** - free 90-day database
- **Easy setup** - similar to Heroku

## 🚀 5-Minute Deployment

### Step 1: Create render.yaml
I'll create the configuration file for you.

### Step 2: Deploy to Render
1. Go to [render.com](https://render.com)
2. Sign up with GitHub
3. Click **"New +"** → **"Web Service"**
4. Connect your GitHub repository
5. Use these settings:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT backend.app:app`
   - **Python Version**: 3.10.12

### Step 3: Configure Environment Variables
In Render dashboard:
1. Go to your service → **"Environment"**
2. Add variables:
   - `PYTHON_VERSION`: `3.10.12`
   - `REDDIT_CLIENT_ID`: (optional)
   - `REDDIT_CLIENT_SECRET`: (optional)

### Step 4: Access Your App
- Render provides URL like: `https://portfolio-analyzer-abc123.onrender.com`
- App sleeps after 15min inactivity
- Wakes up in ~30 seconds when accessed

## 💰 Cost: $0/month

**Free tier includes:**
- 750 hours/month (basically unlimited for personal use)
- 512MB RAM
- Custom domains
- Automatic HTTPS
- Build minutes included

**Perfect for:**
- Personal projects
- Demos and portfolios
- Low-traffic applications
- Development/testing

## ⚡ Performance Notes

**Cold Start:**
- App sleeps after 15 minutes of no requests
- Wake-up time: ~15-30 seconds
- After wake-up: normal performance

**Workaround for Always-On:**
- Set up a simple cron job to ping your app every 14 minutes
- Use services like [cron-job.org](https://cron-job.org) (free)
- Keeps your app awake during active hours

## 🆚 Render vs Railway

| Feature | Render (Free) | Railway ($5 credit) |
|---------|---------------|-------------------|
| **Cost** | $0 | ~$1-3/month |
| **Uptime** | Sleeps after 15min | Always-on |
| **RAM** | 512MB | 1GB |
| **Storage** | 1GB | 1GB |
| **Database** | PostgreSQL (90 days) | PostgreSQL (unlimited) |
| **Custom Domain** | ✅ Free | ✅ Free |
| **SSL** | ✅ Free | ✅ Free |

## 🔄 Auto-Deploy

After setup:
1. Push changes to GitHub
2. Render automatically rebuilds
3. New version live in ~2-3 minutes
4. Zero downtime deployments

---

**Best for:** Truly free hosting with professional features, perfect if you don't mind occasional cold starts.