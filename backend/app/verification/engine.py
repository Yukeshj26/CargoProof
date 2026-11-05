"""Deterministic, three-state shipment evidence evaluation.
The score is a rule-weighted severity index, NOT a calibrated fraud probability.
"""
from datetime import datetime, timezone
import hashlib, json

RULES = [
 ('SHIPMENT_EXISTS','CRITICAL'),('VESSEL_EXISTS','CRITICAL'),('CONTAINER_EXISTS','CRITICAL'),
 ('VESSEL_CONTAINER_ASSOCIATION','CRITICAL'),('VESSEL_IMO_CONSISTENCY','CRITICAL'),
 ('ORIGIN_CONSISTENCY','HIGH'),('DESTINATION_CONSISTENCY','CRITICAL'),
 ('VESSEL_STATUS_CONSISTENCY','CRITICAL'),('PORT_EVENT_CONSISTENCY','HIGH'),
 ('GPS_ROUTE_CONSISTENCY','HIGH'),('INSPECTION_VERIFICATION','MEDIUM'),
 ('DOCUMENT_CARGO_CONSISTENCY','HIGH'),('EVIDENCE_FRESHNESS','LOW')]
WEIGHTS={'CRITICAL':40,'HIGH':25,'MEDIUM':12,'LOW':5}

def _dt(value):
    if not value:return None
    try:
        d=datetime.fromisoformat(str(value).replace('Z','+00:00'))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (ValueError,TypeError):return None

def _norm(v):return str(v or '').strip().casefold()
def _result(rule, severity, state, explanation, refs=()):
    return {'rule':rule,'result':state,'passed':state=='PASS','severity':severity,'explanation':explanation,'evidence_references':list(refs)}

