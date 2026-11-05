# CargoProof AI — Complete Integrated Build

**Verify shipment evidence before trusting the trade.**

CargoProof is a React/Vite + FastAPI application for shipment intake, quotations, evidence procurement, deterministic verification, evidence provenance, customer payment verification, x402 provider purchases and Algorand TestNet escrow operations.

## 1. Current implementation modes

- **Demo mode (`DEMO_MODE=true`)**: runs an end-to-end local workflow using a clearly labelled `SYNTHETIC_TEST_CASE` fixture. It does not call vendors, send payments or deploy blockchain contracts.
- **Live provider mode (`LIVE_PROVIDER_MODE=true`)**: calls only configured provider base URLs and operator-supplied documented endpoint paths. No Strale/AISFleet/Synthora API path is assumed by the code. If a provider is not configured or returns an error, CargoProof does not substitute synthetic success.
- **Documents**: private PDF/PNG/JPEG uploads are SHA-256 fingerprinted. Text-based PDFs are extracted with pypdf for basic shipment-field matching; image OCR is not configured.
- **Supabase mode**: when `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are configured and `STORAGE_MODE=auto`, backend records use Supabase PostgREST and private Supabase Storage. If not configured, local development uses persistent SQLite under `backend/data/cargoproof.db`.
- **x402**: uses GoPlausible’s official `x402-avm` HTTPX client, with TestNet exact-scheme requirement checks, budget/ASA validation, backend-only signing, automatic paid retry and settlement-receipt validation. It is disabled until explicitly configured.
- **Customer payments**: Base Sepolia USDC transaction receipt verification is separate from x402 provider purchases.
- **Escrow**: Algorand TestNet ASA escrow is separate from customer payments and x402 provider purchases. Contract deployment is an operator action; the application only reports confirmed on-chain state/actions.

## 2. Windows 11 quick start (PowerShell)

Install Python 3.11 and Node.js 20+ first. Extract the ZIP and open PowerShell in the `CargoProof-AI` project root.

```powershell
# Create and activate Python environment
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install backend dependencies
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt

# Create local environment files
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env

# Install frontend packages
cd frontend
npm install
cd ..
```

Edit `backend/.env` and `frontend/.env` as described below. For a local synthetic demo, you can leave Supabase/provider/blockchain/payment credentials blank and keep `DEMO_MODE=true`.

Start the backend in PowerShell window 1:

```powershell
cd backend
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Start the frontend in PowerShell window 2:

```powershell
cd frontend
npm run dev
```

Open:
- Frontend: http://localhost:5173
- API health: http://localhost:8000/health
- Swagger API docs: http://localhost:8000/docs

Alternatively, from the project root use `.\scripts\run-backend.ps1` and `.\scripts\run-frontend.ps1` in separate PowerShell windows after setup.

## 3. Supabase configuration

1. Create a Supabase project.
2. Open **SQL Editor** and run `database/schema.sql`.
3. In `frontend/.env`, set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.
4. In `backend/.env`, set `SUPABASE_URL`, `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_ROLE_KEY`.
5. Keep the service-role key only in `backend/.env`. Never copy it into the frontend.
6. Set `DEMO_MODE=false` and `STORAGE_MODE=auto` only after auth/database setup is complete.
7. Enable email/password in Supabase Auth and configure redirect URLs for `http://localhost:5173`.

The backend validates Supabase access tokens through the Supabase Auth `/user` endpoint and applies the authenticated user ID to every record query. The service-role key is server-only; because it bypasses RLS, the backend's ownership filters are mandatory. RLS policies in the SQL schema provide an additional client-side tenant boundary.

## 4. Provider configuration

Provider documentation and credentials must come from your actual provider account or contract. Do not guess API paths. Set:

- `LIVE_PROVIDER_MODE=true`
- `STRALE_API_BASE`, `STRALE_ENDPOINT`, `STRALE_API_KEY`
- `AISFLEET_API_BASE`, `AISFLEET_ENDPOINT`, `AISFLEET_API_KEY`
- `SYNTHORA_API_BASE`, `SYNTHORA_ENDPOINT`, `SYNTHORA_API_KEY`

Each endpoint is called as a GET request with `resource_id` and `capability` query parameters. Configure the exact endpoint and authentication scheme expected by your provider. The current adapters use Bearer authentication; providers requiring another auth method need a provider-specific adapter change. Provider responses must be JSON objects. The normalized evidence response shapes are described in `docs/PROVIDERS.md`.

## 5. x402 provider payments (GoPlausible / Algorand TestNet)

The implementation uses GoPlausible's official [x402-avm Python SDK](https://pypi.org/project/x402-avm/) and the Algorand AVM exact payment flow documented in the [GoPlausible integration guide](https://github.com/GoPlausible/.github/blob/main/profile/algorand-x402-documentation/python/x402-avm-httpx-examples-python.md). The official `x402-avm` HTTPX transport parses the provider's HTTP 402 `PAYMENT-REQUIRED` response, signs and retries using the x402 V2 payment header, and reads the `PAYMENT-RESPONSE` settlement receipt. Providers must return the x402 V2 `PAYMENT-REQUIRED` header; legacy 402 formats are not treated as payable.

