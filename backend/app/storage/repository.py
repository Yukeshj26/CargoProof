"""Persistent repository: Supabase PostgREST when configured, SQLite for local development.
SQLite is a durable local fallback, not an in-memory production database.
"""
import json, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Any
import httpx
from ..config import settings

class Repository:
    def __init__(self):
        self.remote = bool(settings.supabase_url and settings.supabase_service_role_key and settings.storage_mode != 'sqlite')
        self.db_path = Path(settings.sqlite_path)
        if not self.remote:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_sqlite()

    def _connect(self):
        conn=sqlite3.connect(self.db_path, timeout=20)
        conn.row_factory=sqlite3.Row
        conn.execute('PRAGMA journal_mode=WAL')
        conn.execute('PRAGMA foreign_keys=ON')
        return conn

    def _init_sqlite(self):
        with self._connect() as c:
            c.executescript('''
            CREATE TABLE IF NOT EXISTS shipments(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS quotations(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,shipment_id TEXT,data TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,shipment_id TEXT,quote_id TEXT,data TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS transactions(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,quote_id TEXT NOT NULL,tx_hash TEXT UNIQUE,data TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS agent_jobs(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,quote_id TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,quote_id TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS provider_payments(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,quote_id TEXT NOT NULL,tx_hash TEXT UNIQUE,data TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit_logs(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id TEXT,action TEXT NOT NULL,metadata TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS shipment_documents(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,shipment_id TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS escrow_records(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,app_id INTEGER NOT NULL,nonce TEXT NOT NULL,data TEXT NOT NULL,created_at TEXT NOT NULL,UNIQUE(user_id,app_id));
            ''')

    def _request(self, method, table, *, params=None, payload=None, prefer='return=representation'):
        url=f"{settings.supabase_url.rstrip('/')}/rest/v1/{table}"
        headers={'apikey':settings.supabase_service_role_key,'Authorization':f'Bearer {settings.supabase_service_role_key}','Content-Type':'application/json','Prefer':prefer}
        with httpx.Client(timeout=15) as client:
            r=client.request(method,url,params=params,json=payload,headers=headers)
        if r.is_error:
            raise RuntimeError(f'Supabase {table} {method} failed ({r.status_code}): {r.text[:400]}')
        return r.json() if r.content else []

    def _insert(self, table, row): return self._request('POST',table,payload=row)
    def _select(self, table, params): return self._request('GET',table,params=params)

    def save_shipment(self,user_id,data):
        now=datetime.now(timezone.utc).isoformat(); sid=data.get('id')
        if self.remote:
            row={k:v for k,v in data.items() if k!='id'}; row.update(user_id=user_id)
            out=self._insert('shipments',row); return out[0]
        sid=sid or __import__('uuid').uuid4().hex
        with self._connect() as c:c.execute('INSERT OR REPLACE INTO shipments VALUES(?,?,?,?)',(sid,user_id,json.dumps(data),now))
        return {'id':sid,'user_id':user_id,**data,'created_at':now}

    def get_shipment(self,shipment_id,user_id):
        if self.remote:
            rows=self._select('shipments',{'id':f'eq.{shipment_id}','user_id':f'eq.{user_id}','select':'*','limit':'1'})
            return rows[0] if rows else None
        with self._connect() as c:r=c.execute('SELECT data FROM shipments WHERE id=? AND user_id=?',(shipment_id,user_id)).fetchone()
        return json.loads(r['data']) if r else None

    def save_document(self,user_id,shipment_id,record):
        now=datetime.now(timezone.utc).isoformat()
        if self.remote:
            self._insert('shipment_documents',{'id':record['id'],'user_id':user_id,'shipment_id':shipment_id,'storage_path':record['storage_path'],'original_filename':record['original_filename'],'mime_type':record['mime_type'],'sha256':record['sha256'],'extracted_text':record.get('extracted_text',''),'extracted_fields':record.get('extracted_fields',{})})
        else:
            with self._connect() as c:c.execute('INSERT INTO shipment_documents VALUES(?,?,?,?,?)',(record['id'],user_id,shipment_id,json.dumps(record),now))
        return record

    def list_documents(self,shipment_id,user_id):
        if self.remote:
            return self._select('shipment_documents',{'shipment_id':f'eq.{shipment_id}','user_id':f'eq.{user_id}','select':'*','order':'uploaded_at.desc'})
        with self._connect() as c:rows=c.execute('SELECT data FROM shipment_documents WHERE shipment_id=? AND user_id=? ORDER BY created_at DESC',(shipment_id,user_id)).fetchall()
        return [json.loads(x['data']) for x in rows]

    def get_document(self,document_id,user_id):
        if self.remote:
            rows=self._select('shipment_documents',{'id':f'eq.{document_id}','user_id':f'eq.{user_id}','select':'*','limit':'1'})
            return rows[0] if rows else None
        with self._connect() as c:r=c.execute('SELECT data FROM shipment_documents WHERE id=? AND user_id=?',(document_id,user_id)).fetchone()
        return json.loads(r['data']) if r else None

    def save_quote(self,user_id,q,shipment_id=None):
        now=datetime.now(timezone.utc).isoformat()
        if self.remote:
            row={'id':q['id'],'user_id':user_id,'shipment_id':shipment_id,'breakdown':q,'total_usd':q['total_usd'],'status':q.get('status','PENDING'),'expires_at':q['expires_at']}
            return self._insert('quotations',row)[0]
        with self._connect() as c:c.execute('INSERT OR REPLACE INTO quotations VALUES(?,?,?,?,?)',(q['id'],user_id,shipment_id,json.dumps(q),now))
        return q

    def get_quote(self,qid,user_id):
        if self.remote:
            rows=self._select('quotations',{'id':f'eq.{qid}','user_id':f'eq.{user_id}','select':'*','limit':'1'})
            if not rows:return None
            return rows[0].get('breakdown') or rows[0]
        with self._connect() as c:r=c.execute('SELECT data FROM quotations WHERE id=? AND user_id=?',(qid,user_id)).fetchone()
        return json.loads(r['data']) if r else None

    def save_report(self,user_id,report,shipment_id=None):
        now=datetime.now(timezone.utc).isoformat()
        if self.remote:
            row={'id':report['id'],'user_id':user_id,'shipment_id':shipment_id,'evidence_hash':report['evidence_hash'],'decision':report['decision'],'risk_score':report['risk_score'],'source_type':report['source_type'],'report':report}
            self._insert('verification_reports',row)
            for rule in report.get('rules',[]):
                self._insert('verification_rule_results',{'report_id':report['id'],'rule_name':rule['rule'],'result':rule['result'],'severity':rule['severity'],'explanation':rule['explanation'],'evidence_refs':rule.get('evidence_references',[])})
            return report
        with self._connect() as c:c.execute('INSERT OR REPLACE INTO reports VALUES(?,?,?,?,?,?)',(report['id'],user_id,shipment_id,report.get('quote_id'),json.dumps(report),now))
        return report

    def get_report(self,rid,user_id):
        if self.remote:
            rows=self._select('verification_reports',{'id':f'eq.{rid}','user_id':f'eq.{user_id}','select':'report','limit':'1'})
            return rows[0]['report'] if rows else None
        with self._connect() as c:r=c.execute('SELECT data FROM reports WHERE id=? AND user_id=?',(rid,user_id)).fetchone()
        return json.loads(r['data']) if r else None

    def list_reports(self,user_id,limit=100):
        if self.remote:
            rows=self._select('verification_reports',{'user_id':f'eq.{user_id}','select':'report,created_at','order':'created_at.desc','limit':str(limit)})
            return [x['report'] for x in rows]
        with self._connect() as c:rows=c.execute('SELECT data FROM reports WHERE user_id=? ORDER BY created_at DESC LIMIT ?',(user_id,limit)).fetchall()
        return [json.loads(x['data']) for x in rows]

    def has_confirmed_payment(self,user_id,quote_id):
        if self.remote:
            rows=self._select('transactions',{'user_id':f'eq.{user_id}','quotation_id':f'eq.{quote_id}','status':'eq.CONFIRMED','select':'id','limit':'1'})
            return bool(rows)
        with self._connect() as c:r=c.execute('SELECT 1 FROM transactions WHERE user_id=? AND quote_id=? LIMIT 1',(user_id,quote_id)).fetchone()
        return bool(r)

    def daily_provider_spend(self,user_id):
        if self.remote:
            today=datetime.now(timezone.utc).date().isoformat()
            rows=self._select('provider_payments',{'user_id':f'eq.{user_id}','created_at':f'gte.{today}T00:00:00Z','status':'eq.CONFIRMED','select':'amount'})
            return sum(float(x.get('amount') or 0) for x in rows)
        with self._connect() as c:rows=c.execute('SELECT data FROM provider_payments WHERE user_id=? AND created_at>=?',(user_id,datetime.now(timezone.utc).date().isoformat()+'T00:00:00+00:00')).fetchall()
        return sum(float(json.loads(x['data']).get('amount_usd') or 0) for x in rows)

    def transaction_exists(self,tx_hash):
        if self.remote:return bool(self._select('transactions',{'tx_hash':f'eq.{tx_hash}','select':'id','limit':'1'}))
        with self._connect() as c:r=c.execute('SELECT 1 FROM transactions WHERE tx_hash=? LIMIT 1',(tx_hash,)).fetchone()
        return bool(r)

    def get_customer_payment(self,user_id,quote_id):
        if self.remote:
            rows=self._select('transactions',{'user_id':f'eq.{user_id}','quotation_id':f'eq.{quote_id}','status':'eq.CONFIRMED','select':'*','order':'created_at.desc','limit':'1'})
            return rows[0] if rows else None
        with self._connect() as c:r=c.execute('SELECT data FROM transactions WHERE user_id=? AND quote_id=? ORDER BY created_at DESC LIMIT 1',(user_id,quote_id)).fetchone()
        return json.loads(r['data']) if r else None

    def save_transaction(self,user_id,quote_id,result):
        now=datetime.now(timezone.utc).isoformat(); txid=__import__('uuid').uuid4().hex
        if self.remote:
            self._insert('transactions',{'user_id':user_id,'quotation_id':quote_id,'chain_id':result.get('chain_id'),'tx_hash':result.get('tx_hash'),'token_address':result.get('token'),'sender':result.get('sender'),'recipient':result.get('recipient'),'amount':result.get('amount_usd'),'status':result.get('status','CONFIRMED')})
        else:
            with self._connect() as c:c.execute('INSERT INTO transactions VALUES(?,?,?,?,?,?)',(txid,user_id,quote_id,result.get('tx_hash'),json.dumps(result),now))

    def save_job(self,user_id,quote_id,job,shipment_id=None):
        now=datetime.now(timezone.utc).isoformat()
        if self.remote:
            self._insert('agent_jobs',{'id':job['id'],'user_id':user_id,'quotation_id':quote_id,'shipment_id':shipment_id,'status':job['status'],'budget_usd':job['budget_usd'],'spent_usd':job['spent_usd'],'logs':job.get('logs',[]),'result':job})
        else:
            with self._connect() as c:c.execute('INSERT OR REPLACE INTO agent_jobs VALUES(?,?,?,?,?)',(job['id'],user_id,quote_id,json.dumps(job),now))
        for payment in job.get('payment_records',[]):
            if self.remote:
                self._insert('provider_payments',{'user_id':user_id,'quotation_id':quote_id,'provider':payment.get('provider','unknown'),'endpoint_id':payment.get('capability'),'network':payment.get('network'),'token':payment.get('asset'),'amount':payment.get('amount_usd'),'tx_hash':payment.get('tx_id'),'status':payment.get('status','CONFIRMED'),'idempotency_key':payment.get('tx_id'),'facilitator_response':payment.get('settlement_receipt')})
            else:
                with self._connect() as c:c.execute('INSERT OR IGNORE INTO provider_payments VALUES(?,?,?,?,?,?)',(__import__('uuid').uuid4().hex,user_id,quote_id,payment.get('tx_id'),json.dumps(payment),now))
        for ev in job.get('evidence_records',[]):
            if self.remote:
                self._insert('evidence',{'user_id':user_id,'shipment_id':shipment_id,'provider':ev.get('provider'),'endpoint_id':ev.get('endpoint_id'),'source_type':ev.get('source_type','SYNTHETIC_TEST_CASE'),'observed_at':ev.get('observed_at'),'raw_evidence':ev.get('raw'),'normalized_evidence':ev.get('normalized',{}),'sha256':ev.get('sha256','0'*64)})
            else:
                with self._connect() as c:c.execute('INSERT INTO evidence VALUES(?,?,?,?,?)',(__import__('uuid').uuid4().hex,user_id,quote_id,json.dumps(ev),now))

    def save_escrow_record(self,user_id,record):
        now=datetime.now(timezone.utc).isoformat()
        if self.remote:
            row={'user_id':user_id,'network':'algorand-testnet','app_id':record['app_id'],'tx_id':record.get('tx_id'),'evidence_hash':record.get('evidence_hash'),'nonce':record['nonce'],'expires_at':record['expires_at'],'status':record['status'],'beneficiary':record.get('beneficiary'),'depositor':record.get('depositor'),'app_address':record.get('app_address'),'asset_id':record.get('asset_id'),'amount_base_units':record.get('amount_base_units'),'confirmed_round':record.get('confirmed_round'),'explorer_url':record.get('explorer_url')}
            return self._insert('escrow_records',row)[0]
        with self._connect() as c:c.execute('INSERT OR REPLACE INTO escrow_records VALUES(?,?,?,?,?,?)',(record['id'],user_id,record['app_id'],record['nonce'],json.dumps(record),now))
        return record

    def list_escrow_records(self,user_id):
        if self.remote:return self._select('escrow_records',{'user_id':f'eq.{user_id}','select':'*','order':'created_at.desc'})
        with self._connect() as c:rows=c.execute('SELECT data FROM escrow_records WHERE user_id=? ORDER BY created_at DESC',(user_id,)).fetchall()
        return [json.loads(x['data']) for x in rows]

    def update_escrow_record(self,user_id,app_id,updates):
        if self.remote:
            self._request('PATCH','escrow_records',params={'user_id':f'eq.{user_id}','app_id':f'eq.{app_id}'},payload=updates)
            return
        with self._connect() as c:r=c.execute('SELECT data FROM escrow_records WHERE user_id=? AND app_id=?',(user_id,app_id)).fetchone()
        if not r:return
        data=json.loads(r['data']);data.update(updates)
        with self._connect() as c:c.execute('UPDATE escrow_records SET data=? WHERE user_id=? AND app_id=?',(json.dumps(data),user_id,app_id))

    def admin_metrics(self):
        if self.remote:
            profiles=self._select('profiles',{'select':'id,role','limit':'10000'})
            shipments=self._select('shipments',{'select':'id','limit':'10000'})
            reports=self._select('verification_reports',{'select':'id,decision','limit':'10000'})
            customer=self._select('transactions',{'select':'amount,status','limit':'10000'})
            provider=self._select('provider_payments',{'select':'amount,status','limit':'10000'})
            revenue=sum(float(x.get('amount') or 0) for x in customer if x.get('status')=='CONFIRMED')
            costs=sum(float(x.get('amount') or 0) for x in provider if x.get('status')=='CONFIRMED')
            return {'users':len(profiles),'shipments':len(shipments),'reports':len(reports),'verified':sum(x.get('decision')=='VERIFIED' for x in reports),'on_hold':sum(x.get('decision')=='HOLD' for x in reports),'rejected':sum(x.get('decision')=='REJECTED' for x in reports),'customer_revenue_usd':round(revenue,6),'provider_costs_usd':round(costs,6),'gross_contribution_usd':round(revenue-costs,6)}
        with self._connect() as c:
            users=c.execute('SELECT COUNT(DISTINCT user_id) n FROM shipments').fetchone()['n']
            shipments=c.execute('SELECT COUNT(*) n FROM shipments').fetchone()['n']
            reports=c.execute('SELECT data FROM reports').fetchall()
            customer=c.execute('SELECT data FROM transactions').fetchall();provider=c.execute('SELECT data FROM provider_payments').fetchall()
        decoded=[json.loads(x['data']) for x in reports]
        revenue=sum(float(json.loads(x['data']).get('amount_usd') or 0) for x in customer)
        costs=sum(float(json.loads(x['data']).get('amount_usd') or 0) for x in provider)
        return {'users':users,'shipments':shipments,'reports':len(decoded),'verified':sum(x.get('decision')=='VERIFIED' for x in decoded),'on_hold':sum(x.get('decision')=='HOLD' for x in decoded),'rejected':sum(x.get('decision')=='REJECTED' for x in decoded),'customer_revenue_usd':round(revenue,6),'provider_costs_usd':round(costs,6),'gross_contribution_usd':round(revenue-costs,6)}

    def audit(self,user_id,action,metadata=None):
        now=datetime.now(timezone.utc).isoformat()
        if self.remote:self._insert('audit_logs',{'user_id':user_id,'action':action,'metadata':metadata or {}})
        else:
            with self._connect() as c:c.execute('INSERT INTO audit_logs(user_id,action,metadata,created_at) VALUES(?,?,?,?)',(user_id,action,json.dumps(metadata or {}),now))

repo=Repository()
