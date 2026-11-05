create extension if not exists pgcrypto;
create table if not exists public.profiles (id uuid primary key references auth.users(id) on delete cascade, full_name text, role text not null default 'user' check(role in ('user','admin')), created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.wallets (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, address text not null, chain_id bigint not null, verified_at timestamptz, created_at timestamptz not null default now(), unique(user_id,address,chain_id));
create table if not exists public.shipments (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, container_number text not null, vessel_imo text, booking_number text, bill_of_lading text, origin_port text, destination_port text, cargo_description text, created_at timestamptz not null default now());
create table if not exists public.quotations (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, shipment_id uuid references public.shipments(id) on delete set null, breakdown jsonb not null, total_usd numeric(18,6) not null check(total_usd>=0), status text not null default 'PENDING', expires_at timestamptz not null, created_at timestamptz not null default now());
create table if not exists public.transactions (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, quotation_id uuid references public.quotations(id), chain_id bigint, tx_hash text, token_address text, sender text, recipient text, amount numeric(24,8), status text not null, idempotency_key text unique, created_at timestamptz not null default now(), unique(chain_id,tx_hash));
create table if not exists public.provider_payments (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, quotation_id uuid references public.quotations(id), provider text not null, endpoint_id text, network text, token text, amount numeric(24,8), tx_hash text, status text not null, idempotency_key text unique, created_at timestamptz not null default now());
create table if not exists public.agent_jobs (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, shipment_id uuid references public.shipments(id), quotation_id uuid references public.quotations(id), status text not null, budget_usd numeric(18,6) not null default 0, spent_usd numeric(18,6) not null default 0, created_at timestamptz not null default now(), updated_at timestamptz not null default now());
create table if not exists public.evidence (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, shipment_id uuid references public.shipments(id) on delete cascade, provider text, endpoint_id text, source_type text not null check(source_type in ('LIVE_OBSERVATION','HISTORICAL','SYNTHETIC_TEST_CASE','DOCUMENT_PROVIDED','ISSUER_VERIFIED')), observed_at timestamptz, retrieved_at timestamptz not null default now(), payment_reference uuid references public.provider_payments(id), raw_evidence jsonb, normalized_evidence jsonb not null, sha256 text not null, version integer not null default 1, created_at timestamptz not null default now());
create table if not exists public.verification_reports (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, shipment_id uuid references public.shipments(id) on delete set null, evidence_hash text not null, decision text not null, risk_score integer not null check(risk_score between 0 and 100), source_type text not null, report jsonb not null, created_at timestamptz not null default now());
create table if not exists public.verification_rule_results (id uuid primary key default gen_random_uuid(), report_id uuid not null references public.verification_reports(id) on delete cascade, rule_name text not null, result text not null, severity text not null, explanation text not null, evidence_refs jsonb not null default '[]', created_at timestamptz not null default now(), unique(report_id,rule_name));
create table if not exists public.audit_logs (id uuid primary key default gen_random_uuid(), user_id uuid references auth.users(id) on delete set null, actor_role text, action text not null, entity_type text, entity_id uuid, metadata jsonb not null default '{}', created_at timestamptz not null default now());
create table if not exists public.escrow_records (id uuid primary key default gen_random_uuid(), user_id uuid not null references auth.users(id) on delete cascade, network text not null default 'algorand-testnet', app_id bigint, tx_id text, evidence_hash text, nonce text not null, expires_at timestamptz not null, status text not null, created_at timestamptz not null default now(), unique(network,nonce));
create index if not exists idx_shipments_user_created on public.shipments(user_id,created_at desc);
create index if not exists idx_reports_user_created on public.verification_reports(user_id,created_at desc);
create index if not exists idx_evidence_shipment on public.evidence(shipment_id,version desc);
create index if not exists idx_transactions_user on public.transactions(user_id,created_at desc);

-- RLS: clients can read their own records. All writes to financial, agent, evidence,
-- report, audit and escrow tables are server-only (service role), never direct client inserts.
do $$ declare t text; begin
  foreach t in array array['wallets','shipments','quotations','transactions','provider_payments','agent_jobs','evidence','verification_reports','audit_logs','escrow_records'] loop
    execute format('alter table public.%I enable row level security',t);
    execute format('drop policy if exists %I on public.%I',t||'_select_own',t);
    execute format('drop policy if exists %I on public.%I',t||'_insert_own',t);
    execute format('drop policy if exists %I on public.%I',t||'_update_own',t);
    execute format('create policy %I on public.%I for select using (auth.uid() = user_id)',t||'_select_own',t);
  end loop;
end $$;
alter table public.profiles enable row level security;
drop policy if exists profiles_select_own on public.profiles;
drop policy if exists profiles_update_own on public.profiles;
create policy profiles_select_own on public.profiles for select using (auth.uid()=id);
create policy profiles_update_own on public.profiles for update using (auth.uid()=id) with check (auth.uid()=id);

-- A user may edit profile fields but may never promote their own role.
create or replace function public.prevent_profile_role_escalation() returns trigger language plpgsql as $$
begin
  if coalesce(auth.role(),'') not in ('service_role','supabase_admin') and current_user not in ('postgres','supabase_admin') then
    new.role := old.role;
  end if;
  new.updated_at := now();
  return new;
end;
$$;
drop trigger if exists protect_profile_role on public.profiles;
create trigger protect_profile_role before update on public.profiles for each row execute procedure public.prevent_profile_role_escalation();


-- Automatically create a least-privilege profile for each new Supabase Auth user.
create or replace function public.handle_new_user() returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name, role) values (new.id, coalesce(new.raw_user_meta_data->>'full_name',''), 'user') on conflict (id) do nothing;
  return new;
