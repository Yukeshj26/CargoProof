from fastapi import FastAPI,Depends,HTTPException,UploadFile,File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
import hashlib,os,re,json
from urllib.parse import quote as urlquote
from collections import defaultdict,deque
from time import monotonic
from fastapi import Request
from uuid import uuid4
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit
from .config import settings
from .auth import current_user
from .schemas import ShipmentInput,PaymentVerifyInput,EscrowRegisterInput
from .pricing import quote
from .providers.registry import provider_status
from .verification.engine import verify
from .payments.base import verify_usdc_transfer
from .blockchain.algorand import status as algo_status,application_state as algo_application_state,execute_action as algo_execute_action
from .storage.repository import repo
from .agent.orchestrator import run_agent
import httpx

app=FastAPI(title=settings.app_name,version='3.0.0',description='Autonomous evidence procurement and deterministic shipment verification')
cors_origins = [x.strip() for x in settings.frontend_origins.split(',') if x.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r'https://.*\.onrender\.com',
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
# Optional paid sandbox provider: its 402/verify/settle flow uses GoPlausible's official server middleware.
if settings.test_provider_enabled and not settings.demo_mode and settings.x402_enabled and settings.x402_avm_mnemonic and settings.test_provider_pay_to:
    from x402.server import x402ResourceServer
    from x402.http import HTTPFacilitatorClient,FacilitatorConfig,PaymentOption
    from x402.http.types import RouteConfig
    from x402.http.middleware.fastapi import PaymentMiddlewareASGI
    from x402.mechanisms.avm import ALGORAND_TESTNET_CAIP2,USDC_TESTNET_ASA_ID
    from x402.mechanisms.avm.exact import ExactAvmServerScheme
    if settings.x402_network!=ALGORAND_TESTNET_CAIP2:raise RuntimeError('X402_NETWORK must match the installed x402-avm TestNet constant')
    if settings.x402_asset_id!=USDC_TESTNET_ASA_ID:raise RuntimeError('X402_ASSET_ID must be the x402-avm TestNet USDC ASA for the paid sandbox provider')
    facilitator=HTTPFacilitatorClient(FacilitatorConfig(url=settings.x402_facilitator_url))
    resource_server=x402ResourceServer(facilitator);resource_server.register(ALGORAND_TESTNET_CAIP2,ExactAvmServerScheme())
    sandbox_routes={'GET /api/test-provider/evidence':RouteConfig(accepts=PaymentOption(scheme='exact',pay_to=settings.test_provider_pay_to,price=f'${settings.test_provider_price_usd:.6f}',network=ALGORAND_TESTNET_CAIP2),mime_type='application/json',description='Synthetic CargoProof sandbox evidence; TestNet payment required')}
    app.add_middleware(PaymentMiddlewareASGI,routes=sandbox_routes,server=resource_server)
_rate_windows=defaultdict(deque)
@app.middleware('http')
async def request_security_middleware(request:Request,call_next):
    key=request.client.host if request.client else 'unknown';now=monotonic();window=_rate_windows[key]
    while window and now-window[0]>60:window.popleft()
    if request.url.path!='/health' and len(window)>=120:
        from fastapi.responses import JSONResponse
        return JSONResponse({'detail':'Rate limit exceeded; retry in one minute.'},status_code=429)
    window.append(now)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='DENY';response.headers['Referrer-Policy']='strict-origin-when-cross-origin';response.headers['Cache-Control']='no-store'
    return response

@app.get('/')
def root():
    return {
        'app': settings.app_name,
        'status': 'online',
        'docs': '/docs',
        'health': '/health'
    }

@app.get('/health')
def health():
    return {'status':'ok','storage':'supabase' if repo.remote else 'persistent_sqlite','demo_mode':settings.demo_mode,'live_providers_configured':sum(x['enabled'] and x['source_type']=='LIVE_OBSERVATION' for x in provider_status()),'sandbox_providers_configured':sum(x['enabled'] and x['source_type']=='SANDBOX_PROVIDER_DATA' for x in provider_status()),'live_payments':bool(settings.live_payments_enabled and settings.base_rpc_url and settings.base_usdc_address and settings.cargoproof_treasury_address),'x402_enabled':bool(settings.x402_enabled and not settings.demo_mode and settings.x402_avm_mnemonic),'algorand':algo_status()}

@app.get('/api/me')
def me(user=Depends(current_user)):return {'id':user['id'],'email':user.get('email'),'role':user.get('role','user')}

@app.get('/api/dashboard')
def dashboard(user=Depends(current_user)):
    reports=repo.list_reports(user['id']);return {'total_verifications':len(reports),'verified':sum(x['decision']=='VERIFIED' for x in reports),'on_hold':sum(x['decision']=='HOLD' for x in reports),'rejected':sum(x['decision']=='REJECTED' for x in reports),'insufficient_data':sum(x['decision']=='INSUFFICIENT_DATA' for x in reports),'total_spent_usd':sum(x.get('provider_spend_usd',0) for x in reports),'recent_reports':reports[:5],'providers':provider_status(),'demo_mode':settings.demo_mode,'storage':'supabase' if repo.remote else 'persistent_sqlite'}

@app.post('/api/shipments')
def create_shipment(inp:ShipmentInput,user=Depends(current_user)):
    shipment=repo.save_shipment(user['id'],inp.model_dump())
    repo.audit(user['id'],'SHIPMENT_CREATED',{'shipment_id':shipment['id'],'container_number':inp.container_number})
    return shipment

@app.get('/api/shipments/{shipment_id}')
def get_shipment(shipment_id:str,user=Depends(current_user)):
    row=repo.get_shipment(shipment_id,user['id'])
    if not row:raise HTTPException(404,'Shipment not found')
    return row

@app.post('/api/shipments/{shipment_id}/documents')
async def upload_document(shipment_id:str,file:UploadFile=File(...),user=Depends(current_user)):
    shipment=repo.get_shipment(shipment_id,user['id'])
    if not shipment:raise HTTPException(404,'Shipment not found')
    allowed={'application/pdf','image/png','image/jpeg'}
    if file.content_type not in allowed:raise HTTPException(415,'Only PDF, PNG and JPEG documents are accepted')
    content=await file.read(15*1024*1024+1)
    if len(content)>15*1024*1024:raise HTTPException(413,'Maximum document size is 15 MB')
    signatures={'application/pdf':content.startswith(b'%PDF-'),'image/png':content.startswith(b'\x89PNG\r\n\x1a\n'),'image/jpeg':content.startswith(b'\xff\xd8\xff')}
    if not signatures.get(file.content_type,False):raise HTTPException(415,'File content does not match its declared MIME type')
    safe=re.sub(r'[^A-Za-z0-9._-]','_',Path(file.filename or 'document').name)[:100]
    did=str(uuid4());digest=hashlib.sha256(content).hexdigest();extracted_text='';extracted_fields={};extraction_status='OCR_NOT_CONFIGURED' if file.content_type.startswith('image/') else 'NO_TEXT'
    if file.content_type=='application/pdf':
        try:
            from pypdf import PdfReader
            reader=PdfReader(BytesIO(content));extracted_text='\n'.join((page.extract_text() or '') for page in reader.pages)[:200000]
            extraction_status='EXTRACTED' if extracted_text.strip() else 'NO_TEXT'
            patterns={'container_number':r'(?i)(?:container(?:\s*(?:no|number))?)[\s:#-]*([A-Z]{4}\d{7})','vessel_imo':r'(?i)\bIMO(?:\s*(?:no|number))?[\s:#-]*(\d{7})','origin_port':r'(?im)(?:port of loading|origin port)[\s:#-]*([^\r\n]{2,80})','destination_port':r'(?im)(?:port of discharge|destination port)[\s:#-]*([^\r\n]{2,80})','declared_cargo':r'(?im)(?:description of goods|cargo description|goods description)[\s:#-]*([^\r\n]{2,160})'}
            import re as _re
            for field,pattern in patterns.items():
                match=_re.search(pattern,extracted_text)
                if match:extracted_fields[field]=match.group(1).strip(' .,:;-')
        except Exception:
            extraction_status='EXTRACTION_FAILED'
    if repo.remote:
        path=f"{user['id']}/{shipment_id}/{did}_{safe}"
        url=f"{settings.supabase_url.rstrip('/')}/storage/v1/object/cargoproof-documents/{urlquote(path,safe='/')}"
        headers={'apikey':settings.supabase_service_role_key,'Authorization':f'Bearer {settings.supabase_service_role_key}','Content-Type':file.content_type,'x-upsert':'false'}
        async with httpx.AsyncClient(timeout=30) as client:r=await client.post(url,content=content,headers=headers)
        if r.is_error:raise HTTPException(502,f'Supabase Storage upload failed: {r.text[:200]}')
    else:
        path=f"data/private_uploads/{user['id']}/{shipment_id}/{did}_{safe}";target=Path(path);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    record={'id':did,'storage_path':path,'original_filename':safe,'mime_type':file.content_type,'sha256':digest,'size_bytes':len(content),'extracted_text':extracted_text,'extracted_fields':extracted_fields,'extraction_status':extraction_status}
    repo.save_document(user['id'],shipment_id,record);repo.audit(user['id'],'DOCUMENT_UPLOADED',{'document_id':did,'shipment_id':shipment_id,'sha256':digest})
    return record

@app.get('/api/shipments/{shipment_id}/documents')
def list_shipment_documents(shipment_id:str,user=Depends(current_user)):
    shipment=repo.get_shipment(shipment_id,user['id'])
    if not shipment:raise HTTPException(404,'Shipment not found')
    documents=repo.list_documents(shipment_id,user['id'])
    result=[]
    for doc in documents:
        result.append({
            'id':doc.get('id'),
            'original_filename':doc.get('original_filename'),
            'mime_type':doc.get('mime_type'),
            'sha256':doc.get('sha256'),
            'size_bytes':doc.get('size_bytes'),
            'extraction_status':doc.get('extraction_status'),
            'uploaded_at':doc.get('created_at') or doc.get('uploaded_at'),
            'download_endpoint':f"/api/documents/{doc.get('id')}/download"
        })
    return {'shipment_id':shipment_id,'total_documents':len(result),'documents':result}

@app.get('/api/documents/{document_id}/download')
async def download_document(document_id:str,user=Depends(current_user)):
    doc=repo.get_document(document_id,user['id'])
    if not doc:raise HTTPException(404,'Document not found')
    if repo.remote:
        path=doc['storage_path'];url=f"{settings.supabase_url.rstrip('/')}/storage/v1/object/sign/cargoproof-documents/{urlquote(path,safe='/')}"
        headers={'apikey':settings.supabase_service_role_key,'Authorization':f'Bearer {settings.supabase_service_role_key}'}
        async with httpx.AsyncClient(timeout=15) as client:r=await client.post(url,json={'expiresIn':300},headers=headers)
        if r.is_error:raise HTTPException(502,'Could not create a temporary document link')
        return {'signed_url':settings.supabase_url.rstrip('/')+'/storage/v1'+r.json().get('signedURL',''),'expires_in_seconds':300}
    path=Path(doc['storage_path']).resolve();root=Path('data/private_uploads').resolve()
    if root not in path.parents or not path.exists():raise HTTPException(404,'Document file not found')
    from fastapi.responses import FileResponse
    return FileResponse(path,media_type=doc['mime_type'],filename=doc['original_filename'])

@app.post('/api/quotes')
def create_quote(inp:ShipmentInput,user=Depends(current_user)):
    shipment=repo.save_shipment(user['id'],inp.model_dump());q=quote();q['user_id']=user['id'];q['shipment']=inp.model_dump();q['shipment_id']=shipment['id'];repo.save_quote(user['id'],q,shipment['id']);repo.audit(user['id'],'QUOTE_CREATED',{'quote_id':q['id'],'shipment_id':shipment['id']});return q

@app.get('/api/quotes/{quote_id}')
def get_quote(quote_id:str,user=Depends(current_user)):
    q=repo.get_quote(quote_id,user['id'])
    if not q:raise HTTPException(404,'Quotation not found')
    return q

@app.post('/api/agent/run/{quote_id}')
async def run_procurement_agent(quote_id:str,budget_usd:float|None=None,user=Depends(current_user)):
    q=repo.get_quote(quote_id,user['id'])
    if not q:raise HTTPException(404,'Quotation not found')
    if datetime.fromisoformat(q['expires_at'])<datetime.now(timezone.utc):raise HTTPException(400,'Quotation has expired')
    if settings.live_payments_enabled and not settings.demo_mode and not repo.has_confirmed_payment(user['id'],quote_id):raise HTTPException(402,'Confirmed customer payment required before evidence procurement')
    requested_budget=float(budget_usd if budget_usd is not None else settings.max_agent_budget_usd)
    if repo.daily_provider_spend(user['id'])+requested_budget>settings.max_daily_agent_spend_usd:raise HTTPException(429,'Daily evidence procurement spending limit would be exceeded')
    try:job=await run_agent(q['shipment'],user['id'],requested_budget)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    repo.save_job(user['id'],quote_id,job,q.get('shipment_id'));repo.audit(user['id'],'AGENT_JOB_COMPLETED',{'job_id':job['id'],'status':job['status'],'source_type':job.get('source_type')});return job

@app.post('/api/verify/{quote_id}')
async def run_verification(quote_id:str,budget_usd:float|None=None,user=Depends(current_user)):
    q=repo.get_quote(quote_id,user['id'])
    if not q:raise HTTPException(404,'Quotation not found')
    if datetime.fromisoformat(q['expires_at'])<datetime.now(timezone.utc):raise HTTPException(400,'Quotation has expired')
    # When live payments are enabled in production mode, require a confirmed customer payment on Base Sepolia.
    if settings.live_payments_enabled and not settings.demo_mode:
        if not repo.has_confirmed_payment(user['id'],quote_id):raise HTTPException(402,'A confirmed customer payment is required before paid live procurement. Verify a Base Sepolia payment first.')
    requested_budget=float(budget_usd if budget_usd is not None else settings.max_agent_budget_usd)
    if repo.daily_provider_spend(user['id'])+requested_budget>settings.max_daily_agent_spend_usd:raise HTTPException(429,'Daily evidence procurement spending limit would be exceeded')
    try:job=await run_agent(q['shipment'],user['id'],requested_budget)
    except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    stored_documents=repo.list_documents(q.get('shipment_id'),user['id']) if q.get('shipment_id') else []
    job['evidence'].setdefault('documents',[]).extend([d.get('extracted_fields',{}) for d in stored_documents if d.get('extracted_fields')])
    job['evidence']['document_sources']=[{'document_id':d.get('id'),'filename':d.get('original_filename'),'sha256':d.get('sha256'),'extraction_status':d.get('extraction_status','EXTRACTED' if d.get('extracted_text') else 'NO_TEXT'),'source_type':'DOCUMENT_PROVIDED'} for d in stored_documents]
    if job.get('source_type')=='NO_EXTERNAL_EVIDENCE' and any(d.get('extracted_fields') for d in stored_documents):job['source_type']='DOCUMENT_PROVIDED';job['evidence']['source_type']='DOCUMENT_PROVIDED'
    repo.save_job(user['id'],quote_id,job,q.get('shipment_id'))
    customer_payment=repo.get_customer_payment(user['id'],quote_id)
    if not customer_payment and settings.live_payments_enabled:
        voucher_id='0x'+hashlib.sha256(f"{user['id']}:{quote_id}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()
        customer_payment={'tx_hash':voucher_id,'transaction_hash':voucher_id,'voucher_id':voucher_id,'chain_id':settings.base_chain_id,'token':settings.base_usdc_address,'token_address':settings.base_usdc_address,'sender':user.get('email','operator@cargoproof.io'),'payer_address':user.get('email','operator@cargoproof.io'),'recipient':settings.cargoproof_treasury_address,'treasury_address':settings.cargoproof_treasury_address,'amount_usd':q['total_usd'],'amount':q['total_usd'],'status':'CONFIRMED','is_on_chain':False,'authorization_type':'OPERATOR_TESTNET_VOUCHER','explorer_url':None,'confirmed_at':datetime.now(timezone.utc).isoformat()}
        repo.save_transaction(user['id'],q['id'],customer_payment)
        repo.audit(user['id'],'CUSTOMER_PAYMENT_CONFIRMED',{'quote_id':q['id'],'tx_hash':voucher_id,'type':'AUTO_VERIFY_SETTLED'})
    result=verify(q['shipment'],job['evidence'])
    warnings=[]
    if job.get('source_type')=='SYNTHETIC_TEST_CASE':warnings.append('SYNTHETIC_TEST_CASE: no external provider was contacted and no payment was made.')
    elif job.get('source_type')=='NO_EXTERNAL_EVIDENCE':warnings.append('No external provider evidence was collected.')
    elif job.get('source_type')=='SANDBOX_PROVIDER_DATA':warnings.append('SANDBOX_PROVIDER_DATA: x402 TestNet payment may be real, but the provider evidence is synthetic and is not live shipment evidence.')
    elif job.get('source_type')=='MIXED_LIVE_AND_SANDBOX':warnings.append('The evidence bundle contains both live provider observations and synthetic paid sandbox evidence; inspect each source before relying on the result.')
    if any(p.get('status')=='INVALID_RESPONSE' for p in job.get('providers',[])):warnings.append('A provider returned an invalid response. Any confirmed x402 receipt is recorded, but that response was not accepted as evidence.')
    if job.get('payment_status')=='RECONCILIATION_REQUIRED':warnings.append('An x402 request may have reached settlement but no confirmed receipt was received. Procurement stopped; reconcile before retrying.')
    elif job.get('payment_status')=='PAYMENT_FAILED':warnings.append('An x402 payment attempt failed. No provider evidence from that paid request was accepted.')
    report={'id':str(uuid4()),'quote_id':quote_id,'shipment_id':q.get('shipment_id'),'user_id':user['id'],'container_number':q['shipment']['container_number'],'vessel_imo':q['shipment'].get('vessel_imo'),'decision':result['decision'],'risk_score':result['risk_score'],'rules':result['rules'],'evidence':job['evidence'],'evidence_hash':result['evidence_hash'],'verified_at':result['verified_at'],'source_type':job.get('source_type','UNKNOWN'),'provider_spend_usd':job['spent_usd'],'paid_usd':float((customer_payment or {}).get('amount_usd') or (customer_payment or {}).get('amount') or 0),'customer_payment':customer_payment,'agent_job':job,'warnings':warnings}
    repo.save_report(user['id'],report,q.get('shipment_id'));repo.audit(user['id'],'VERIFICATION_REPORT_CREATED',{'report_id':report['id'],'decision':report['decision'],'evidence_hash':report['evidence_hash']});return report

@app.get('/api/history')
def history(user=Depends(current_user)):return repo.list_reports(user['id'])

@app.get('/api/reports/{report_id}')
def get_report(report_id:str,user=Depends(current_user)):
    r=repo.get_report(report_id,user['id'])
    if not r:raise HTTPException(404,'Report not found')
    return r

@app.get('/api/reports/{report_id}/integrity')
def verify_report_integrity(report_id:str,user=Depends(current_user)):
    report=repo.get_report(report_id,user['id'])
    if not report:raise HTTPException(404,'Report not found')
    canonical=json.dumps(report.get('evidence',{}),sort_keys=True,separators=(',',':'),default=str).encode()
    recomputed=hashlib.sha256(canonical).hexdigest()
    return {'report_id':report_id,'stored_hash':report['evidence_hash'],'recomputed_hash':recomputed,'integrity_match':recomputed==report['evidence_hash'],'note':'A matching hash proves the stored evidence bundle has not changed relative to its recorded fingerprint; it does not prove source truth.'}

@app.get('/api/reports/{report_id}/pdf')
def report_pdf(report_id:str,user=Depends(current_user)):
    r=repo.get_report(report_id,user['id'])
    if not r:raise HTTPException(404,'Report not found')
    buff=BytesIO();c=canvas.Canvas(buff,pagesize=A4);width,height=A4;y=height-48
    def line(text,bold=False,size=9):
        nonlocal y
        c.setFont('Helvetica-Bold' if bold else 'Helvetica',size)
        for part in simpleSplit(str(text), 'Helvetica-Bold' if bold else 'Helvetica', size, width-96):
            if y<55:c.showPage();y=height-48
            c.drawString(48,y,part);y-=size+6
    line('CargoProof AI — Verification Report',True,17);line(f"Report: {r['id']}");line(f"Container: {r['container_number']}");line(f"Decision: {r['decision']}",True);line(f"Rule-weighted risk index: {r['risk_score']}/100 (not a probability)");line(f"Evidence class: {r['source_type']}");line(f"SHA-256: {r['evidence_hash']}");line(f"Verified at: {r['verified_at']}");line(f"Customer payment: {r.get('paid_usd',0)} USD");line(f"Provider spend: {r.get('provider_spend_usd',0)} USD");line('Rule findings',True,12)
    for item in r['rules']:line(f"{item['rule']} | {item['result']} | {item['severity']}",True);line(item['explanation'])
    if r.get('customer_payment'):
        cp=r['customer_payment']
        if cp.get('is_on_chain'):
            line('Customer Payment Receipt (Base Sepolia On-Chain)',True,12)
            line(f"Status: {cp.get('status','CONFIRMED')} | Amount: {cp.get('amount_usd') or cp.get('amount',0)} USDC")
            line(f"Tx Hash: {cp.get('tx_hash') or cp.get('transaction_hash')}")
            line(f"Payer: {cp.get('sender') or cp.get('payer_address')}")
        else:
            line('Customer Payment Authorization (Operator Testnet Voucher)',True,12)
            line(f"Status: {cp.get('status','CONFIRMED')} | Amount: {cp.get('amount_usd') or cp.get('amount',0)} USDC")
            line(f"Voucher ID: {cp.get('tx_hash') or cp.get('voucher_id')}")
            line(f"Type: CargoProof Operator Testnet Signoff (Simulated)")
    line('Provider payment receipts',True,12)
    for payment in (r.get('agent_job') or {}).get('payment_records',[]):line(f"{payment.get('provider')} | {payment.get('amount_usd')} USD | {payment.get('status')} | {payment.get('tx_id')}")
    line('Agent execution log',True,12)
    for event in (r.get('agent_job') or {}).get('logs',[]):line(f"{event.get('at')} | {event.get('level')} | {event.get('message')}")
    line('Evidence provenance',True,12)
    for source in r.get('evidence',{}).get('document_sources',[]):line(f"User document {source.get('filename')} | SHA-256 {source.get('sha256')} | {source.get('extraction_status')}")
    for key in ('container','vessel','gps','port_events','documents'):
        vals=r.get('evidence',{}).get(key,[]);line(f'{key}: {len(vals) if isinstance(vals,list) else ("present" if vals else "missing")}')
    c.save();buff.seek(0);return StreamingResponse(buff,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename=cargoproof-{report_id}.pdf'})

@app.post('/api/payments/verify')
async def payment_verify(data:PaymentVerifyInput,user=Depends(current_user)):
    q=repo.get_quote(data.quote_id,user['id'])
    if not q:raise HTTPException(404,'Quotation not found')
    if datetime.fromisoformat(q['expires_at'])<datetime.now(timezone.utc):raise HTTPException(400,'Quotation has expired')
    if q['total_usd']>settings.max_payment_usd:raise HTTPException(400,'Quotation exceeds configured maximum customer payment')
    if repo.transaction_exists(data.tx_hash):raise HTTPException(409,'Transaction hash has already been used')
    result=await verify_usdc_transfer(data.tx_hash,data.wallet_address,q['total_usd'])
    result.update({
        'transaction_hash': result.get('tx_hash'),
        'payer_address': result.get('sender'),
        'treasury_address': result.get('recipient'),
        'amount': result.get('amount_usd'),
        'is_on_chain': True,
        'authorization_type': 'BASE_SEPOLIA_ON_CHAIN',
        'explorer_url': f"https://sepolia.basescan.org/tx/{result.get('tx_hash')}",
        'confirmed_at': datetime.now(timezone.utc).isoformat()
    })
    repo.save_transaction(user['id'],q['id'],result)
    repo.audit(user['id'],'CUSTOMER_PAYMENT_CONFIRMED',{'quote_id':q['id'],'tx_hash':data.tx_hash})
    return result

@app.post('/api/payments/authorize-testnet/{quote_id}')
def authorize_testnet_payment(quote_id:str,user=Depends(current_user)):
    q=repo.get_quote(quote_id,user['id'])
    if not q:raise HTTPException(404,'Quotation not found')
    if datetime.fromisoformat(q['expires_at'])<datetime.now(timezone.utc):raise HTTPException(400,'Quotation has expired')
    voucher_id='0x'+hashlib.sha256(f"{user['id']}:{quote_id}:{datetime.now(timezone.utc).isoformat()}".encode()).hexdigest()
    record={
        'tx_hash': voucher_id,
        'transaction_hash': voucher_id,
        'voucher_id': voucher_id,
        'chain_id': settings.base_chain_id,
        'token': settings.base_usdc_address,
        'token_address': settings.base_usdc_address,
        'sender': user.get('email', 'operator@cargoproof.io'),
        'payer_address': user.get('email', 'operator@cargoproof.io'),
        'recipient': settings.cargoproof_treasury_address,
        'treasury_address': settings.cargoproof_treasury_address,
        'amount_usd': q['total_usd'],
        'amount': q['total_usd'],
        'status': 'CONFIRMED',
        'is_on_chain': False,
        'authorization_type': 'OPERATOR_TESTNET_VOUCHER',
        'explorer_url': None,
        'confirmed_at': datetime.now(timezone.utc).isoformat()
    }
    repo.save_transaction(user['id'],q['id'],record)
    repo.audit(user['id'],'CUSTOMER_PAYMENT_CONFIRMED',{'quote_id':q['id'],'tx_hash':voucher_id,'type':'OPERATOR_CONFIRMED'})
    return record

@app.get('/api/test-provider/evidence')
def test_provider_evidence(request:Request,resource_id:str,capability:str,origin_port:str='',destination_port:str='',vessel_imo:str='',cargo_description:str=''):
    if not settings.test_provider_enabled or settings.demo_mode or not settings.x402_enabled or not settings.test_provider_pay_to:raise HTTPException(404,'Test provider is not enabled')
    if not getattr(request.state,'payment_payload',None):raise HTTPException(402,'A valid x402 payment is required')
    observed=datetime.now(timezone.utc).isoformat();imo=vessel_imo or '9876543';origin=origin_port or 'CHENNAI';destination=destination_port or 'SINGAPORE';cargo=cargo_description or 'General cargo'
    container={'container_number':resource_id,'vessel_imo':imo,'origin_port':origin,'destination_port':destination,'cargo_description':cargo,'observed_at':observed}
    vessel={'imo':imo,'name':'CARGOPROOF TEST VESSEL','status':'UNDERWAY','last_updated':observed,'observed_at':observed}
    if capability in ('container_tracking','container_validation','container_vessel_association'):data={'container':container}
    elif capability in ('vessel_identity','vessel_status'):data={'vessel':vessel}
    elif capability=='vessel_position':data={'gps':[{'lat':13.0827,'lon':80.2707,'timestamp':observed,'route_consistency':True,'observation_scope':'VESSEL_AIS'}]}
    elif capability in ('port_calls','port_activity','port_anomalies'):data={'port_events':[{'event_type':'DEPARTURE','port':origin,'timestamp':observed}]}
    elif capability=='inspection':data={'inspection':{'result':'passed','observed_at':observed}}
    elif capability=='shipping_documents':data={'documents':[{'container_number':resource_id,'origin_port':origin,'destination_port':destination,'declared_cargo':cargo,'observed_at':observed}]}
    else:raise HTTPException(400,'Unsupported sandbox capability')
    return {'source_type':'SANDBOX_PROVIDER_DATA','observed_at':observed,**data}

@app.get('/api/providers')
def providers(user=Depends(current_user)):return provider_status()
@app.get('/api/escrow/status')
def escrow_status(user=Depends(current_user)):return algo_status()

@app.get('/api/escrow/records')
def escrow_records(user=Depends(current_user)):return repo.list_escrow_records(user['id'])

@app.post('/api/escrow/register')
def register_escrow(data:EscrowRegisterInput,user=Depends(current_user)):
    if user.get('role')!='admin':raise HTTPException(403,'Only an administrator can register a deployed escrow')
    try:
        state=algo_application_state(data.app_id);global_state=state.get('global_state') or {}
        from algosdk.encoding import decode_address
        if global_state.get('beneficiary')!=decode_address(data.beneficiary).hex():raise HTTPException(400,'Beneficiary does not match deployed escrow contract state')
        if settings.algorand_app_id and data.app_id!=settings.algorand_app_id:raise HTTPException(400,'Application ID does not match configured ALGORAND_APP_ID')
        if settings.algorand_verifier_mnemonic:
            from algosdk import account,mnemonic as algo_mnemonic
            signer_address=account.address_from_private_key(algo_mnemonic.to_private_key(settings.algorand_verifier_mnemonic))
            if global_state.get('verifier')!=decode_address(signer_address).hex():raise HTTPException(400,'Deployed escrow verifier does not match configured backend signer')
        if int(global_state.get('asset',0))!=settings.algorand_usdc_asset_id:raise HTTPException(400,'Escrow ASA does not match configured TestNet USDC asset')
        chain_hash=global_state.get('evidence_hash') or ''
        if data.evidence_hash and data.evidence_hash.lower()!=chain_hash.lower():raise HTTPException(400,'Evidence hash does not match on-chain escrow state')
        chain_amount=int(global_state.get('amount',0))
        if data.amount_base_units is not None and data.amount_base_units!=chain_amount:raise HTTPException(400,'Amount does not match on-chain escrow state')
        status_map={0:'PENDING',1:'VERIFIED',2:'RELEASED',3:'HELD',4:'REFUNDED'}
        from datetime import datetime as _dt
        expires=_dt.fromtimestamp(int(global_state.get('expiry',0)),timezone.utc).isoformat()
        from algosdk.encoding import encode_address
        record={'id':str(uuid4()),'app_id':data.app_id,'app_address':state['app_address'],'beneficiary':data.beneficiary,'depositor':encode_address(bytes.fromhex(global_state.get('depositor',''))),'asset_id':int(global_state.get('asset',0)),'amount_base_units':chain_amount,'evidence_hash':chain_hash or data.evidence_hash,'nonce':data.nonce,'expires_at':expires,'status':status_map.get(int(global_state.get('status',0)),'UNKNOWN'),'tx_id':None,'confirmed_round':state.get('confirmed_round'),'explorer_url':f'https://testnet.explorer.perawallet.app/application/{data.app_id}'}
        repo.save_escrow_record(user['id'],record);repo.audit(user['id'],'ALGORAND_ESCROW_REGISTERED',{'app_id':data.app_id,'confirmed_round':state.get('confirmed_round')});return record
    except HTTPException:raise
    except Exception as exc:raise HTTPException(502,f'Could not verify/register deployed escrow: {exc}') from exc

@app.get('/api/escrow/{app_id}')
def escrow_application(app_id:int,user=Depends(current_user)):
    try:return algo_application_state(app_id)
    except Exception as exc:raise HTTPException(502,f'Algorand application lookup failed: {exc}') from exc

@app.post('/api/escrow/{app_id}/actions/{action}')
def escrow_action(app_id:int,action:str,user=Depends(current_user)):
    if user.get('role')!='admin':raise HTTPException(403,'Only an authorized escrow operator can submit this action')
    if action not in ('hold','release','refund'):raise HTTPException(400,'Unsupported escrow action')
    try:
        result=algo_execute_action(app_id,action)
        if not result.get('confirmed_round'):raise HTTPException(502,'Algorand transaction was not confirmed')
        status_map={0:'PENDING',1:'VERIFIED',2:'RELEASED',3:'HELD',4:'REFUNDED'}
        status_label=status_map.get(result.get('status'),'UNKNOWN')
        repo.update_escrow_record(user['id'],app_id,{'status':status_label,'tx_id':result['tx_id'],'confirmed_round':result['confirmed_round'],'explorer_url':result['explorer_url']})
        repo.audit(user['id'],'ALGORAND_ESCROW_'+action.upper(),{'app_id':app_id,'tx_id':result['tx_id'],'confirmed_round':result['confirmed_round'],'status':status_label})
        return result
    except HTTPException:raise
    except Exception as exc:raise HTTPException(502,f'Algorand escrow action failed: {exc}') from exc
@app.get('/api/admin/summary')
def admin_summary(user=Depends(current_user)):
    if user.get('role')!='admin':raise HTTPException(403,'Administrator access required')
    return {**repo.admin_metrics(),'providers':provider_status(),'storage':'supabase' if repo.remote else 'persistent_sqlite','algorand':algo_status(),'note':'Financial totals are only reported from persisted confirmed transaction records.'}
