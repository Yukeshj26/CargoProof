# Security controls and deployment caveats

- Supabase anon key may be used in the frontend; Supabase service-role key and all mnemonics are backend-only.
- Backend validates Supabase access tokens using Supabase Auth `/user` when URL + anon key are configured.
- Every data query is scoped by authenticated `user_id`. Supabase RLS is enabled on tenant tables; service-role use bypasses RLS, so backend scoping must remain intact.
- Local demo login is only enabled when Supabase is not configured and `DEMO_MODE=true`.
- Document upload accepts PDF/PNG/JPEG only, checks MIME magic bytes and limits files to 15 MB. Supabase bucket is private; local files are stored outside public static paths.
- Payment verification checks Base chain, token contract, sender, treasury recipient, exact amount and transaction uniqueness.
- x402 requires exact Algorand TestNet network/ASA matching, a per-job budget, daily spend cap, GoPlausible facilitator pre-verification and provider settlement receipt before confirmed spend is recorded.
- Algorand escrow state transitions require an admin role and a server-side verifier mnemonic. API release status is read from confirmed chain state.
- Process-local rate limit is a lightweight single-process guard, not a distributed production limiter.
- TestNet contract is unaudited. Do not use real assets. Production requires external security review, key management/HSM, monitoring, shared rate limiting, idempotency reconciliation, contract audit and provider due diligence.
