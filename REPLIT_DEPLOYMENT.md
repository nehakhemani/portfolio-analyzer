# 🚀 Deploy Portfolio Analyzer to Replit

This guide will help you deploy your Portfolio Analyzer to Replit for temporary hosting and sharing.

## ✅ Quick Deploy Steps

### 1. Create New Replit
1. Go to [replit.com](https://replit.com)
2. Click "Create Repl"
3. Choose "Import from GitHub" or "Upload files"

### 2. Upload Your Files
**Option A: GitHub Import (Recommended)**
1. If your code is on GitHub, paste the repository URL
2. Replit will automatically import everything

**Option B: File Upload**
1. Create a new Python Repl
2. Delete the default `main.py`
3. Upload all your project files by dragging them into the file explorer
4. Make sure the folder structure matches:
```
Portfolio-analyzer_app/
├── main.py              # ← Entry point for Replit
├── requirements.txt     # ← Dependencies
├── .replit             # ← Replit configuration
├── replit.nix          # ← System dependencies
├── backend/            # ← Flask application
├── frontend/           # ← Web interface
├── uploads/            # ← CSV uploads (auto-created)
└── README.md
```

### 3. Install Dependencies
Replit should automatically install from `requirements.txt`, but if needed:
```bash
pip install -r requirements.txt
```

### 4. Run the Application
1. Click the "Run" button (green play button)
2. The app will start on port 5000 (or Replit's assigned port)
3. Open the web view to access your portfolio analyzer

### 5. Configure Environment Variables (Optional)
To enable Reddit sentiment analysis:
1. Click "Secrets" tab in the left sidebar
2. Add these environment variables:
   - `REDDIT_CLIENT_ID`: Your Reddit app client ID
   - `REDDIT_CLIENT_SECRET`: Your Reddit app client secret
   - `REDDIT_USER_AGENT`: `portfolio_analyzer_1.0`

## 🔧 Configuration Files Explained

**main.py**: Entry point optimized for Replit
**requirements.txt**: All Python dependencies
**.replit**: Replit configuration (run command, environment)
**replit.nix**: System-level dependencies

## 🌐 Accessing Your App

Once deployed:
1. Click the web view icon (browser icon) in Replit
2. Your app will open in a new tab
3. Use the login: username: `admin`, password: `portfolio123`
4. Upload CSV files and analyze your portfolio!

## 📊 Features Available

✅ **Portfolio Analysis**: Upload CSV, view holdings, calculate returns
✅ **Market Data**: Real-time stock prices via Yahoo Finance
✅ **Sentiment Analysis**: Social media sentiment (Reddit integration optional)
✅ **ML Recommendations**: AI-powered investment recommendations
✅ **Multi-Currency Support**: Convert between 163+ currencies
✅ **Risk Assessment**: Portfolio risk metrics and diversification analysis
✅ **Export Options**: Download portfolio data as CSV/JSON

## 🔒 Security Notes

- Default login is `admin` / `portfolio123` - change this for production
- SQLite database is stored in Replit (persistent storage)
- API keys (Reddit, etc.) are stored as Replit Secrets
- All data stays within your Replit environment

## 🛠 Troubleshooting

**App won't start**: Check the console for Python errors, ensure all files uploaded correctly

**Missing dependencies**: Run `pip install -r requirements.txt` in the shell

**Database errors**: The SQLite database is auto-created on first run

**Port issues**: Replit automatically assigns ports, the app adapts automatically

**CSV upload fails**: Check file format matches the sample CSV structure

## 📱 Sharing Your App

1. Click "Share" button in top-right of Replit
2. Copy the public URL 
3. Share with anyone - they can access without Replit account
4. For private sharing, use "Invite" to add collaborators

## 🚀 Performance Tips

- Replit free tier has some limitations on CPU/memory
- For heavy usage, consider upgrading to Replit Core
- Database and uploaded files persist between sessions
- App may sleep after inactivity (normal for free tier)

## 🔄 Updates and Maintenance

To update your deployed app:
1. Upload new files to Replit
2. Restart the application
3. Database and user data will be preserved

---

**Need help?** Check the console logs in Replit for debugging information.

**Want local development?** See the main README.md for local setup instructions.