Configure in `backend/.env`:

```dotenv
X402_ENABLED=true
X402_FACILITATOR_URL=https://facilitator.goplausible.xyz
X402_NETWORK=algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI=
X402_ASSET_ID=10458941
X402_AVM_MNEMONIC=YOUR_DEDICATED_TESTNET_AGENT_WALLET_MNEMONIC
TEST_PROVIDER_ENABLED=true
TEST_PROVIDER_PAY_TO=YOUR_TESTNET_USDC_RECEIVER_ADDRESS
TEST_PROVIDER_PRICE_USD=0.01
ALGORAND_NETWORK=testnet
ALGORAND_ALGOD_URL=https://testnet-api.algonode.cloud
```

Fund the dedicated agent wallet with TestNet USDC ASA `10458941` and enough ALGO for fees if the provider's requirements do not include a facilitator fee payer. Use a dedicated low-balance TestNet wallet; never reuse a personal/mainnet seed. The agent rejects unsupported networks/assets, malformed requirements and payments above the remaining per-job budget. The official SDK performs the facilitator verification/settlement handshake and retries the resource request. CargoProof checks the advertised TestNet network, ASA, amount and remaining budget before allowing that SDK retry, then records provider spend only after a successful settlement response with a transaction reference.

A provider must be x402-compatible and its own settlement middleware must accept the selected header version. An optional CargoProof sandbox provider is included: it uses GoPlausible's official FastAPI x402 middleware and facilitator to gate clearly synthetic evidence behind a real TestNet USDC payment. The integration uses GoPlausible's official `x402-avm` Python HTTPX client and TestNet scheme registration. For an end-to-end paid sandbox test, set `DEMO_MODE=false`, configure Supabase Auth, enable `TEST_PROVIDER_ENABLED`, set `TEST_PROVIDER_PAY_TO` to a receiver opted into TestNet USDC ASA `10458941`, and use a funded dedicated TestNet agent wallet. The local default provider URL is `http://127.0.0.1:8000`; set `TEST_PROVIDER_BASE_URL` to the backend's reachable URL if needed. Sandbox evidence is always labelled `SANDBOX_PROVIDER_DATA`; it must never be presented as live cargo evidence. The flow has not been exercised against a funded wallet in this environment.

## 6. Base Sepolia customer payment verification

Set `LIVE_PAYMENTS_ENABLED=true` only when all values are correct:

```dotenv
BASE_CHAIN_ID=84532
BASE_RPC_URL=YOUR_BASE_SEPOLIA_RPC_URL
BASE_USDC_ADDRESS=THE_VERIFIED_BASE_SEPOLIA_USDC_CONTRACT
CARGOPROOF_TREASURY_ADDRESS=YOUR_TREASURY_ADDRESS
MAX_PAYMENT_USD=25
```

The API checks the confirmed transaction receipt, chain ID, USDC contract, Transfer event sender, treasury recipient and exact quoted USDC amount (6 decimals). The payer submits a transaction hash and wallet address; the backend does not custody customer keys. A verified customer payment is stored separately from provider payment records. Never use a mainnet token address in TestNet configuration.

## 7. Algorand escrow TestNet deployment

The PyTeal reference contract is in `contracts/algorand/cargoproof_escrow_reference.py`; the deployment/interaction CLI is `contracts/algorand/scripts/escrow_cli.py`. Set `ALGORAND_VERIFIER_MNEMONIC` only in `backend/.env` and configure `ALGORAND_USDC_ASSET_ID=10458941` for the documented TestNet USDC ASA.

From the project root after installing backend requirements:

```powershell
# Deploy an escrow app; save the printed APP_ID
.\.venv\Scripts\python.exe contracts/algorand/scripts/escrow_cli.py deploy --beneficiary BENEFICIARY_ALGORAND_ADDRESS

# Fund the app account with 0.2 ALGO for its ASA opt-in minimum balance (microAlgo)
.\.venv\Scripts\python.exe contracts/algorand/scripts/escrow_cli.py fund-algo --app-id APP_ID --amount 200000

# Opt the app account into the USDC ASA
.\.venv\Scripts\python.exe contracts/algorand/scripts/escrow_cli.py optin --app-id APP_ID

# Transfer 1 USDC (1,000,000 base units) into the app address
.\.venv\Scripts\python.exe contracts/algorand/scripts/escrow_cli.py fund --app-id APP_ID --amount 1000000

# Record the evidence hash and the amount eligible for release
.\.venv\Scripts\python.exe contracts/algorand/scripts/escrow_cli.py evidence --app-id APP_ID --sha256 YOUR_64_HEX_SHA256 --amount 1000000

# Authorized verifier releases to the beneficiary
.\.venv\Scripts\python.exe contracts/algorand/scripts/escrow_cli.py release --app-id APP_ID --beneficiary BENEFICIARY_ALGORAND_ADDRESS

# Inspect on-chain global state
.\.venv\Scripts\python.exe contracts/algorand/scripts/escrow_cli.py hold --app-id APP_ID
.\.venv\Scripts\python.exe contracts/algorand/scripts/escrow_cli.py refund --app-id APP_ID --asset 10458941  # only depositor, after expiry
.\.venv\Scripts\python.exe contracts/algorand/scripts/escrow_cli.py status --app-id APP_ID
```

