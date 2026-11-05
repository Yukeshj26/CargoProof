from fastapi.testclient import TestClient
from app import main
from app.storage.repository import Repository
from app.config import settings

def test_local_end_to_end_persists_report_and_document(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,'demo_mode',True)
    monkeypatch.setattr(settings,'test_provider_enabled',False)
    monkeypatch.setattr(settings,'supabase_url','')
    monkeypatch.setattr(settings,'supabase_service_role_key','')
    monkeypatch.setattr(settings,'storage_mode','sqlite')
    monkeypatch.setattr(settings,'sqlite_path',str(tmp_path/'cargoproof.db'))
    monkeypatch.setattr(main,'repo',Repository())
    client=TestClient(main.app)
    health=client.get('/health');assert health.status_code==200 and health.json()['storage']=='persistent_sqlite'
    assert client.get('/api/test-provider/evidence?resource_id=MSCU1234567&capability=container_tracking').status_code in (402, 404)
    quote_response=client.post('/api/quotes',json={'container_number':'MSCU1234567','vessel_imo':'','booking_number':'','bill_of_lading':'','origin_port':'Chennai','destination_port':'Singapore','cargo_description':'General cargo'})
    assert quote_response.status_code==200,quote_response.text
    quote=quote_response.json()
    upload=client.post(f"/api/shipments/{quote['shipment_id']}/documents",files={'file':('bill.pdf',b'%PDF-1.4\nDemo file','application/pdf')})
    assert upload.status_code==200,upload.text
    listing=client.get(f"/api/shipments/{quote['shipment_id']}/documents")
    assert listing.status_code==200,listing.text
    assert listing.json()['total_documents']==1
    document=listing.json()['documents'][0]
    assert document['id']==upload.json()['id']
    assert document['original_filename']=='bill.pdf'
    assert document['sha256']==upload.json()['sha256']
    assert document['download_endpoint']==f"/api/documents/{upload.json()['id']}/download"
    assert 'storage_path' not in document
    assert 'extracted_text' not in document
    report_response=client.post(f"/api/verify/{quote['id']}?budget_usd=1.00")
    assert report_response.status_code==200,report_response.text
    report=report_response.json()
    assert report['source_type']=='SYNTHETIC_TEST_CASE'
    assert len(report['rules'])==13
    assert report['decision'] in ('VERIFIED','HOLD','REJECTED','INSUFFICIENT_DATA')
    assert client.get(f"/api/reports/{report['id']}").status_code==200
    integrity=client.get(f"/api/reports/{report['id']}/integrity")
    assert integrity.status_code==200 and integrity.json()['integrity_match'] is True
    pdf=client.get(f"/api/reports/{report['id']}/pdf")
    assert pdf.status_code==200 and pdf.headers['content-type']=='application/pdf'
    assert len(client.get('/api/history').json())==1
    # New repository instance proves data survives an application/repository restart.
    second=Repository()
    assert second.get_report(report['id'],'demo-user')['evidence_hash']==report['evidence_hash']
    assert second.get_document(upload.json()['id'],'demo-user')['sha256']==upload.json()['sha256']
