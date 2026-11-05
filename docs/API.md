# API Reference

Interactive OpenAPI: `http://localhost:8000/docs`.

All `/api/*` endpoints require Supabase Bearer access token when Supabase is configured. With no Supabase configured and `DEMO_MODE=true`, a local demo user is used.

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Runtime mode and integration readiness |
| GET | `/api/me` | Current authenticated user |
| GET | `/api/dashboard` | Report counts and recent reports |
| POST | `/api/shipments` | Register shipment |
| GET | `/api/shipments/{shipment_id}` | Read owned shipment |
| POST | `/api/shipments/{shipment_id}/documents` | Upload private PDF/PNG/JPEG (15 MB max) |
| GET | `/api/documents/{document_id}/download` | Download owned document / get temporary signed URL |
| POST | `/api/quotes` | Persist shipment and create estimate |
| GET | `/api/quotes/{quote_id}` | Read owned quote |
| POST | `/api/agent/run/{quote_id}?budget_usd=1.00` | Run evidence procurement agent |
| POST | `/api/verify/{quote_id}?budget_usd=1.00` | Run agent then verification; returns report |
| GET | `/api/history` | Owned verification reports |
| GET | `/api/reports/{report_id}` | Owned report |
| GET | `/api/reports/{report_id}/integrity` | Recompute SHA-256 evidence fingerprint |
| GET | `/api/reports/{report_id}/pdf` | PDF export |
| POST | `/api/payments/verify` | Verify Base Sepolia USDC receipt |
| GET | `/api/providers` | Provider readiness |
| GET | `/api/test-provider/evidence` | Optional x402-gated synthetic sandbox evidence |
| GET | `/api/escrow/status` | Escrow configuration |
| GET | `/api/escrow/records` | List owned registered escrow records |
| POST | `/api/escrow/register` | Admin verifies/registers a deployed app |
| GET | `/api/escrow/{app_id}` | Read deployed app global state |
| POST | `/api/escrow/{app_id}/actions/{hold|release|refund}` | Admin-only on-chain state transition |
| GET | `/api/admin/summary` | Admin-only operational summary |

`POST /api/quotes` JSON body fields: `container_number` (required), `vessel_imo`, `booking_number`, `bill_of_lading`, `origin_port`, `destination_port`, `cargo_description`, `expected_departure`, `expected_arrival`, `declared_cargo_value_usd`, `beneficiary_address`, `claimed_status`.

## Decisions
- `VERIFIED`: all mandatory evidence checks pass.
- `HOLD`: non-critical contradictions/failures require review.
- `REJECTED`: a critical contradiction/failure exists.
- `INSUFFICIENT_DATA`: required evidence is missing/inconclusive and no critical failure already determines the outcome.

Each rule returns `PASS`, `FAIL`, or `INSUFFICIENT`. The risk score is a weighted rule-severity index, not a calibrated probability.
