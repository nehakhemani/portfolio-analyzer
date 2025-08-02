# ☁️ Deploy to Google Cloud (Free $300 Credit + Always Free Tier)

Google Cloud is perfect for personal projects with generous free tiers and scales to zero (pay only when used).

## 💰 Google Cloud Benefits
- **$300 free credit** for new users (90 days)
- **Always Free tier** - 2 million requests/month
- **Pay-per-use** - costs $0 when not used
- **Scales to zero** - automatic scaling
- **Professional infrastructure** - Google's global network

## 🎯 Two Deployment Options

### Option 1: Cloud Run (Recommended)
- **Best for**: Personal projects, automatic scaling
- **Cost**: $0 for low usage, scales with demand
- **Features**: Serverless, containers, global deployment

### Option 2: App Engine
- **Best for**: Simple Flask apps, zero config
- **Cost**: $0 for low usage
- **Features**: Fully managed, automatic scaling

## 🚀 Cloud Run Deployment (Recommended)

### Step 1: Setup Google Cloud
1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create account (get $300 free credit)
3. Create new project: "portfolio-analyzer"
4. Enable required APIs:
   - Cloud Run API
   - Cloud Build API
   - Container Registry API

### Step 2: Install Google Cloud CLI
**Windows:**
```bash
# Download and install from: https://cloud.google.com/sdk/docs/install
# Or use PowerShell:
(New-Object Net.WebClient).DownloadFile("https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe", "$env:Temp\GoogleCloudSDKInstaller.exe")
& $env:Temp\GoogleCloudSDKInstaller.exe
```

**Alternative: Use Cloud Shell** (no installation needed)
- Go to console.cloud.google.com
- Click "Activate Cloud Shell" (terminal icon)
- Upload your project files

### Step 3: Deploy Your App

**Method A: One-Command Deploy**
```bash
# Clone your repo in Cloud Shell or local terminal
git clone https://github.com/yourusername/your-repo.git
cd your-repo

# Login to Google Cloud
gcloud auth login

# Set your project
gcloud config set project your-project-id

# Deploy to Cloud Run (one command!)
gcloud run deploy portfolio-analyzer \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --max-instances 10

# Your app will be available at:
# https://portfolio-analyzer-[hash]-uc.a.run.app
```

**Method B: Using Dockerfile**
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/your-project-id/portfolio-analyzer
gcloud run deploy portfolio-analyzer \
  --image gcr.io/your-project-id/portfolio-analyzer \
  --region us-central1 \
  --allow-unauthenticated
```

### Step 4: Set Environment Variables (Optional)
```bash
# Add Reddit API credentials
gcloud run services update portfolio-analyzer \
  --update-env-vars REDDIT_CLIENT_ID=your_client_id,REDDIT_CLIENT_SECRET=your_secret \
  --region us-central1
```

### Step 5: Custom Domain (Optional)
```bash
# Map custom domain
gcloud run domain-mappings create \
  --service portfolio-analyzer \
  --domain your-domain.com \
  --region us-central1
```

## 🔧 Alternative: App Engine (Simpler)

### Step 1: Deploy to App Engine
```bash
# From your project directory
gcloud app deploy app.yaml

# Your app will be available at:
# https://your-project-id.appspot.com
```

### Step 2: Set Environment Variables
Edit `app.yaml` and add:
```yaml
env_variables:
  REDDIT_CLIENT_ID: "your_client_id"
  REDDIT_CLIENT_SECRET: "your_client_secret"
```

Then redeploy:
```bash
gcloud app deploy
```

## 💰 Cost Breakdown

### Free Tier (Always Free)
- **Cloud Run**: 2 million requests/month
- **App Engine**: 28 instance hours/day
- **Cloud Build**: 120 build minutes/day
- **Storage**: 5GB

### Typical Personal Project Costs
- **Cloud Run**: $0-2/month (most personal projects stay free)
- **App Engine**: $0-5/month
- **Storage/Database**: $0-1/month

### $300 Credit Benefits
- Covers 3-12 months of usage
- Try premium features
- Scale up for demos/testing

## 🌐 Features You Get

✅ **Global CDN** - Fast worldwide access
✅ **Automatic HTTPS** - SSL certificates included  
✅ **Custom domains** - Professional URLs
✅ **Auto-scaling** - Handles traffic spikes
✅ **Zero downtime deploys** - Blue/green deployments
✅ **Monitoring & Logging** - Google Cloud Console
✅ **Security** - Google's enterprise security

## 🔄 Continuous Deployment

### Connect to GitHub (Automated deploys)
1. Go to Cloud Build → Triggers
2. Connect your GitHub repository
3. Create trigger on push to main branch
4. Uses `cloudbuild.yaml` for automatic deployment

### Manual Updates
```bash
# After making changes
git push origin main

# Or redeploy manually
gcloud run deploy portfolio-analyzer --source .
```

## 🛠 Monitoring & Debugging

### View Logs
```bash
# Cloud Run logs
gcloud run services describe portfolio-analyzer --region us-central1

# Stream live logs
gcloud logging tail "resource.type=cloud_run_revision"
```

### Access Cloud Console
- Go to console.cloud.google.com
- Navigate to Cloud Run or App Engine
- View metrics, logs, and performance

## ⚡ Performance Optimization

### Cloud Run Settings
- **Memory**: 1Gi (good for portfolio analysis)
- **CPU**: 1 vCPU (handles multiple users)
- **Concurrency**: 80 (requests per instance)
- **Max instances**: 10 (auto-scales up)

### Cold Start Optimization
- Uses gunicorn for faster startup
- Dockerfile optimized for caching
- Minimal container size

## 🔐 Security

### Environment Variables
Store secrets securely:
```bash
# Using Secret Manager (recommended)
gcloud secrets create reddit-client-id --data-file=client_id.txt
gcloud secrets create reddit-client-secret --data-file=client_secret.txt

# Mount secrets in Cloud Run
gcloud run services update portfolio-analyzer \
  --update-secrets REDDIT_CLIENT_ID=reddit-client-id:latest,REDDIT_CLIENT_SECRET=reddit-client-secret:latest
```

## 🆚 Comparison: Cloud Run vs App Engine

| Feature | Cloud Run | App Engine |
|---------|-----------|------------|
| **Container Support** | ✅ Docker | ❌ Runtime only |
| **Scaling** | 0 to thousands | 0 to hundreds |
| **Cold Start** | ~1-2 seconds | ~3-5 seconds |
| **Custom Domains** | ✅ Yes | ✅ Yes |
| **WebSockets** | ✅ Yes | ❌ No |
| **Complexity** | Medium | Low |

## 🎉 Final Result

After deployment, you'll have:
- **Professional URL**: `https://portfolio-analyzer-xyz.a.run.app`
- **Global availability** with Google's CDN
- **Automatic scaling** from 0 to high traffic
- **Zero cost** for low usage
- **Enterprise-grade** security and monitoring

**Ready to deploy?** 
1. Create Google Cloud account
2. Follow the Cloud Run deployment steps above
3. Your portfolio analyzer will be live in ~5 minutes!

---

**Pro tip**: Start with Cloud Run for flexibility, switch to App Engine if you want maximum simplicity.