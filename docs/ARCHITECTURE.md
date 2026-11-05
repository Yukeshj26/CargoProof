# Architecture

```text
React/Vite
  ├─ Supabase Auth (browser anon key)
  └─ FastAPI (Bearer access token)
       ├─ Auth validator → Supabase Auth /user
       ├─ Repository → Supabase PostgREST + private Storage
       │             ↳ persistent SQLite local fallback
       ├─ Quote calculator
       ├─ Evidence procurement agent
       │    ├─ provider registry (Strale / AISFleet / Synthora adapters)
       │    ├─ provider HTTP 402 → requirement validation
       │    ├─ official x402-avm HTTPX client → GoPlausible facilitator
       │    └─ paid retry → provider / settlement response
       ├─ deterministic 13-rule engine → PDF + SHA-256
       ├─ Base Sepolia customer receipt verifier
       └─ Algorand TestNet escrow contract/confirmed state
```

The agent uses deterministic capability selection, spending limits and state transitions. It does not need an LLM to decide whether to sign or release funds. An LLM may later be added for document extraction and human-readable explanations, but financial actions remain policy-gated.

## Data flow
1. Supabase-authenticated user creates a shipment and quotation.
2. Shipment and quotation are persisted in Supabase or local SQLite.
3. In live mode the backend requires a confirmed customer payment before procurement.
4. Agent identifies evidence capabilities from the shipment fields and rule requirements.
5. Provider adapters call only configured endpoints. A 402 response is parsed; exact Algorand x402 payment requirements are checked against network, ASA and budget. The optional sandbox route is protected by GoPlausible’s FastAPI middleware.
6. A dedicated server-side TestNet wallet signs through the official x402-avm HTTPX transport. The provider-side middleware uses the GoPlausible facilitator to verify and settle; the transport retries the resource request and reads the settlement response.
7. Evidence is accepted only when the provider response is valid; a paid request is only counted as settled when a successful payment response with transaction reference is returned.
8. Evidence is normalized and fingerprinted; the 13-rule engine returns PASS/FAIL/INSUFFICIENT per rule.
9. Report, rule results, evidence, agent job, provider payment receipts and audit events are persisted.
10. Escrow is a separate operator-authorized Algorand application. A release is reported only after a confirmed app-call transaction and on-chain state read.

## Storage modes
- Supabase: requires URL, anon key, service-role key. Service role is used only server-side; every read is additionally scoped by authenticated user ID.
- SQLite: durable local-only development fallback at `backend/data/cargoproof.db`; never used as an in-memory production store.
