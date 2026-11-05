import pytest
import asyncio
from app.pricing import quote
from app.verification.engine import verify
from app.demo import synthetic_evidence
from app.schemas import ShipmentInput
from app.agent.orchestrator import run_agent
from app.payments.x402 import decode_payment_required,select_requirement,X402Error
from app.config import settings

def fixture():
    inp=ShipmentInput(container_number='MSCU1234567',vessel_imo='9876543',origin_port='Chennai',destination_port='Singapore',cargo_description='General cargo')
    return inp,synthetic_evidence(inp)

def test_quote_is_transparent_and_marks_prices_illustrative():
    q=quote();assert q['markup_percent']==30;assert q['total_usd']>q['upstream_estimate_usd'];assert len(q['provider_costs'])>=3
    assert all(x['price_source']=='ILLUSTRATIVE_NOT_LIVE' for x in q['provider_costs'])

def test_all_thirteen_rules_present_and_clean_fixture_passes():
    inp,ev=fixture();result=verify(inp.model_dump(),ev)
    assert len(result['rules'])==13
    assert {r['result'] for r in result['rules']}=={'PASS'}
    assert result['decision']=='VERIFIED'
    assert len(result['evidence_hash'])==64
    assert result['evidence_classification']=='SYNTHETIC_TEST_CASE'

def test_vessel_container_mismatch_is_rejected():
    inp,ev=fixture();ev['container']['vessel_imo']='1111111'
    result=verify(inp.model_dump(),ev)
    assert result['decision']=='REJECTED'
    assert any(r['rule']=='VESSEL_CONTAINER_ASSOCIATION' and r['result']=='FAIL' for r in result['rules'])

def test_missing_evidence_is_insufficient_not_pass():
    inp=ShipmentInput(container_number='MSCU1234567')
    result=verify(inp.model_dump(),{'source_type':'SYNTHETIC_TEST_CASE'})
    assert result['decision']=='INSUFFICIENT_DATA'
    assert all(r['result']=='INSUFFICIENT' for r in result['rules'] if r['rule']!='SHIPMENT_EXISTS')

def test_stale_evidence_fails_freshness():
    inp,ev=fixture();ev['vessel']['last_updated']='2020-01-01T00:00:00+00:00';ev['vessel']['observed_at']='2020-01-01T00:00:00+00:00'
    for group in ('gps','port_events','documents'):
        for item in ev[group]:item['observed_at']='2020-01-01T00:00:00+00:00'
    result=verify(inp.model_dump(),ev)
    assert next(r for r in result['rules'] if r['rule']=='EVIDENCE_FRESHNESS')['result']=='FAIL'

def test_demo_agent_labels_synthetic_data_and_never_claims_payment(monkeypatch):
    monkeypatch.setattr(settings,'demo_mode',True)
    inp,ev=fixture();job=asyncio.run(run_agent(inp.model_dump(),'test-user',1.0))
    assert job['source_type']=='SYNTHETIC_TEST_CASE'
    assert job['spent_usd']==0
    assert 'no vendor or payment' in ' '.join(x['message'] for x in job['logs']).lower()

def test_x402_requirement_validation():
    import base64,json
    required={'x402Version':2,'accepts':[{'scheme':'exact','network':settings.x402_network,'payTo':'ALGO_ADDRESS','asset':'10458941','maxAmountRequired':'10000','extra':{'decimals':6}}]}
    header=base64.b64encode(json.dumps(required).encode()).decode()
    decoded=decode_payment_required(header)
    assert select_requirement(decoded,0.02)['payTo']=='ALGO_ADDRESS'
    try:select_requirement(decoded,0.001)
    except X402Error:pass
    else:raise AssertionError('budget overrun must be rejected')

def test_conflicting_provider_observations_trigger_hold():
    inp,ev=fixture()
    ev['provider_observations']=[{'provider':'other-provider','evidence':{'container':{'origin_port':'Mumbai','vessel_imo':'9876543'},'vessel':{'imo':'9876543','status':'UNDERWAY'}}}]
    result=verify(inp.model_dump(),ev)
    origin=next(r for r in result['rules'] if r['rule']=='ORIGIN_CONSISTENCY')
    assert origin['result']=='FAIL'
    assert result['decision']=='HOLD'

def test_gps_coordinates_alone_are_not_route_verification():
    inp,ev=fixture();ev['gps'][0].pop('route_consistency')
    result=verify(inp.model_dump(),ev)
    assert next(r for r in result['rules'] if r['rule']=='GPS_ROUTE_CONSISTENCY')['result']=='INSUFFICIENT'

def test_x402_disabled_never_signs_payment(monkeypatch):
    monkeypatch.setattr(settings,'x402_enabled',False)
    from app.payments.x402 import _signer
    try:_signer()
    except X402Error as exc:assert 'disabled' in str(exc).lower()
    else:raise AssertionError('x402 signing must remain disabled without explicit opt-in')

@pytest.mark.asyncio
async def test_live_mode_without_providers_never_uses_synthetic_success(monkeypatch):
    from app.agent.orchestrator import run_agent
    monkeypatch.setattr(settings,'demo_mode',False)
    monkeypatch.setattr('app.agent.orchestrator.PROVIDERS',{})
    job=await run_agent({'container_number':'MSCU1234567','origin_port':'Chennai'},'test-user',1.0)
    assert job['source_type']=='NO_EXTERNAL_EVIDENCE'
    assert job['evidence_records']==[]
    assert job['status']=='COMPLETED_WITH_INSUFFICIENT_EVIDENCE'

@pytest.mark.asyncio
async def test_live_multi_api_providers_retrieve_real_evidence(monkeypatch):
    from app.agent.orchestrator import run_agent
    monkeypatch.setattr(settings,'demo_mode',False)
    job=await run_agent({'container_number':'MSCU1234567','vessel_imo':'9876543','origin_port':'Chennai','destination_port':'Singapore','cargo_description':'Electronics and tea'},'test-user',1.0)
    assert job['source_type'] in ('LIVE_OBSERVATION', 'MIXED_LIVE_AND_SANDBOX')
    assert len(job['evidence_records'])>0
    assert job['status']=='COMPLETED'
    assert 'container' in job['evidence']
    assert 'vessel' in job['evidence']
    assert 'gps' in job['evidence']
    assert 'port_events' in job['evidence']
    assert 'inspection' in job['evidence']
    assert 'documents' in job['evidence']
    result=verify({'container_number':'MSCU1234567','vessel_imo':'9876543','origin_port':'Chennai','destination_port':'Singapore','cargo_description':'Electronics and tea'},job['evidence'])
    assert result['decision']=='VERIFIED'
    assert result['risk_score']==0
