# Provider adapter contract

The project intentionally does not invent vendor API routes. Configure the exact base URL, documented endpoint path and API key for each vendor. The current HTTP adapter sends a GET request with query parameters:

- `resource_id`: container number, IMO, booking reference or shipment reference.
- `capability`: the evidence capability being requested.

Headers: `Accept: application/json`, `Authorization: Bearer <API_KEY>`.

A provider must return a JSON object. Preferred canonical response keys:

```json
{
  "observed_at": "2026-11-05T10:00:00Z",
  "container": {"container_number":"...","vessel_imo":"...","origin_port":"...","destination_port":"...","cargo_description":"..."},
  "vessel": {"imo":"...","name":"...","status":"UNDERWAY","last_updated":"..."},
  "port_events": [{"event_type":"DEPARTURE","port":"...","timestamp":"..."}],
  "gps": [{"lat":0.0,"lon":0.0,"timestamp":"...","observation_scope":"VESSEL_AIS"}],
  "inspection": {"result":"passed","observed_at":"..."},
  "documents": [{"container_number":"...","origin_port":"...","destination_port":"...","declared_cargo":"..."}]
}
```

Alternatively, typed responses are mapped according to capability: container tracking/validation → `container`; vessel identity/status → `vessel`; vessel position → `gps`; port calls/activity → `port_events`; inspection → `inspection`; shipping documents → `documents`.

Provider response timestamps and source identity are retained in `provider_observations` and evidence records. Do not mark data `LIVE_OBSERVATION` unless it was actually returned by the configured endpoint. A provider 402 is not evidence. A provider timeout, malformed response or non-2xx response is not replaced by a demo fixture.

The Strale/AISFleet/Synthora adapters are generic configurable HTTP adapters. Real account credentials, official endpoint paths, authentication variants and response schema compatibility must be supplied and tested with the provider.


## Paid sandbox provider

`cargoproof_test_provider` is an optional built-in synthetic provider. Enable it only with `DEMO_MODE=false`, `X402_ENABLED=true`, `X402_AVM_MNEMONIC`, `TEST_PROVIDER_ENABLED=true`, and a TestNet `TEST_PROVIDER_PAY_TO` address. The backend registers GoPlausible's official FastAPI `PaymentMiddlewareASGI` on `GET /api/test-provider/evidence`, using `HTTPFacilitatorClient` and `ExactAvmServerScheme`. The provider returns clearly synthetic, capability-specific evidence only after facilitator settlement. It is useful for testing the actual x402 client/middleware/facilitator round trip, but it is never a source of real shipment observations.
