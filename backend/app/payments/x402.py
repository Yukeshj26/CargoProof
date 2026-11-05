"""GoPlausible x402-avm SDK integration for Algorand TestNet.
The official x402-httpx transport handles the 402 -> signed retry -> facilitator settlement flow.
CargoProof validates the advertised network, ASA, amount and budget before allowing the SDK retry.
"""
import base64,json
import httpx
from ..config import settings

class X402Error(RuntimeError):pass
class X402ReconciliationRequired(X402Error):pass

def decode_payment_required(header_value:str):
    if not header_value:raise X402Error('Provider returned HTTP 402 without PAYMENT-REQUIRED data')
    try:return json.loads(base64.b64decode(header_value+'===').decode('utf-8'))
    except Exception:
        try:return json.loads(header_value)
        except Exception as exc:raise X402Error('Payment requirements are not valid base64 JSON or JSON') from exc

def select_requirement(payment_required,max_amount_usd:float):
    accepts=payment_required.get('accepts') or payment_required.get('paymentRequirements') or []
    if not isinstance(accepts,list):raise X402Error('No x402 accepts/paymentRequirements array found')
    # x402-avm chooses a requirement by its registered network/scheme. Require exactly
    # one such option so it cannot silently select a different ASA or amount.
    matching=[r for r in accepts if isinstance(r,dict) and (r.get('network') or r.get('networkId'))==settings.x402_network and r.get('scheme')=='exact']
    if len(matching)!=1:raise X402Error('Provider must advertise exactly one Algorand TestNet exact payment option')
    req=matching[0];pay_to=req.get('payTo') or req.get('pay_to');asset=str(req.get('asset') or req.get('token') or '')
    try:amount_units=int(req.get('amount') or req.get('maxAmountRequired'))
    except (ValueError,TypeError):raise X402Error('x402 payment amount is missing or invalid')
    decimals=int((req.get('extra') or {}).get('decimals',6));amount_usd=amount_units/(10**decimals)
    if asset!=str(settings.x402_asset_id):raise X402Error('Provider requested an unsupported ASA; only configured TestNet USDC is allowed')
    if not pay_to or amount_units<=0:raise X402Error('x402 payment recipient or amount is invalid')
    if amount_usd>max_amount_usd:raise X402Error('x402 payment amount exceeds remaining procurement budget')
    return req

def _signer():
    if not settings.x402_enabled or settings.demo_mode:raise X402Error('x402 is disabled by configuration or demo mode is active')
    if not settings.x402_avm_mnemonic:raise X402Error('X402_AVM_MNEMONIC is not configured')
    try:
        import algosdk
        from algosdk import account,mnemonic
        from algosdk.v2client import algod
        from x402 import x402Client
        from x402.http import x402HTTPClient
        from x402.http.clients.httpx import x402HttpxClient
        from x402.mechanisms.avm import ALGORAND_TESTNET_CAIP2
        from x402.mechanisms.avm.exact.register import register_exact_avm_client
    except ImportError as exc:raise X402Error('Install x402-avm[httpx,avm] and py-algorand-sdk to enable x402') from exc
    if settings.x402_network!=ALGORAND_TESTNET_CAIP2:raise X402Error('Configured x402 network does not match the installed x402-avm TestNet CAIP-2 identifier')
    secret_key=mnemonic.to_private_key(settings.x402_avm_mnemonic);address=account.address_from_private_key(secret_key)
    class AlgorandSigner:
        def __init__(self,sk,addr):self._secret_key=sk;self._address=addr
        @property
        def address(self):return self._address
        def sign_transactions(self,unsigned_txns,indexes_to_sign):
            result=[]
            for i,txn_bytes in enumerate(unsigned_txns):
                if i in indexes_to_sign:
                    txn=algosdk.encoding.msgpack_decode(base64.b64encode(txn_bytes).decode())
                    signed=txn.sign(self._secret_key)
                    result.append(base64.b64decode(algosdk.encoding.msgpack_encode(signed)))
                else:result.append(None)
            return result
    signer=AlgorandSigner(secret_key,address)
    x402_client=x402Client()
    register_exact_avm_client(x402_client,signer,networks=ALGORAND_TESTNET_CAIP2,algod_url=settings.algorand_algod_url)
    return x402_client,x402HttpxClient,x402HTTPClient,address,algod

def check_wallet_balance(requirement):
    _,_,_,address,algod=_signer()
    client=algod.AlgodClient(settings.algorand_algod_token,settings.algorand_algod_url)
    info=client.account_info(address);asset_id=int(requirement['asset']);amount=int(requirement['amount'])
    holding=next((x for x in info.get('assets',[]) if int(x.get('asset-id',0))==asset_id),None)
    if not holding or int(holding.get('amount',0))<amount:raise X402Error('Agent wallet is not opted into the required ASA or has insufficient USDC')
    fee_payer=(requirement.get('extra') or {}).get('feePayer')
    if not fee_payer and int(info.get('amount',0))<1000:raise X402Error('Agent wallet has insufficient ALGO for the x402 transaction fee')
    return address

async def paid_httpx_request(url,params,headers):
    x402_client,x402_httpx_client,x402_http_client,_,_=_signer()
    async with x402_httpx_client(x402_client,timeout=30.0,follow_redirects=False) as client:
        try:response=await client.get(url,params=params,headers=headers)
        except Exception as exc:
            if exc.__class__.__name__=='PaymentError' or isinstance(exc,httpx.TimeoutException):
                raise X402ReconciliationRequired(f'x402 payment transport failed after payment handling may have started: {exc}') from exc
            raise X402Error(f'x402 request failed before a confirmed settlement: {exc}') from exc
        await response.aread()
        if response.status_code==402:raise X402Error('Provider still returned HTTP 402 after the x402 retry; payment was not confirmed')
        if not response.is_success:
            if response.status_code>=500:raise X402ReconciliationRequired(f'Provider returned HTTP {response.status_code} after x402 payment handling; reconcile before retrying')
            raise X402Error(f'Paid provider retry returned HTTP {response.status_code}')
        settlement_client=x402_http_client(x402_client)
        try:settlement=settlement_client.get_payment_settle_response(lambda name:response.headers.get(name))
        except ValueError as exc:raise X402ReconciliationRequired('Provider returned a successful resource response but no verifiable x402 settlement receipt; reconcile before retrying') from exc
        data=settlement.model_dump() if hasattr(settlement,'model_dump') else dict(settlement)
        if not data.get('success'):raise X402ReconciliationRequired(f'Facilitator settlement response is not successful or is ambiguous: {data}')
        tx=data.get('transaction') or {}
        if isinstance(tx,str):tx_id=tx
        elif isinstance(tx,dict):tx_id=tx.get('txId') or tx.get('tx_id') or tx.get('id')
        else:tx_id=getattr(tx,'tx_id',None) or getattr(tx,'txId',None)
        if not tx_id:raise X402ReconciliationRequired('Settlement response has no transaction ID; reconcile before retrying')
        return response,{'status':'CONFIRMED','tx_id':tx_id,'network':data.get('network',settings.x402_network),'receipt':data}
