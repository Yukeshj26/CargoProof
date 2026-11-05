"""Budget-bounded evidence procurement orchestration.
Financial actions are never inferred from LLM output; this engine uses explicit policies.
"""
from datetime import datetime,timezone
from uuid import uuid4
import hashlib,json,math
from ..config import settings
from ..demo import synthetic_evidence
from ..providers.registry import PROVIDERS
from ..payments.x402 import X402ReconciliationRequired

CAPABILITY_COST={'container_tracking':0.054,'container_validation':0.054,'container_vessel_association':0.054,'vessel_position':0.010,'vessel_identity':0.010,'vessel_status':0.010,'port_calls':0.020,'port_activity':0.020,'port_anomalies':0.020,'inspection':0.030,'shipping_documents':0.030}
REQUIREMENTS={
 'container':['container_tracking','container_validation'], 'vessel':['vessel_identity','vessel_position','vessel_status'],
 'ports':['port_calls','port_activity'], 'inspection':['inspection'], 'documents':['shipping_documents']}

def _merge_evidence(base, incoming, provider=None, retrieved_at=None, source_type='LIVE_OBSERVATION'):
    """Merge known evidence collections; do not allow a provider to overwrite provenance."""
    if provider:base.setdefault('provider_observations',[]).append({'provider':provider,'retrieved_at':retrieved_at,'source_type':source_type,'evidence':incoming})
    for key in ('shipment','container','vessel','inspection'):
        if isinstance(incoming.get(key),dict):
            if not isinstance(base.get(key),dict):base[key]={}
            base[key].update(incoming[key])
    for key in ('port_events','gps','documents'):
        if isinstance(incoming.get(key),list):base.setdefault(key,[]).extend(incoming[key])

def _extract_payload(result):
    payload=result.get('evidence') or {}
    if not isinstance(payload,dict):return {}
    # Provider payload can either be a canonical evidence object or a typed single-source response.
    if any(k in payload for k in ('shipment','container','vessel','port_events','gps','inspection','documents')):return payload
    kind=result.get('capability')
    if kind in ('container_tracking','container_validation','container_vessel_association'):return {'container':payload}
    if kind in ('vessel_identity','vessel_position','vessel_status'):return {'vessel':payload} if kind!='vessel_position' else {'gps':[payload]}
    if kind in ('port_calls','port_activity','port_anomalies'):return {'port_events':payload.get('events',payload.get('port_events',[]))}
    if kind=='inspection':return {'inspection':payload}
    if kind=='shipping_documents':return {'documents':payload.get('documents',[payload])}
    return {}

