# ScraperPro — Universal Product Scraper

Jumia-themed web app. Backend on Render, Frontend on Netlify.

## Project Structure
```
scraper-app/
├── backend/
│   ├── main.py              ← FastAPI backend
│   ├── product_scraper.py   ← Scraping logic (Amazon, Noon, GSMArena, Generic)
│   ├── BOBTemplate.csv      ← Jumia BOB template
│   ├── VendorCenterTemplate.xlsx
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.js           ← Full React UI
│   │   └── index.js
│   ├── public/index.html
│   └── package.json
├── render.yaml              ← Render deployment config
└── netlify.toml             ← Netlify deployment config
```

## Deploy Backend → Render

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Settings:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: Free
5. Click **Create Web Service**
6. Note your URL: `https://your-service.onrender.com`

## Deploy Frontend → Netlify

1. Go to [netlify.com](https://netlify.com) → Add new site → Import from Git
2. Connect your GitHub repo
3. Settings:
   - **Base directory**: `frontend`
   - **Build command**: `npm run build`
   - **Publish directory**: `frontend/build`
4. Add Environment Variable:
   - Key: `REACT_APP_API_URL`
   - Value: `https://your-service.onrender.com` ← your Render URL
5. Click **Deploy site**

## Local Development

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm install
REACT_APP_API_URL=http://localhost:8000 npm start
```

## Features
- Single URL scrape → immediate download
- Batch URL scrape (paste list) → background job with live progress
- File upload (CSV/Excel with URL column) → background job
- Export to: **BOBTemplate CSV**, **VendorCenter XLSX**, or **Raw CSV**
- Supports: Amazon, Noon, GSMArena, any website