end;
$$;
drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users for each row execute procedure public.handle_new_user();

-- CargoProof Complete additions (safe to re-run)
alter table public.shipments add column if not exists expected_departure timestamptz;
alter table public.shipments add column if not exists expected_arrival timestamptz;
alter table public.shipments add column if not exists declared_cargo_value_usd numeric(18,2) check (declared_cargo_value_usd is null or declared_cargo_value_usd >= 0);
alter table public.shipments add column if not exists beneficiary_address text;
alter table public.shipments add column if not exists claimed_status text default 'IN_TRANSIT';
alter table public.agent_jobs add column if not exists logs jsonb not null default '[]';
alter table public.agent_jobs add column if not exists result jsonb not null default '{}';
alter table public.provider_payments add column if not exists payment_requirements jsonb;
alter table public.provider_payments add column if not exists facilitator_response jsonb;
alter table public.escrow_records add column if not exists beneficiary text;
alter table public.escrow_records add column if not exists depositor text;
alter table public.escrow_records add column if not exists app_address text;
alter table public.escrow_records add column if not exists asset_id bigint;
alter table public.escrow_records add column if not exists amount_base_units numeric(30,0);
alter table public.escrow_records add column if not exists confirmed_round bigint;
alter table public.escrow_records add column if not exists explorer_url text;

-- Rule-result rows are readable only when their parent report belongs to the caller.
alter table public.verification_rule_results enable row level security;
drop policy if exists verification_rule_results_select_own on public.verification_rule_results;
create policy verification_rule_results_select_own on public.verification_rule_results for select using (
  exists (select 1 from public.verification_reports r where r.id=report_id and r.user_id=auth.uid())
);

create table if not exists public.shipment_documents (
 id uuid primary key default gen_random_uuid(),
 user_id uuid not null references auth.users(id) on delete cascade,
 shipment_id uuid not null references public.shipments(id) on delete cascade,
 storage_path text not null,
 original_filename text not null,
 mime_type text not null,
 sha256 text not null,
 uploaded_at timestamptz not null default now(),
 extracted_text text not null default '',
 extracted_fields jsonb not null default '{}'
);
alter table public.shipment_documents add column if not exists extracted_text text not null default '';
alter table public.shipment_documents add column if not exists extracted_fields jsonb not null default '{}';
alter table public.shipment_documents enable row level security;
drop policy if exists shipment_documents_select_own on public.shipment_documents;
create policy shipment_documents_select_own on public.shipment_documents for select using(auth.uid()=user_id);
drop policy if exists shipment_documents_insert_own on public.shipment_documents;
drop policy if exists shipment_documents_delete_own on public.shipment_documents;

-- Create a private bucket. Object names must be prefixed by the authenticated user's UUID.
insert into storage.buckets(id,name,public) values('cargoproof-documents','cargoproof-documents',false)
on conflict(id) do update set public=false;
drop policy if exists cargoproof_documents_select_own on storage.objects;
create policy cargoproof_documents_select_own on storage.objects for select using(bucket_id='cargoproof-documents' and (storage.foldername(name))[1]=auth.uid()::text);
drop policy if exists cargoproof_documents_insert_own on storage.objects;
drop policy if exists cargoproof_documents_delete_own on storage.objects;

create index if not exists idx_agent_jobs_user_created on public.agent_jobs(user_id,created_at desc);
create index if not exists idx_provider_payments_user_created on public.provider_payments(user_id,created_at desc);
create index if not exists idx_escrow_user_created on public.escrow_records(user_id,created_at desc);
create unique index if not exists idx_escrow_user_app_unique on public.escrow_records(user_id,app_id);

-- Provider payment receipts are persisted independently from customer payments.
create unique index if not exists idx_provider_payments_tx_unique on public.provider_payments(tx_hash) where tx_hash is not null;

-- Sandbox evidence is kept distinct from real vendor observations.
alter table public.evidence drop constraint if exists evidence_source_type_check;
alter table public.evidence add constraint evidence_source_type_check check(source_type in ('LIVE_OBSERVATION','HISTORICAL','SYNTHETIC_TEST_CASE','SANDBOX_PROVIDER_DATA','DOCUMENT_PROVIDED','ISSUER_VERIFIED'));
