# Portfolio Analyzer - External Deployment Guide

## 🚀 Your server is now configured for external access!

### Quick Start
```bash
cd C:\Users\NEHA\Documents\Portfolio-analyzer_app
python start_server.py
```

## 🌐 Access Methods

### 1. Local Network Access (Recommended)
- **Your IP**: `192.168.1.66:5001`
- **URL**: `http://192.168.1.66:5001`
- **Who can access**: Anyone on your WiFi/LAN network
- **Devices**: Phones, tablets, laptops on same network

### 2. Internet Access Options

#### Option A: ngrok (Easiest)
1. Download ngrok: https://ngrok.com/download
2. Install and setup account
3. Run: `ngrok http 5001`
4. Share the ngrok URL (e.g., `https://abc123.ngrok.io`)

#### Option B: Router Port Forwarding
1. Login to your router (usually 192.168.1.1)
2. Find "Port Forwarding" settings
3. Forward port 5001 to `192.168.1.66:5001`
4. Get your public IP from whatismyip.com
5. Share: `http://YOUR_PUBLIC_IP:5001`

## 🔒 Security Features
- ✅ Windows Firewall configured
- ✅ CORS enabled for cross-origin access
- ✅ Security headers added
- ✅ Non-debug mode for production

## 📱 Sharing Instructions

### For Local Network:
1. Make sure other devices are on the same WiFi
2. Give them this URL: `http://192.168.1.66:5001`
3. They can bookmark it for easy access

### For Internet Access:
1. Use ngrok or port forwarding (see options above)
2. Share the public URL
3. Works from anywhere in the world

## 🛠️ Advanced Options

### Production Deployment
For serious production use, consider:
- **Gunicorn/Waitress**: Better WSGI server
- **Nginx**: Reverse proxy and load balancing
- **SSL Certificate**: HTTPS encryption
- **Domain Name**: Custom domain instead of IP

### Cloud Deployment
- **Heroku**: Easy cloud deployment
- **AWS/Azure**: Full cloud infrastructure
- **DigitalOcean**: Simple VPS hosting

## 🔧 Troubleshooting

### Can't Access from Other Devices?
1. Check Windows Firewall (should be auto-configured)
2. Make sure devices are on same network
3. Try disabling Windows Firewall temporarily
4. Check router settings for device isolation

### Server Won't Start?
1. Make sure port 5001 isn't in use: `netstat -ano | findstr :5001`
2. Check all dependencies are installed: `pip install -r requirements.txt`
3. Run from correct directory

### Performance Issues?
1. Check your internet connection
2. Yahoo Finance API has rate limits
3. Consider caching market data

## 📊 Server Statistics
- **Server Type**: Flask Development Server
- **Host**: 0.0.0.0 (all interfaces)
- **Port**: 5001
- **Threading**: Enabled
- **Debug**: Disabled for production

## 🎯 Next Steps
1. Test access from another device on your network
2. Consider setting up ngrok for internet access
3. Add more security if exposing to internet
4. Monitor server logs for usage patterns

---
**Created**: July 30, 2025
**Your Server**: http://192.168.1.66:5001