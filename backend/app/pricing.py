from uuid import uuid4
from datetime import datetime,timezone,timedelta
from .config import settings
# Planning-only catalog. Provider prices must be read from the provider's actual x402 402 response.
CATALOG={'container_tracking':0.054,'vessel_position':0.010,'port_calls':0.020,'inspection':0.030,'shipping_documents':0.030}
def quote():
    upstream=sum(CATALOG.values());processing=settings.processing_allowance_usd;markup=upstream*settings.default_markup_percent/100
    taxable=upstream+processing+markup;tax=taxable*settings.tax_percent/100
    return {'id':str(uuid4()),'currency':'USD','provider_costs':[{'service':k,'estimated_usd':v,'price_source':'ILLUSTRATIVE_NOT_LIVE'} for k,v in CATALOG.items()],
      'upstream_estimate_usd':round(upstream,6),'processing_allowance_usd':round(processing,6),'markup_percent':settings.default_markup_percent,
      'markup_usd':round(markup,6),'tax_percent':settings.tax_percent,'tax_usd':round(tax,6),'total_usd':round(taxable+tax,6),
      'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=settings.quote_ttl_minutes)).isoformat(),'status':'ESTIMATE_PENDING_PAYMENT'}
