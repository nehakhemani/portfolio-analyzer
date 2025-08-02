# 🚂 Deploy to Railway (Free $5/month credit)

Railway is perfect for personal projects - you get $5 monthly credit which easily covers small applications.

## ✅ Why Railway?
- **Free $5/month credit** (usually enough for personal projects)
- **GitHub integration** - auto-deploy on git push
- **Always-on** - no sleeping (unlike Render/Heroku)
- **Custom domains** - get a professional URL
- **Built-in databases** - PostgreSQL, Redis, etc.
- **Environment variables** - easy secret management

## 🚀 5-Minute Deployment

### Step 1: Prepare Your App
Add these files to your project (I'll create them):

1. **`railway.json`** - Railway configuration
2. **`Procfile`** - Process configuration  
3. **`runtime.txt`** - Python version
4. Update **`requirements.txt`** - Add gunicorn

### Step 2: Deploy
1. Go to [railway.app](https://railway.app)
2. Sign up with GitHub
3. Click **"New Project"** → **"Deploy from GitHub repo"**
4. Select your portfolio analyzer repository
5. Railway auto-detects Python and deploys!

### Step 3: Configure Environment
1. In Railway dashboard, go to your project
2. Click **"Variables"** tab
3. Add these variables:
   - `PORT`: (Railway sets this automatically)
   - `REDDIT_CLIENT_ID`: (optional - your Reddit API key)
   - `REDDIT_CLIENT_SECRET`: (optional - your Reddit API secret)

### Step 4: Access Your App
1. Railway provides a URL like: `https://portfolio-analyzer-production.up.railway.app`
2. Click the URL to access your app
3. Login: `admin` / `portfolio123`

## 💰 Cost Breakdown

**Free tier includes:**
- $5 monthly credit
- Up to 500 hours runtime (~17 days always-on)
- 1GB RAM, 1 vCPU
- 1GB disk space

**Typical usage for personal project:**
- Small Flask app: ~$1-3/month
- **Result: Usually stays within free $5 credit!**

## 🔧 Custom Domain (Optional)
1. Buy domain from Namecheap/GoDaddy (~$10/year)
2. In Railway: Settings → Domains → Add custom domain
3. Update DNS records as shown
4. Get professional URL like `portfolio.yourdomain.com`

## 📊 What You Get

✅ **Always-on application** (no sleeping)
✅ **Automatic HTTPS** (SSL certificate included)
✅ **GitHub integration** (auto-deploy on push)
✅ **Environment variables** (secure secret storage)
✅ **Custom domains** (professional URLs)
✅ **Built-in monitoring** (logs, metrics, alerts)
✅ **Database options** (PostgreSQL, Redis, etc.)

## 🆚 Comparison with Other Platforms

| Platform | Free Tier | Always-On | Auto-Deploy | Database |
|----------|-----------|-----------|-------------|----------|
| **Railway** | $5 credit | ✅ Yes | ✅ Yes | ✅ Yes |
| Render | 750hrs | ❌ Sleeps | ✅ Yes | ✅ Yes |
| Replit | Limited | ❌ Sleeps | ✅ Yes | ❌ No |
| PythonAnywhere | Always-on | ✅ Yes | ❌ Manual | ⚠️ Limited |
| Fly.io | $5 credit | ✅ Yes | ✅ Yes | ✅ Yes |

## 🔄 Easy Updates

After initial deployment:
1. Make changes to your code
2. Push to GitHub: `git push origin main`
3. Railway automatically rebuilds and deploys
4. Your app updates in ~2-3 minutes

---

**Bottom line:** Railway gives you a professional deployment experience for free, perfect for personal projects!