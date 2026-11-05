"""Deploy and operate CargoProof escrow on Algorand TestNet.
All signing material is read from ALGORAND_VERIFIER_MNEMONIC on the backend/operator machine.
"""
import argparse, hashlib, json, os, time, sys
from dotenv import load_dotenv
from algosdk import account, mnemonic, transaction, logic
from algosdk.encoding import decode_address
from algosdk.v2client import algod
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from cargoproof_escrow_reference import approval, clear
from pyteal import compileTeal, Mode

load_dotenv(os.path.join(os.path.dirname(__file__),'..','..','..','backend','.env'))
ALGOD=os.getenv('ALGORAND_ALGOD_URL','https://testnet-api.algonode.cloud')
TOKEN=os.getenv('ALGORAND_ALGOD_TOKEN','')
MNEMONIC=os.getenv('ALGORAND_VERIFIER_MNEMONIC','')
ASSET=int(os.getenv('ALGORAND_USDC_ASSET_ID','10458941'))
client=algod.AlgodClient(TOKEN,ALGOD)

def signer():
    if not MNEMONIC:raise SystemExit('Set ALGORAND_VERIFIER_MNEMONIC in backend/.env')
    return mnemonic.to_private_key(MNEMONIC)
def send(txn,sk):
    stx=txn.sign(sk);txid=client.send_transaction(stx);print('Submitted:',txid)
    result=transaction.wait_for_confirmation(client,txid,8);print('Confirmed round:',result.get('confirmed-round'));return txid,result

def deploy(args):
    sk=signer();addr=account.address_from_private_key(sk);sp=client.suggested_params()
    approval_teal=compileTeal(approval(),Mode.Application,version=8);clear_teal=compileTeal(clear(),Mode.Application,version=8)
    approval_bin=base64_decode(client.compile(approval_teal)['result']);clear_bin=base64_decode(client.compile(clear_teal)['result'])
    app_args=[b'init',args.asset.to_bytes(8,'big'),decode_address(args.beneficiary),decode_address(addr),decode_address(addr),int(time.time()+args.ttl).to_bytes(8,'big')]
    txn=transaction.ApplicationCreateTxn(addr,sp,transaction.OnComplete.NoOpOC,approval_bin,clear_bin,transaction.StateSchema(4,4),transaction.StateSchema(0,0),app_args=app_args)
    txid,res=send(txn,sk);app_id=res['application-index'];app_addr=logic.get_application_address(app_id)
    print(json.dumps({'app_id':app_id,'app_address':app_addr,'creator':addr,'asset_id':args.asset,'create_txid':txid},indent=2))

def base_app_call(app_id,args,accounts=None,assets=None,fee=2000):
    sk=signer();addr=account.address_from_private_key(sk);sp=client.suggested_params();sp.flat_fee=True;sp.fee=fee
    txn=transaction.ApplicationNoOpTxn(addr,sp,app_id,app_args=args,accounts=accounts,foreign_assets=assets)
    return send(txn,sk)

def app_addr(app_id):return logic.get_application_address(app_id)
def optin(args):base_app_call(args.app_id,[b'optin'],assets=[args.asset])
def fund_algo(args):
    sk=signer();addr=account.address_from_private_key(sk);sp=client.suggested_params();sp.flat_fee=True
    txn=transaction.PaymentTxn(addr,sp,app_addr(args.app_id),args.amount)
    send(txn,sk)
def fund(args):
    sk=signer();addr=account.address_from_private_key(sk);sp=client.suggested_params();sp.flat_fee=True
    txn=transaction.AssetTransferTxn(addr,sp,app_addr(args.app_id),args.amount,args.asset)
    send(txn,sk)
def evidence(args):
    digest=bytes.fromhex(args.sha256)
    if len(digest)!=32:raise SystemExit('SHA-256 must be 64 hex characters')
    base_app_call(args.app_id,[b'evidence',digest,args.amount.to_bytes(8,'big')])
def hold(args):base_app_call(args.app_id,[b'hold'])
def release(args):base_app_call(args.app_id,[b'release'],accounts=[args.beneficiary],assets=[args.asset])
def refund(args):base_app_call(args.app_id,[b'refund'],assets=[args.asset])
def status(args):
    info=client.application_info(args.app_id);gs={x['key']:x['value'] for x in info['params'].get('global-state',[])}
    from base64 import b64decode
    decoded={}
    for key,val in gs.items():
        name=b64decode(key).decode(errors='replace');decoded[name]=val.get('uint') if val['type']==2 else b64decode(val.get('bytes','')).hex()
    print(json.dumps({'app_id':args.app_id,'app_address':app_addr(args.app_id),'global_state':decoded,'confirmed_round':info.get('round')},indent=2))
def base64_decode(s):
    import base64;return base64.b64decode(s)

p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
d=sub.add_parser('deploy');d.add_argument('--beneficiary',required=True);d.add_argument('--asset',type=int,default=ASSET);d.add_argument('--ttl',type=int,default=86400);d.set_defaults(fn=deploy)
for name,fn in [('optin',optin),('fund-algo',fund_algo),('fund',fund),('evidence',evidence),('hold',hold),('release',release),('refund',refund),('status',status)]:
    q=sub.add_parser(name);q.add_argument('--app-id',type=int,required=True);q.set_defaults(fn=fn)
    if name in ('optin','fund','release','refund'):q.add_argument('--asset',type=int,default=ASSET)
    if name=='fund-algo':q.add_argument('--amount',type=int,default=200000,help='MicroAlgo to fund the app account minimum balance')
    if name=='fund':q.add_argument('--amount',type=int,required=True,help='ASA base units; USDC has 6 decimals')
    if name=='evidence':q.add_argument('--sha256',required=True);q.add_argument('--amount',type=int,required=True)
    if name=='release':q.add_argument('--beneficiary',required=True)
a=p.parse_args();a.fn(a)
