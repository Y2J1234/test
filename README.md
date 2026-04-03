# 📊 Finviz Market Dashboard — Public Web App

A live stock market dashboard showing top daily gainers, market breadth, futures, and chart patterns from Finviz.

**No login required — anyone with the link can access it!**

## Filters
- ✅ Stock price > $1 (no penny stocks)
- ✅ Weekly performance > 0% (positive momentum only)
- ✅ Sorted by volume, top 30 shown

## 🚀 Quick Start (Local)

```bash
pip install -r requirements.txt
python server.py
```
Open http://localhost:5000

## ☁️ Deploy Free (Choose One)

### Option 1: Render.com (Recommended — Free Tier)
1. Go to https://render.com → Sign up free
2. New → Web Service → Connect your GitHub repo (or upload)
3. Settings:
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 60 server:app`
4. Click Deploy → Get a public URL like `https://your-app.onrender.com`

### Option 2: Railway.app
1. Go to https://railway.app → Sign up
2. New Project → Deploy from GitHub
3. It auto-detects the Dockerfile
4. Get a public URL

### Option 3: Fly.io
```bash
flyctl launch
flyctl deploy
```

### Option 4: Docker (Any VPS)
```bash
docker build -t finviz-dashboard .
docker run -p 5000:5000 finviz-dashboard
```

## Features
- 🔄 Refresh button for live data
- ⏰ Auto-refreshes every 5 minutes
- 📊 Sortable columns (click headers)
- 📐 Chart patterns tab
- 🌍 Futures overview
- 📈 Market breadth indicators
- 📱 Mobile responsive
