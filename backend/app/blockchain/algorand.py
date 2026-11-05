"""Algorand TestNet status and escrow actions. Secrets remain backend-only."""
import base64
from ..config import settings

def _client():
    try:from algosdk.v2client import algod
    except ImportError as exc:raise RuntimeError('Install py-algorand-sdk to use Algorand integration') from exc
    return algod.AlgodClient(settings.algorand_algod_token,settings.algorand_algod_url)

def _decode_state(app_info):
    state={}
    for item in app_info.get('params',{}).get('global-state',[]):
        key=base64.b64decode(item['key']).decode(errors='replace');value=item['value']
        state[key]=value.get('uint') if value.get('type')==2 else base64.b64decode(value.get('bytes','')).hex()
    return state

def application_state(app_id=None):
    app_id=int(app_id or settings.algorand_app_id)
    if not app_id:return {'configured':False,'status':'NOT_DEPLOYED','network':settings.algorand_network}
    from algosdk import logic
    client=_client();info=client.application_info(app_id)
    return {'configured':True,'app_id':app_id,'app_address':logic.get_application_address(app_id),'network':settings.algorand_network,'global_state':_decode_state(info),'confirmed_round':info.get('round')}

def status():
    return {'network':settings.algorand_network,'algod_url':settings.algorand_algod_url,'app_id':settings.algorand_app_id or None,'enabled':bool(not settings.demo_mode and settings.algorand_app_id and settings.algorand_verifier_mnemonic),'mode':'TESTNET_CONFIGURED' if settings.algorand_app_id and settings.algorand_verifier_mnemonic else 'DEPLOYMENT_REQUIRED','note':'x402 provider purchases, Base customer payments and Algorand escrow are separate transactions.'}

def execute_action(app_id,action):
    if settings.demo_mode:raise RuntimeError('Disable DEMO_MODE before enabling blockchain actions')
    if settings.algorand_network.lower()!='testnet':raise RuntimeError('This application action endpoint is restricted to Algorand TestNet')
    if not settings.algorand_app_id:raise RuntimeError('ALGORAND_APP_ID must be configured before API escrow actions are enabled')
    if int(app_id)!=settings.algorand_app_id:raise RuntimeError('Application ID does not match configured escrow application')
    if not settings.algorand_verifier_mnemonic:raise RuntimeError('ALGORAND_VERIFIER_MNEMONIC is not configured')
    if settings.algorand_app_id and int(app_id)!=settings.algorand_app_id:raise RuntimeError('Application ID does not match configured escrow application')
    from algosdk import mnemonic,account,transaction
    client=_client();private_key=mnemonic.to_private_key(settings.algorand_verifier_mnemonic);sender=account.address_from_private_key(private_key)
    info=client.application_info(int(app_id));state=_decode_state(info)
    asset_id=int(state.get('asset',0));beneficiary=state.get('beneficiary','')
    args=[action.encode()];accounts=[beneficiary] if action=='release' and beneficiary else None;assets=[asset_id] if action in ('release','refund') and asset_id else None
    if action=='release' and not beneficiary:raise RuntimeError('Escrow contract has no beneficiary')
    params=client.suggested_params();params.flat_fee=True;params.fee=2000
    txn=transaction.ApplicationNoOpTxn(sender,params,int(app_id),app_args=args,accounts=accounts,foreign_assets=assets)
    txid=client.send_transaction(txn.sign(private_key));confirmed=transaction.wait_for_confirmation(client,txid,10)
    latest=application_state(app_id)
    return {'tx_id':txid,'confirmed_round':confirmed.get('confirmed-round'),'application':latest,'status':latest.get('global_state',{}).get('status'),'explorer_url':f'https://testnet.explorer.perawallet.app/application/{app_id}'}
