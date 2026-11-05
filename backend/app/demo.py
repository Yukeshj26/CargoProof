"""Explicitly synthetic fixture used only when DEMO_MODE=true."""
from datetime import datetime,timezone,timedelta

def synthetic_evidence(inp):
    get = lambda k, default='': (
        (inp.get(k) if isinstance(inp, dict) else getattr(inp, k, default)) or default
    )
    now=datetime.now(timezone.utc); stamp=now.isoformat()
    container=str(get('container_number','MSCU1234567')).upper()
    imo=str(get('vessel_imo','9876543') or '9876543')
    origin=str(get('origin_port','Chennai') or 'Chennai')
    destination=str(get('destination_port','Singapore') or 'Singapore')
    cargo=str(get('cargo_description','General cargo') or 'General cargo')
    return {'source_type':'SYNTHETIC_TEST_CASE','shipment':{'container_number':container,'vessel_imo':imo,'origin_port':origin,'destination_port':destination,'claimed_status':'IN_TRANSIT','cargo_description':cargo},
      'container':{'container_number':container,'vessel_imo':imo,'origin_port':origin,'destination_port':destination,'cargo_description':cargo,'observed_at':stamp},
      'vessel':{'imo':imo,'name':'SYNTHETIC TEST VESSEL','status':'UNDERWAY','last_updated':stamp,'observed_at':stamp},
      'port_events':[{'event_type':'DEPARTURE','port':origin,'timestamp':(now-timedelta(days=1)).isoformat(),'observed_at':stamp}],
      'gps':[{'lat':13.1,'lon':80.3,'timestamp':stamp,'observed_at':stamp,'observation_scope':'VESSEL_AIS','route_consistency':True}],
      'inspection':{'result':'passed','observed_at':stamp,'source':'SYNTHETIC_TEST_FIXTURE'},
      'documents':[{'container_number':container,'origin_port':origin,'destination_port':destination,'declared_cargo':cargo,'observed_at':stamp,'source':'SYNTHETIC_TEST_FIXTURE'}]}