async def run_agent(shipment,user_id,budget_usd=None):
    budget=float(budget_usd if budget_usd is not None else settings.max_agent_budget_usd)
    if not math.isfinite(budget) or budget<0 or budget>settings.max_agent_budget_usd:raise ValueError(f'Budget must be between $0 and ${settings.max_agent_budget_usd:.2f}')
    job={'id':str(uuid4()),'user_id':user_id,'status':'RUNNING','budget_usd':round(budget,6),'spent_usd':0.0,'estimated_cost_usd':0.0,'started_at':datetime.now(timezone.utc).isoformat(),'logs':[],'evidence_records':[],'payment_records':[],'providers':[],'payment_status':'NOT_REQUIRED_OR_NOT_CONFIGURED'}
    log=lambda message,kind='INFO':job['logs'].append({'at':datetime.now(timezone.utc).isoformat(),'level':kind,'message':message})
    evidence={'source_type':'SYNTHETIC_TEST_CASE' if settings.demo_mode else 'LIVE_OBSERVATION','shipment':{**shipment,'claimed_status':'IN_TRANSIT'}}
    # Determine requested evidence dynamically from missing fields/rule requirements.
    required=[]
    if shipment.get('container_number'):required += ['container_tracking','container_validation','container_vessel_association']
    if shipment.get('container_number') or shipment.get('vessel_imo'):required += ['vessel_identity','vessel_position','vessel_status']
    if shipment.get('origin_port') or shipment.get('destination_port'):required += ['port_calls','port_activity']
    required += ['inspection','shipping_documents']
    log(f'Analyzed shipment claims; evidence capabilities required: {", ".join(dict.fromkeys(required))}.')
    providers=[]
    x402_item=None
    for provider in PROVIDERS.values():
        if not provider.enabled:
            continue
        if provider.name == 'cargoproof_test_provider':
            if settings.x402_enabled:
                x402_item = (provider, ['container_validation'])
        else:
            overlap = [cap for cap in provider.capabilities if cap in required]
            if overlap:
                providers.append((provider, overlap))
    if x402_item:
        providers.insert(0, x402_item)
    requests=0;stop_procurement=False
    if settings.demo_mode:
        # The local fixture is visibly synthetic and never masquerades as a vendor.
        evidence=synthetic_evidence(type('Shipment',(),shipment)())
        job['source_type']='SYNTHETIC_TEST_CASE'; log('DEMO MODE: using explicitly labelled synthetic fixture; no vendor or payment was contacted.','WARNING')
    else:
        job['source_type']='LIVE_OBSERVATION'
        for provider,caps in providers:
            if stop_procurement:break
            for capability in caps:
                if stop_procurement:break
                if requests>=settings.max_agent_requests:log('Maximum evidence request count reached.','WARNING');break
                cost=CAPABILITY_COST.get(capability,0.02)
                if job['estimated_cost_usd']+cost>budget:log(f'Budget limit reached before {provider.name}/{capability}.','WARNING');break
                requests+=1; log(f'Requesting {capability} from {provider.name}.')
                paid_this_request=False
                idempotency_key=hashlib.sha256(f'{user_id}|{shipment.get("container_number")}|{provider.name}|{capability}'.encode()).hexdigest()
                provider_context={k:shipment[k] for k in ('origin_port','destination_port','vessel_imo','cargo_description','container_number') if shipment.get(k)}
                result=await provider.fetch(shipment.get('container_number') or shipment.get('vessel_imo') or shipment.get('booking_number') or 'shipment',capability=capability,_idempotency_key=idempotency_key,**provider_context)
                job['providers'].append({'provider':provider.name,'capability':capability,'status':result.get('status'),'http_status':result.get('http_status')})
                if result.get('status')=='PAYMENT_REQUIRED_UNSUPPORTED':
                    job['payment_status']='PAYMENT_FAILED';log(f'{provider.name} returned HTTP 402 without the x402 V2 PAYMENT-REQUIRED header; payment was not attempted.','WARNING');continue
                if result.get('status')=='PAYMENT_REQUIRED':
                    job['payment_status']='PAYMENT_REQUIRED_NOT_SETTLED'
                    try:
                        from ..payments.x402 import decode_payment_required,select_requirement,check_wallet_balance
                        required_payment=decode_payment_required(result.get('payment_required'))
                        selected=select_requirement(required_payment,max(0,budget-job['estimated_cost_usd']))
                        check_wallet_balance(selected)
                        paid=await provider.fetch_with_x402(shipment.get('container_number') or shipment.get('vessel_imo') or shipment.get('booking_number') or 'shipment',capability,idempotency_key,**provider_context)
                        receipt=paid.get('settlement') or {}
                        if receipt.get('status')!='CONFIRMED' or not receipt.get('tx_id'):raise RuntimeError('x402 SDK did not return a confirmed settlement transaction')
                        amount_usd=int(selected['amount'])/(10**int((selected.get('extra') or {}).get('decimals',6)))
                        job['spent_usd']=round(job['spent_usd']+amount_usd,6);job['estimated_cost_usd']=round(job['estimated_cost_usd']+amount_usd,6)
                        job['payment_status']='SETTLED';paid_this_request=True
                        job['payment_records'].append({'provider':provider.name,'capability':capability,'network':selected.get('network'),'asset':selected.get('asset'),'amount_usd':amount_usd,'pay_to':selected.get('payTo') or selected.get('pay_to'),'tx_id':receipt['tx_id'],'status':'CONFIRMED','facilitator':'GoPlausible x402-avm SDK','settlement_receipt':receipt})
                        result=paid
                        job['providers'][-1]['status']=paid.get('status');job['providers'][-1]['http_status']=paid.get('http_status')
                        log(f'x402 payment confirmed for {provider.name}/{capability}: ${amount_usd:.6f}; transaction {receipt["tx_id"]}.')
                    except Exception as exc:
                        if isinstance(exc,X402ReconciliationRequired):
                            job['payment_status']='RECONCILIATION_REQUIRED';stop_procurement=True
                            log(f'{provider.name} x402 settlement is uncertain. Procurement stopped to prevent a duplicate charge; reconcile the transaction before retrying: {exc}','ERROR')
                        else:
                            job['payment_status']='PAYMENT_FAILED'
                            log(f'{provider.name} HTTP 402 payment flow did not complete; no evidence was accepted: {exc}','WARNING')
                        continue
                if result.get('status')!='AVAILABLE':log(f'{provider.name}/{capability} unavailable: {result.get("error","unknown error")}.','WARNING');continue
                payload=_extract_payload({**result,'capability':capability})
                if not payload:log(f'{provider.name}/{capability} returned an unsupported response shape.','WARNING');continue
                _merge_evidence(evidence,payload,provider.name,result.get('retrieved_at'),result.get('source_type','LIVE_OBSERVATION'))
                raw=json.dumps(result.get('evidence'),sort_keys=True,default=str).encode()
                job['evidence_records'].append({'provider':provider.name,'endpoint_id':capability,'source_type':result.get('source_type','LIVE_OBSERVATION'),'observed_at':result.get('observed_at'),'retrieved_at':result.get('retrieved_at'),'raw':result.get('evidence'),'normalized':payload,'sha256':hashlib.sha256(raw).hexdigest()})
                if not paid_this_request:job['estimated_cost_usd']+=cost
        if not providers:log('No live providers are configured. No synthetic success was substituted.','WARNING')
    if not settings.demo_mode:
        source_types={e.get('source_type','LIVE_OBSERVATION') for e in job['evidence_records']}
        job['source_type']='MIXED_LIVE_AND_SANDBOX' if 'LIVE_OBSERVATION' in source_types and 'SANDBOX_PROVIDER_DATA' in source_types else (next(iter(source_types)) if source_types else 'NO_EXTERNAL_EVIDENCE')
    evidence['source_type']=job['source_type']
    job['status']='COMPLETED' if evidence.get('container') or settings.demo_mode else 'COMPLETED_WITH_INSUFFICIENT_EVIDENCE'
    job['completed_at']=datetime.now(timezone.utc).isoformat(); job['spent_usd']=round(job['spent_usd'],6);job['estimated_cost_usd']=round(job['estimated_cost_usd'],6)
    job['evidence']=evidence
    log(f'Procurement finished after {requests} request(s); estimated provider cost ${job["estimated_cost_usd"]:.6f}; confirmed spend ${job["spent_usd"]:.6f}.')
    return job
