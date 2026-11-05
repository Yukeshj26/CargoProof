from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

_backend_dir = Path(__file__).resolve().parent.parent
_root_dir = _backend_dir.parent

_env_candidates = [
    Path('.env'),
    _backend_dir / '.env',
    _root_dir / '.env',
]
_env_files = [str(p) for p in _env_candidates if p.exists()] or ['.env']

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_files, extra='ignore', case_sensitive=False)
    app_name: str = 'CargoProof AI'
    frontend_origins: str = 'http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173'
    demo_mode: bool = True
    storage_mode: str = 'auto'  # auto: Supabase when configured, otherwise persistent SQLite
    sqlite_path: str = str(_root_dir / 'data' / 'cargoproof.db')
    firebase_project_id: str = ''
    google_application_credentials: str = ''
    supabase_url: str = ''
    supabase_anon_key: str = ''
    supabase_jwt_secret: str = ''
    supabase_jwt_audience: str = 'authenticated'
    supabase_service_role_key: str = ''
    live_provider_mode: bool = False
    provider_timeout_seconds: int = 12
    provider_max_retries: int = 1
    strale_api_base: str = ''
    strale_api_key: str = ''
    strale_endpoint: str = ''
    aisfleet_api_base: str = ''
    aisfleet_api_key: str = ''
    aisfleet_endpoint: str = ''
    synthora_api_base: str = ''
    synthora_api_key: str = ''
    synthora_endpoint: str = ''
    default_markup_percent: float = 30
    processing_allowance_usd: float = .006
    tax_percent: float = 0
    quote_ttl_minutes: int = 15
    live_payments_enabled: bool = False
    base_chain_id: int = 84532
    base_rpc_url: str = ''
    base_usdc_address: str = ''
    cargoproof_treasury_address: str = ''
    max_payment_usd: float = 25
    max_daily_agent_spend_usd: float = 100
    max_agent_budget_usd: float = 25
    max_agent_requests: int = 25
    x402_enabled: bool = False
    x402_facilitator_url: str = 'https://facilitator.goplausible.xyz'
    test_provider_enabled: bool = False
    test_provider_pay_to: str = ''
    test_provider_base_url: str = 'http://127.0.0.1:8000'
    test_provider_price_usd: float = Field(default=0.01,gt=0,le=10)
    x402_network: str = 'algorand:SGO1GKSzyE7IEPItTxCByw9x8FmnrCDexi9/cOUJOiI='
    x402_asset_id: int = 10458941
    x402_pay_to: str = ''
    x402_private_key: str = ''
    x402_avm_mnemonic: str = ''
    algorand_network: str = 'testnet'
    algorand_algod_url: str = 'https://testnet-api.algonode.cloud'
    algorand_algod_token: str = ''
    algorand_indexer_url: str = 'https://testnet-idx.algonode.cloud'
    algorand_app_id: int = 0
    algorand_usdc_asset_id: int = 10458941
    algorand_verifier_mnemonic: str = ''

settings = Settings()
