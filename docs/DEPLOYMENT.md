# Deployment guide

## Supabase

1. Create the project and run `database/schema.sql` in the SQL Editor.
2. Configure Auth email/password and allowed redirect URLs.
3. Configure a private `cargoproof-documents` storage bucket (the schema creates it if missing).
4. Copy project URL + anon key to frontend environment; copy URL + anon + service-role key to backend environment.
5. Set `DEMO_MODE=false`, `STORAGE_MODE=auto` only after the schema and auth are verified.

## Backend (Render, Railway, or another Python ASGI host)

- Runtime: Python 3.11.
- Root directory: `backend`.
- Build command: `pip install -r requirements.txt`.
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Add all required values from `backend/.env.example` as encrypted environment variables.
- Set `FRONTEND_ORIGINS` to the deployed frontend origin(s), comma-separated.
- Configure Supabase persistence. Do not rely on a host's ephemeral local filesystem for SQLite in production.
- Do not enable provider payments until the dedicated Algorand TestNet wallet, x402 facilitator and provider test endpoints have been validated.

## Frontend (Vercel, Netlify, or another static host)

- Root directory: `frontend`.
- Build command: `npm run build`.
- Output directory: `dist`.
- Set `VITE_API_URL` to the deployed backend URL.
- Set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
- For Base Sepolia customer payments, set public `VITE_BASE_USDC_ADDRESS`, `VITE_BASE_TREASURY_ADDRESS` and `VITE_BASE_CHAIN_ID=84532`.
- Never set `SUPABASE_SERVICE_ROLE_KEY`, `X402_AVM_MNEMONIC`, `ALGORAND_VERIFIER_MNEMONIC`, or RPC credentials as `VITE_` variables.

## Go-live sequence

1. Deploy and validate Supabase auth + RLS.
2. Deploy backend and verify `/health`, `/docs`, file upload and PDF report.
3. Deploy frontend and validate allowed CORS origin.
4. Validate Base Sepolia payment with worthless test USDC only.
5. Deploy the Algorand escrow to TestNet, register the app ID and test funding/hold/release/refund with worthless TestNet ASA.
6. Configure one documented provider sandbox and validate non-payment responses.
7. Enable x402 only after the provider returns documented 402 requirements and GoPlausible verifies the dedicated TestNet payment group.
8. Keep `DEMO_MODE=false` only when live providers and customer payment settings are actually configured.

No production deployment, external account credentials or on-chain contract deployment is included in this ZIP.