`hold` is available to the verifier; `refund` is available to the recorded depositor after expiry while the escrow is pending, verified or held. App calls that submit inner transactions use a 2,000 microAlgo fee budget. The API's `/api/escrow/{app_id}` reads confirmed state; `/api/escrow/{app_id}/actions/{hold|release|refund}` is restricted to a trusted admin and reports success only after confirmation. Configure `ALGORAND_APP_ID` and the backend verifier mnemonic before enabling API actions.

**TestNet only.** This is a hackathon reference contract, not an audited escrow product. Do not use real funds.

## 8. Tests and frontend build

Backend tests:

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

Frontend production build:

```powershell
cd frontend
npm run build
```

Or from project root use `scripts/test-backend.ps1` and `scripts/build-frontend.ps1`.

## 9. API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Runtime modes and integration readiness |
| GET | `/api/me` | Authenticated user |
| GET | `/api/dashboard` | User report statistics |
| POST | `/api/shipments` | Register shipment |
| GET | `/api/shipments/{id}` | Retrieve owned shipment |
| POST | `/api/shipments/{id}/documents` | Upload private PDF/PNG/JPEG |
| GET | `/api/documents/{id}/download` | Private download / signed URL |
| POST | `/api/quotes` | Create shipment + itemized estimate |
| GET | `/api/quotes/{id}` | Retrieve owned quote |
| POST | `/api/agent/run/{quote_id}` | Run procurement agent (live mode requires customer payment) |
| POST | `/api/verify/{quote_id}` | Procurement + 13-rule report |
| GET | `/api/history` | Owned report history |
| GET | `/api/reports/{id}` | Owned report details |
| GET | `/api/reports/{id}/integrity` | Recompute SHA-256 evidence fingerprint |
| GET | `/api/reports/{id}/pdf` | Download PDF |
| POST | `/api/payments/verify` | Verify Base Sepolia customer USDC transfer |
| GET | `/api/providers` | Provider registry status |
| GET | `/api/test-provider/evidence` | Optional x402-gated synthetic sandbox evidence (TestNet only) |
| GET | `/api/escrow/status` | Algorand configuration |
| GET | `/api/escrow/records` | Owned registered escrow records |
| POST | `/api/escrow/register` | Admin verifies/registers a deployed app |
| GET | `/api/escrow/{app_id}` | Read on-chain escrow state |
| POST | `/api/escrow/{app_id}/actions/{action}` | Admin-only hold/release/refund |
| GET | `/api/admin/summary` | Admin-only operational summary |

## 10. Verification decisions

Each of the 13 checks returns `PASS`, `FAIL` or `INSUFFICIENT`. Missing evidence never becomes a pass. Critical failures produce `REJECTED`; non-critical failures produce `HOLD`; unresolved required evidence produces `INSUFFICIENT_DATA`; all checks must pass for `VERIFIED`. The 0–100 risk index is a severity-weighted rule score, not a statistically calibrated probability.

## 11. Security and production caveats

- All signing mnemonics, Supabase service-role keys and RPC credentials are backend-only.
- Demo login is only for local demo mode; configure Supabase Auth for real users.
- Local SQLite is persistent for development but not a horizontally-scalable production database.
- The included process-local rate limiter is a basic development guard; use a shared gateway/Redis limiter in production.
- Provider capabilities and paths are not verified until real vendor documentation/credentials are supplied.
- The Algorand contract requires independent audit and additional operational controls before production.
- x402 payments, Base customer receipts and escrow are distinct transactions and are never treated as interchangeable.


## Firebase Google Authentication

CargoProof uses Firebase Authentication for email/password and Google sign-in. Configure the `VITE_FIREBASE_*` variables from your Firebase Web App in `frontend/.env`. In Firebase Console, enable **Authentication → Sign-in method → Google** and **Email/Password**. Add your deployed frontend domain under **Authentication → Settings → Authorized domains**.

The backend verifies Firebase ID tokens with Firebase Admin SDK. Create a Firebase service account in Project settings → Service accounts, store its JSON securely outside the repository, install backend requirements, and set `GOOGLE_APPLICATION_CREDENTIALS` to that file path plus `FIREBASE_PROJECT_ID=cargoproof-ccb53`. Never commit the service-account JSON.

Email/password registration sends a verification email and signs the user out; they must verify and then sign in. Firebase Google sign-in automatically creates a Firebase account on a user's first successful Google sign-in; subsequent Google sign-ins authenticate that existing account. Supabase may remain configured for PostgreSQL storage, but it is no longer used for authentication. Existing Supabase user IDs and user-owned records are not automatically migrated to Firebase UIDs.
