from ..config import settings
from fastapi import HTTPException

async def verify_usdc_transfer(tx_hash:str,expected_sender:str,expected_amount_usd:float):
    if settings.demo_mode or not settings.live_payments_enabled:raise HTTPException(503,'Live payments are disabled. Test/demo mode cannot accept real funds.')
    if expected_amount_usd<=0 or expected_amount_usd>settings.max_payment_usd:raise HTTPException(400,'Payment amount is outside the configured limit')
    try:
        from web3 import Web3
        from web3.exceptions import TransactionNotFound
    except ImportError as exc:raise HTTPException(503,'Install web3 to enable Base payment receipt verification') from exc
    if not all([settings.base_rpc_url,settings.base_usdc_address,settings.cargoproof_treasury_address]):raise HTTPException(503,'Base payment configuration incomplete')
    w3=Web3(Web3.HTTPProvider(settings.base_rpc_url,request_kwargs={'timeout':12}))
    if not w3.is_connected():raise HTTPException(503,'Could not connect to configured Base RPC endpoint')
    try:receipt=w3.eth.get_transaction_receipt(tx_hash)
    except TransactionNotFound as exc:raise HTTPException(404,'Transaction is not yet confirmed or does not exist on Base Sepolia') from exc
    except Exception as exc:raise HTTPException(503,'Could not retrieve Base transaction receipt') from exc
    if receipt is None or receipt.status!=1:raise HTTPException(400,'Transaction was not successful')
    if w3.eth.chain_id!=settings.base_chain_id:raise HTTPException(400,'Unexpected Base chain ID')
    try:
        token=Web3.to_checksum_address(settings.base_usdc_address);treasury=Web3.to_checksum_address(settings.cargoproof_treasury_address);sender=Web3.to_checksum_address(expected_sender)
    except ValueError as exc:raise HTTPException(503,'Configured token/treasury or submitted wallet address is invalid') from exc
    topic=Web3.keccak(text='Transfer(address,address,uint256)').hex();matches=[]
    for log in receipt.logs:
        if log.address.lower()!=token.lower() or len(log.topics)<3 or log.topics[0].hex()!=topic:continue
        src=Web3.to_checksum_address('0x'+log.topics[1].hex()[-40:]);dst=Web3.to_checksum_address('0x'+log.topics[2].hex()[-40:]);amount=int.from_bytes(log.data,'big')
        if src.lower()==sender.lower() and dst.lower()==treasury.lower():matches.append(amount)
    required=int(round(expected_amount_usd*1_000_000))
    if required not in matches:raise HTTPException(400,'No matching USDC Transfer event from the submitted wallet to the CargoProof treasury for the exact quote amount')
    return {'tx_hash':tx_hash,'chain_id':w3.eth.chain_id,'token':token,'sender':sender,'recipient':treasury,'amount_usd':expected_amount_usd,'status':'CONFIRMED','block_number':receipt.blockNumber}
