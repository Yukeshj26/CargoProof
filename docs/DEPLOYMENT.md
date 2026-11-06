# CargoProof AI — Deployment Guide

This guide covers deploying CargoProof AI to **Render** ([render.com](https://render.com)) using either the automated Blueprint Infrastructure-as-Code specification or manual service creation, as well as production database and Web3 configurations.

---

## Method 1: 1-Click Automated Render Blueprint (Recommended)

The repository includes a ready-to-use [`render.yaml`](../render.yaml) blueprint specification that automatically provisions both the **FastAPI Web Service** and **React Static Site** with inter-service networking, SPA client rewrites, and environment variables pre-configured.

### Steps:
1. Push your repository to GitHub: `https://github.com/Yukeshj26/CargoProof`
2. Log into your [Render Dashboard](https://dashboard.render.com).
3. In the top navigation, click **New +** and select **Blueprint**.
4. Connect your GitHub account and select the **`Yukeshj26/CargoProof`** repository.
5. Render will detect `render.yaml` and display the blueprint plan:
   - **`cargoproof-api`** (Python 3.11 Web Service — Free tier)
   - **`cargoproof-web`** (Static Site with SPA route rewrites — Free tier)
6. Click **Apply**.
7. Render will build and deploy both services simultaneously:
   - Backend live URL: `https://cargoproof-api.onrender.com`
   - Frontend live URL: `https://cargoproof-web.onrender.com`

---

## Method 2: Manual Setup on Render Dashboard

If you prefer to configure the services manually on Render:

### 1. Backend Web Service (`cargoproof-api`)

1. In Render Dashboard, click **New +** $\to$ **Web Service**.
2. Select your repository `Yukeshj26/CargoProof`.
3. Configure the following fields:
   - **Name**: `cargoproof-api`
   - **Region**: Choose closest to your users (e.g. `Oregon (US West)` or `Frankfurt (EU)`)
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Runtime**: `Python`
   - **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Plan**: `Free`
4. Expand **Advanced** $\to$ **Add Environment Variable**:
   | Key | Value | Description |
   | :--- | :--- | :--- |
   | `PYTHON_VERSION` | `3.11.9` | Enforces Python 3.11 runtime |
   | `APP_ENV` | `production` | Production environment |
   | `DEMO_MODE` | `true` | Enables instant test presets & sandbox |
   | `STORAGE_MODE` | `sqlite` | Durable local SQLite (or `auto` for Supabase) |
   | `SQLITE_PATH` | `data/cargoproof.db` | Database file path |
   | `FRONTEND_ORIGINS` | `https://cargoproof-web.onrender.com,http://localhost:5173` | Allowed CORS origins |
   | `LIVE_PAYMENTS_ENABLED` | `true` | Enables Base Sepolia USDC payment verification |
   | `BASE_CHAIN_ID` | `84532` | Base Sepolia chain ID |
   | `BASE_RPC_URL` | `https://sepolia.base.org` | Public Base Sepolia RPC endpoint |
   | `BASE_USDC_ADDRESS` | `0x036CbD53842c5426634e7929541eC2318f3dCF7e` | Official Base Sepolia USDC contract |
   | `CARGOPROOF_TREASURY_ADDRESS` | `0x742d35Cc6634C0532925a3b844Bc454e4438f44e` | Receiving treasury wallet |
   | `FIREBASE_PROJECT_ID` | `cargoproof-ccb53` | Firebase project ID |
5. Click **Create Web Service**.
6. Note the generated public URL (e.g. `https://cargoproof-api.onrender.com`). Verify by visiting `/health` in your browser.

---

### 2. Frontend Static Site (`cargoproof-web`)

1. In Render Dashboard, click **New +** $\to$ **Static Site**.
2. Select your repository `Yukeshj26/CargoProof`.
3. Configure the following fields:
   - **Name**: `cargoproof-web`
   - **Branch**: `main`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`
4. Expand **Advanced** $\to$ **Add Environment Variable**:
   | Key | Value |
   | :--- | :--- |
   | `NODE_VERSION` | `20.18.0` |
   | `VITE_API_URL` | `https://cargoproof-api.onrender.com` *(Replace with your actual backend URL)* |
   | `VITE_BASE_CHAIN_ID` | `84532` |
   | `VITE_BASE_USDC_ADDRESS` | `0x036CbD53842c5426634e7929541eC2318f3dCF7e` |
   | `VITE_BASE_TREASURY_ADDRESS` | `0x742d35Cc6634C0532925a3b844Bc454e4438f44e` |
   | `VITE_FIREBASE_API_KEY` | `AIzaSyAjlrWX9COIgdabdcTXh0KZoO7-Gcw48_g` |
   | `VITE_FIREBASE_AUTH_DOMAIN` | `cargoproof-ccb53.firebaseapp.com` |
   | `VITE_FIREBASE_PROJECT_ID` | `cargoproof-ccb53` |
   | `VITE_FIREBASE_STORAGE_BUCKET` | `cargoproof-ccb53.firebasestorage.app` |
   | `VITE_FIREBASE_MESSAGING_SENDER_ID` | `745884671758` |
   | `VITE_FIREBASE_APP_ID` | `1:745884671758:web:7b7bc502554f870b55015f` |
   | `VITE_FIREBASE_MEASUREMENT_ID` | `G-CTWJMJQCZ5` |
5. **Critical for React Router (SPA)**:
   - Navigate to the **Redirects/Rewrites** tab in your Static Site settings.
   - Click **Add Rule**:
     - **Type**: `Rewrite`
     - **Source**: `/*`
     - **Destination**: `/index.html`
   - Save the rule. This prevents 404 errors when refreshing `/verify`, `/wallet`, or `/report/:id`.
6. Click **Create Static Site**.

---

## 3. Post-Deployment Verification Checklist

1. **Backend Health**:
   - Open `https://<your-backend>.onrender.com/health`
   - Expected response: `{"status":"ok","app":"CargoProof AI","demo_mode":true,...}`
2. **Interactive API Docs**:
   - Open `https://<your-backend>.onrender.com/docs`
   - Confirm Swagger UI loads all endpoints.
3. **Frontend Application**:
   - Open `https://<your-frontend>.onrender.com`
   - Click **Explore Demo Workspace (1-Click Access)**.
   - Run a verification using one of the 4 maritime presets (**MS FINNTIDE**, **MS FINNMAID**, **MSC OSCAR**, **EVER GIVEN**).
   - Test PDF report generation and MetaMask connection on Base Sepolia.
4. **CORS Verification**:
   - Backend automatically allows any `https://*.onrender.com` origin as well as localhost.