def verify(shipment, evidence):
    s={**(evidence.get('shipment') or {}), **{k:v for k,v in (shipment or {}).items() if v is not None}}; c=evidence.get('container') or {}; v=evidence.get('vessel') or {}
    docs=evidence.get('documents') or []; events=evidence.get('port_events') or []; gps=evidence.get('gps') or []; observations=evidence.get('provider_observations') or []
    def observed(entity,field):
        values=[]
        for observation in observations:
            value=((observation.get('evidence') or {}).get(entity) or {}).get(field)
            if value not in (None,''):values.append(value)
        return values
    out=[]
    out.append(_result('SHIPMENT_EXISTS','CRITICAL','PASS' if s.get('container_number') else 'INSUFFICIENT','Shipment claim is present' if s.get('container_number') else 'No shipment reference/container claim was supplied',['shipment'] if s else []))
    out.append(_result('VESSEL_EXISTS','CRITICAL','PASS' if v.get('imo') or v.get('name') else 'INSUFFICIENT','Vessel identity evidence is present' if v.get('imo') or v.get('name') else 'No independent vessel identity evidence',['vessel'] if v else []))
    out.append(_result('CONTAINER_EXISTS','CRITICAL','PASS' if c.get('container_number') else 'INSUFFICIENT','Container evidence is present' if c.get('container_number') else 'No container tracking evidence',['container'] if c else []))
    si=_norm(s.get('vessel_imo'));container_imos=[_norm(x) for x in [c.get('vessel_imo'),*observed('container','vessel_imo')] if x];vessel_imos_for_link=[_norm(x) for x in [v.get('imo'),*observed('vessel','imo')] if x]
    if si and container_imos:state='PASS' if all(x==si for x in container_imos) else 'FAIL'
    elif container_imos and vessel_imos_for_link:state='PASS' if all(x==container_imos[0] for x in container_imos+vessel_imos_for_link) else 'FAIL'
    else:state='INSUFFICIENT'
    out.append(_result('VESSEL_CONTAINER_ASSOCIATION','CRITICAL',state,'Container is associated with the claimed vessel or independently matching vessel identity evidence' if state=='PASS' else ('Vessel/container association cannot be established' if state=='INSUFFICIENT' else 'Container and vessel evidence identify different vessels'),['shipment','container','vessel']))
    vessel_imos=[_norm(x) for x in [v.get('imo'),*observed('vessel','imo')] if x]; state='INSUFFICIENT' if not s.get('vessel_imo') or not vessel_imos else ('PASS' if all(x==_norm(s.get('vessel_imo')) for x in vessel_imos) else 'FAIL')
    out.append(_result('VESSEL_IMO_CONSISTENCY','CRITICAL',state,'Vessel IMO matches shipment claim' if state=='PASS' else ('Vessel IMO comparison unavailable' if state=='INSUFFICIENT' else 'Vessel IMO contradicts shipment claim'),['shipment','vessel']))
    for key,label,sev in [('origin_port','Origin','HIGH'),('destination_port','Destination','CRITICAL')]:
        claim=_norm(s.get(key)); values=[_norm(x) for x in [c.get(key),*observed('container',key),*[d.get(key) for d in docs],*[d.get(key) for d in [z for o in observations for z in (o.get('evidence') or {}).get('documents',[])]] ] if x]
        state='INSUFFICIENT' if not claim or not values else ('PASS' if all(x==claim for x in values) else 'FAIL')
        out.append(_result('ORIGIN_CONSISTENCY' if key=='origin_port' else 'DESTINATION_CONSISTENCY',sev,state,f'{label} matches across available evidence' if state=='PASS' else (f'{label} cannot be independently compared' if state=='INSUFFICIENT' else f'{label} differs across shipment and evidence'),['shipment','container','documents']))
    claimed=_norm(s.get('claimed_status') or s.get('status')); actuals=[_norm(x) for x in [v.get('status'),*observed('vessel','status')] if x]
    if not claimed or not actuals:state='INSUFFICIENT'
    elif any(claimed in ('in_transit','underway') and actual in ('docked','moored','anchored','idle','at_berth') for actual in actuals):state='FAIL'
    else:state='PASS'
    out.append(_result('VESSEL_STATUS_CONSISTENCY','CRITICAL',state,'Observed vessel status is compatible with the shipment claim' if state=='PASS' else ('Claimed/observed status comparison unavailable' if state=='INSUFFICIENT' else 'Observed vessel status contradicts the shipment claim'),['shipment','vessel']))
    event_groups=[events] if not observations else [((o.get('evidence') or {}).get('port_events') or []) for o in observations if (o.get('evidence') or {}).get('port_events')]
    if not event_groups:event_groups=[events]
    valid_events=[e for group in event_groups for e in group if _dt(e.get('timestamp'))]
    if not valid_events:state='INSUFFICIENT'
    else:
        bad=False
        for group in event_groups:
            ordered=[e for e in group if _dt(e.get('timestamp'))]
            for a,b in zip(ordered,ordered[1:]):
                if _dt(b['timestamp']) < _dt(a['timestamp']):bad=True
                if _norm(a.get('event_type'))=='departure' and _norm(b.get('event_type'))=='arrival' and _norm(a.get('port'))==_norm(b.get('port')):bad=True
        state='FAIL' if bad else 'PASS'
    out.append(_result('PORT_EVENT_CONSISTENCY','HIGH',state,'Available port events are chronologically coherent' if state=='PASS' else ('No timestamped port events are available' if state=='INSUFFICIENT' else 'Port event sequence contains a contradiction'),['port_events']))
    coords=[]
    for g in gps:
        try:
            lat,lon=float(g['lat']),float(g['lon'])
            if -90<=lat<=90 and -180<=lon<=180:coords.append(g)
        except (KeyError,TypeError,ValueError):pass
    route_flags=[g.get('route_consistency') for g in gps if 'route_consistency' in g]
    route_states=[_norm(g.get('route_status')) for g in gps if g.get('route_status')]
    if not coords or (not route_flags and not route_states):state='INSUFFICIENT'
    elif any(flag is False for flag in route_flags) or any(x in ('off_route','inconsistent','deviation') for x in route_states):state='FAIL'
    elif all(flag is True for flag in route_flags) and all(x in ('on_route','consistent','within_corridor') for x in route_states):state='PASS'
    elif route_flags and not route_states and all(flag is True for flag in route_flags):state='PASS'
    elif route_states and not route_flags and all(x in ('on_route','consistent','within_corridor') for x in route_states):state='PASS'
    else:state='INSUFFICIENT'
    out.append(_result('GPS_ROUTE_CONSISTENCY','HIGH',state,'Provider explicitly confirms route consistency for valid vessel-position observations; this is not container GPS' if state=='PASS' else ('Provider reports a route deviation or inconsistency' if state=='FAIL' else 'Valid vessel coordinates exist but no explicit route-consistency evidence is available'),['gps']))
    inspection=evidence.get('inspection') or {}; inspection_values=[_norm(x) for x in [inspection.get('result') or inspection.get('status'),*observed('inspection','result'),*observed('inspection','status')] if x]
    if not inspection_values:state='INSUFFICIENT'
    elif any(x in ('failed','fail','rejected','non_compliant') for x in inspection_values):state='FAIL'
    elif all(x in ('passed','pass','clear','compliant') for x in inspection_values):state='PASS'
    else:state='INSUFFICIENT'
    out.append(_result('INSPECTION_VERIFICATION','MEDIUM',state,'Inspection evidence reports a pass' if state=='PASS' else ('Inspection evidence is absent or inconclusive' if state=='INSUFFICIENT' else 'Inspection evidence reports a failure'),['inspection'] if inspection else []))
    expected={'container_number':s.get('container_number'),'origin_port':s.get('origin_port'),'destination_port':s.get('destination_port'),'declared_cargo':s.get('cargo_description')}
    comparisons=[]
    for d in docs:
        for field,want in expected.items():
            got=d.get(field)
            if got and want:comparisons.append(_norm(got)==_norm(want))
    cargo_c_values=[_norm(x) for x in [c.get('cargo_description'),*observed('container','cargo_description')] if x]; cargo_s=_norm(s.get('cargo_description'))
    if cargo_s and cargo_c_values:comparisons.extend(x==cargo_s for x in cargo_c_values)
    state='INSUFFICIENT' if not comparisons else ('PASS' if all(comparisons) else 'FAIL')
    out.append(_result('DOCUMENT_CARGO_CONSISTENCY','HIGH',state,'Available document/container cargo fields match shipment claims' if state=='PASS' else ('No comparable document or cargo evidence is available' if state=='INSUFFICIENT' else 'Document or cargo fields contradict shipment claims'),['shipment','container','documents']))
    timestamps=[]
    for item in [v,*gps,*events,*docs,*[z for o in observations for z in [((o.get('evidence') or {}).get('vessel') or {}),*((o.get('evidence') or {}).get('gps') or []),*((o.get('evidence') or {}).get('port_events') or []),*((o.get('evidence') or {}).get('documents') or [])]]]:
        d=_dt(item.get('observed_at') or item.get('last_updated') or item.get('timestamp') or item.get('issued_at'))
        if d:timestamps.append(d)
    if not timestamps:state='INSUFFICIENT'
    else:
        ages=[(datetime.now(timezone.utc)-stamp).total_seconds() for stamp in timestamps]
        state='PASS' if all(-300<=age<=72*3600 for age in ages) else 'FAIL'
    out.append(_result('EVIDENCE_FRESHNESS','LOW',state,'Newest timestamped evidence is within 72 hours' if state=='PASS' else ('Evidence timestamps are missing or invalid' if state=='INSUFFICIENT' else 'Newest evidence is older than 72 hours'),['vessel','gps','port_events','documents']))
    failed=[r for r in out if r['result']=='FAIL']; insufficient=[r for r in out if r['result']=='INSUFFICIENT']
    if any(r['severity']=='CRITICAL' for r in failed):decision='REJECTED'
    elif failed:decision='HOLD'
    elif insufficient:decision='INSUFFICIENT_DATA'
    else:decision='VERIFIED'
    penalty=sum(WEIGHTS[r['severity']] for r in failed)+sum(max(1,WEIGHTS[r['severity']]//2) for r in insufficient)
    canonical=json.dumps(evidence,sort_keys=True,separators=(',',':'),default=str).encode()
    return {'decision':decision,'risk_score':min(100,penalty),'rules':out,'evidence_hash':hashlib.sha256(canonical).hexdigest(),'verified_at':datetime.now(timezone.utc).isoformat(),'evidence_classification':evidence.get('source_type','UNKNOWN')}
