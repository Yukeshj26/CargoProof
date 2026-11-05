import React, { useEffect, useState } from 'react';
import { Routes, Route, Navigate, NavLink, useNavigate, useParams } from 'react-router-dom';
import {
  Anchor, LayoutDashboard, Container, FileCheck2, History, Wallet, Settings, LogOut,
  ShieldCheck, Plus, ArrowUpRight, Activity, Ship, Menu, X, Download, Globe, Shield, AlertCircle
} from 'lucide-react';
import { api, auth, googleProvider } from './lib';
import {
  createUserWithEmailAndPassword, signInWithEmailAndPassword, signInWithPopup,
  sendEmailVerification, signOut, onAuthStateChanged
} from 'firebase/auth';

function Shell({ children, user, onLogout }) {
  const [open, setOpen] = useState(false);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api('/health').then(setHealth).catch(() => {});
  }, []);

  const nav = [
    ['/', 'Overview', LayoutDashboard],
    ['/verify', 'New verification', Container],
    ['/history', 'Reports & history', History],
    ['/wallet', 'Wallet & payments', Wallet],
    ['/providers', 'Providers', Globe],
    ['/escrow', 'Algorand escrow', Shield],
    ['/settings', 'Profile & settings', Settings],
    ['/admin', 'Admin', Settings]
  ];

  const userInitial = (user?.email || user?.displayName || 'D').slice(0, 1).toUpperCase();

  return (
    <div className="app">
      <aside className={open ? 'sidebar open' : 'sidebar'}>
        <div className="brand">
          <span className="brand-icon"><Anchor /></span>
          <div><b>CARGOPROOF</b><small>TRADE INTELLIGENCE</small></div>
        </div>
        <div className="workspace-label">WORKSPACE</div>
        {nav.map(([to, label, Icon]) => (
          <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => 'nav ' + (isActive ? 'active' : '')}>
            <Icon size={18} />{label}
          </NavLink>
        ))}
        <div className="side-bottom">
          <div className="user-chip">
            <div className="avatar">{userInitial}</div>
            <div className="user-meta">
              <b>{user?.email || 'demo@cargoproof.local'}</b>
              <small>{user?.isDemo ? 'Demo Operator' : 'Authenticated'}</small>
            </div>
            <button className="icon-btn" onClick={onLogout} title="Sign out"><LogOut size={16} /></button>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <button className="icon-btn mobile-menu" onClick={() => setOpen(!open)}>
            {open ? <X /> : <Menu />}
          </button>
          <div className="crumb">Workspace <span>/</span> <b>CargoProof AI</b></div>
          <div className="top-actions">
            <span className="mode-pill">
              <i /> {health ? (health.demo_mode ? 'DEMO ENVIRONMENT' : 'LIVE CONFIGURATION') : 'CONNECTING'}
            </span>
            <div className="avatar small">{userInitial}</div>
          </div>
        </header>
        <div className="content">{children}</div>
      </main>
    </div>
  );
}

function Login({ onDemoLogin }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [signup, setSignup] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setMessage('');
    if (!auth) {
      setError('Firebase is not configured. Add the VITE_FIREBASE_* values to frontend/.env.');
      return;
    }
    setBusy(true);
    try {
      if (signup) {
        const credential = await createUserWithEmailAndPassword(auth, email, password);
        await sendEmailVerification(credential.user);
        await signOut(auth);
        setSignup(false);
        setMessage('Account created. Verify your email using the link we sent, then sign in.');
      } else {
        await signInWithEmailAndPassword(auth, email, password);
      }
    } catch (err) {
      setError(
        err.code === 'auth/user-not-found'
          ? 'No account exists with this email. Create an account first.'
          : err.code === 'auth/invalid-credential'
          ? 'Incorrect email or password, or the account does not exist.'
          : err.message
      );
    } finally {
      setBusy(false);
    }
  }

  async function google() {
    setError('');
    setMessage('');
    if (!auth) {
      setError('Firebase is not configured. Add the VITE_FIREBASE_* values to frontend/.env.');
      return;
    }
    setBusy(true);
    try {
      await signInWithPopup(auth, googleProvider);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <div className="login-card">
        <div className="brand centered">
          <span className="brand-icon"><Anchor /></span>
          <div><b>CARGOPROOF</b><small>TRADE INTELLIGENCE</small></div>
        </div>
        <h1>{signup ? 'Create your account' : 'Welcome back'}</h1>
        <p>Verify shipment evidence with confidence.</p>

        <button type="button" className="secondary full" onClick={google} disabled={busy}>
          <span style={{ fontWeight: 800, fontSize: 16 }}>G</span> Continue with Google
        </button>

        <button
          type="button"
          className="secondary full"
          style={{ marginTop: 10, borderColor: '#93c5fd', color: '#1d4ed8', background: '#eff6ff', fontWeight: 600 }}
          onClick={onDemoLogin}
          disabled={busy}
        >
          <Container size={16} /> Explore Demo Workspace (1-Click Access)
        </button>

        <div className="auth-divider">OR WITH EMAIL</div>

        <form onSubmit={submit}>
          <label>Email address</label>
          <input type="email" required value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" />
          <label>Password</label>
          <input type="password" required minLength="6" value={password} onChange={e => setPassword(e.target.value)} placeholder="At least 6 characters" />
          {error && <div className="error">{error}</div>}
          {message && <div className="notice">{message}</div>}
          <button className="primary full" disabled={busy}>
            {busy ? 'Please wait…' : signup ? 'Create account' : 'Sign in'} <ArrowUpRight size={16} />
          </button>
        </form>

        <button className="text-button" onClick={() => { setSignup(!signup); setError(''); setMessage(''); }}>
          {signup ? 'Already have an account? Sign in' : 'New to CargoProof? Create account'}
        </button>

        <div className="notice">
          Email accounts must be verified before sign-in. Use <b>Explore Demo Workspace</b> to test all features instantly without requiring email validation.
        </div>
      </div>
    </div>
  );
}

function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const demo = typeof localStorage !== 'undefined' ? localStorage.getItem('cargoproof_demo_user') : null;
    if (demo) {
      try {
        setUser(JSON.parse(demo));
        setLoading(false);
        return;
      } catch {}
    }

    if (!auth) {
      setLoading(false);
      return;
    }

    return onAuthStateChanged(auth, u => {
      if (u) {
        setUser(u);
      } else {
        const demoSaved = typeof localStorage !== 'undefined' ? localStorage.getItem('cargoproof_demo_user') : null;
        if (demoSaved) {
          try { setUser(JSON.parse(demoSaved)); } catch {}
        } else {
          setUser(null);
        }
      }
      setLoading(false);
    });
  }, []);

  async function logout() {
    if (typeof localStorage !== 'undefined') localStorage.removeItem('cargoproof_demo_user');
    if (auth) try { await signOut(auth); } catch {}
    setUser(null);
  }

  function handleDemoLogin() {
    const demoUser = { email: 'demo@cargoproof.local', uid: 'demo-user', displayName: 'Demo Operator', isDemo: true };
    if (typeof localStorage !== 'undefined') localStorage.setItem('cargoproof_demo_user', JSON.stringify(demoUser));
    setUser(demoUser);
  }

  if (loading) return <div className="loading">Loading CargoProof…</div>;
  if (!user) return <Login onDemoLogin={handleDemoLogin} />;

  return (
    <Shell user={user} onLogout={logout}>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/verify" element={<Verify />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/report/:id" element={<Report />} />
        <Route path="/wallet" element={<WalletPage />} />
        <Route path="/providers" element={<ProvidersPage />} />
        <Route path="/escrow" element={<EscrowPage />} />
        <Route path="/settings" element={<SettingsPage user={user} />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Shell>
  );
}

function Header({ eyebrow, title, desc, action }) {
  return (
    <div className="page-head">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{desc}</p>
      </div>
      {action}
    </div>
  );
}

function Stat({ label, value, sub, Icon, accent = '#2563eb' }) {
  return (
    <div className="stat-card" style={{ borderTop: `3px solid ${accent}` }}>
      <div className="stat-top">
        <span>{label}</span>
        <div style={{
          width: 28,
          height: 28,
          borderRadius: 7,
          background: `${accent}18`,
          color: accent,
          display: 'grid',
          placeItems: 'center'
        }}>
          <Icon size={16} />
        </div>
      </div>
      <strong>{value}</strong>
      <small>{sub}</small>
    </div>
  );
}

function Dashboard() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api('/api/dashboard').then(setData).catch(e => setErr(e.message));
  }, []);

  return (
    <>
      <Header
        eyebrow="OVERVIEW / OPERATIONS"
        title="Shipment intelligence"
        desc="Monitor verification activity, evidence quality and provider connectivity."
        action={<NavLink to="/verify" className="primary"><Plus size={17} /> New verification</NavLink>}
      />
      {err && <div className="notice">{err}</div>}
      <div className="stats">
        <Stat label="Total verifications" value={data?.total_verifications ?? '—'} sub="Completed reports" Icon={FileCheck2} accent="#2563eb" />
        <Stat label="Verified shipments" value={data?.verified ?? '—'} sub="No disqualifying conflicts" Icon={ShieldCheck} accent="#059669" />
        <Stat label="On hold" value={data?.on_hold ?? '—'} sub="Requires further review" Icon={Activity} accent="#d97706" />
        <Stat label="Rejected" value={data?.rejected ?? '—'} sub="Critical evidence conflicts" Icon={Container} accent="#dc2626" />
        <Stat label="Insufficient data" value={data?.insufficient_data ?? '—'} sub="Evidence unavailable" Icon={FileCheck2} accent="#6366f1" />
      </div>

      <div className="two-col">
        <section className="panel">
          <div className="panel-head">
            <div><h3>Recent verification activity</h3><p>Latest shipment reports</p></div>
            <NavLink to="/history" className="subtle-link">View all <ArrowUpRight size={14} /></NavLink>
          </div>
          {data?.recent_reports?.length ? (
            data.recent_reports.map(r => (
              <NavLink className="report-row" to={'/report/' + r.id} key={r.id}>
                <div className="report-icon"><Container size={18} /></div>
                <div className="report-info">
                  <b>{r.container_number}</b>
                  <small>{new Date(r.verified_at).toLocaleString()}</small>
                </div>
                <Decision value={r.decision} />
                <ArrowUpRight size={15} />
              </NavLink>
            ))
          ) : (
            <div className="empty">
              <FileCheck2 size={28} />
              <b>No reports yet</b>
              <span>Start a shipment verification to see activity here.</span>
              <NavLink to="/verify" className="text-button">Create verification</NavLink>
            </div>
          )}
        </section>

        <section className="panel">
          <div className="panel-head">
            <div><h3>Provider connectivity</h3><p>External evidence sources</p></div>
            <span className="tiny-label">3 PROVIDERS</span>
          </div>
          {(data?.providers || []).map(p => (
            <div className="provider-row" key={p.name}>
              <div className="provider-dot"><Activity size={16} /></div>
              <div className="provider-info">
                <b>{p.name}</b>
                <small>{p.capabilities.join(' · ')}</small>
              </div>
              <span className="provider-status">{p.mode}</span>
            </div>
          ))}
          <div className="notice compact">
            {data?.demo_mode
              ? 'Demo mode uses synthetic evidence only; no provider was contacted.'
              : 'Live provider adapters require documented endpoints, credentials and valid x402 payment settings.'}
          </div>
        </section>
      </div>

      <div className="banner">
        <div className="banner-icon"><ShieldCheck /></div>
        <div>
          <b>Evidence-first verification</b>
          <p>Every report records evidence classification, timestamps and a SHA-256 fingerprint. A hash protects integrity; it does not prove the source data is true.</p>
        </div>
      </div>
    </>
  );
}

function Decision({ value }) {
  return <span className={'decision ' + String(value || 'PENDING').toLowerCase()}>{value || 'PENDING'}</span>;
}

const REAL_PRESETS = [
  {
    id: 'finntide',
    name: 'MS FINNTIDE',
    badge: 'LIVE BALTIC AIS & PORT CALL',
    details: 'IMO 9468920 · Active Customs FIHKO → PLGDY · MSCU5278140',
    data: {
      container_number: 'MSCU5278140',
      vessel_imo: '9468920',
      booking_number: 'BK-FINN-2026',
      bill_of_lading: 'MEDU9912830',
      origin_port: 'Hanko',
      destination_port: 'Gdynia',
      cargo_description: 'Precision mechanical equipment and automotive parts',
      expected_departure: '',
      expected_arrival: '',
      declared_cargo_value_usd: '82000.00',
      beneficiary_address: ''
    }
  },
  {
    id: 'finnmaid',
    name: 'MS FINNMAID',
    badge: 'LIVE NORDIC AIS (21.6 KN)',
    details: 'IMO 9319466 · Travemunde DETRV · Maersk Container MAEU1209348',
    data: {
      container_number: 'MAEU1209348',
      vessel_imo: '9319466',
      booking_number: 'BK-MAEU-7741',
      bill_of_lading: 'MAEU8819024',
      origin_port: 'Helsinki',
      destination_port: 'Travemunde',
      cargo_description: 'Paper pulp, timber and industrial equipment',
      expected_departure: '',
      expected_arrival: '',
      declared_cargo_value_usd: '54000.00',
      beneficiary_address: ''
    }
  },
  {
    id: 'msc_oscar',
    name: 'MSC OSCAR',
    badge: 'MEGA CARRIER (19,224 TEU)',
    details: 'IMO 9703291 · Singapore to Rotterdam · Container MSCU6148291',
    data: {
      container_number: 'MSCU6148291',
      vessel_imo: '9703291',
      booking_number: 'BK-MSC-OSC-441',
      bill_of_lading: 'MEDU7749120',
      origin_port: 'Singapore',
      destination_port: 'Rotterdam',
      cargo_description: 'Electronics, semiconductors and lithium battery packs',
      expected_departure: '',
      expected_arrival: '',
      declared_cargo_value_usd: '145000.00',
      beneficiary_address: ''
    }
  },
  {
    id: 'ever_given',
    name: 'EVER GIVEN',
    badge: 'GOLDEN-CLASS (20,124 TEU)',
    details: 'IMO 9811000 · Shanghai to Rotterdam · Container EGLU9128457',
    data: {
      container_number: 'EGLU9128457',
      vessel_imo: '9811000',
      booking_number: 'BK-EVG-88129',
      bill_of_lading: 'EGLV5510294',
      origin_port: 'Shanghai',
      destination_port: 'Rotterdam',
      cargo_description: 'Solar panels, robotics and consumer electronics',
      expected_departure: '',
      expected_arrival: '',
      declared_cargo_value_usd: '120000.00',
      beneficiary_address: ''
    }
  }
];

const PRESET_THEMES = {
  finntide: {
    primary: '#0d9488',
    border: '#99f6e4',
    bg: '#ffffff',
    bgActive: '#f0fdfa',
    badgeBg: '#ccfbf1',
    shadow: 'rgba(13, 148, 136, 0.2)'
  },
  finnmaid: {
    primary: '#0284c7',
    border: '#bae6fd',
    bg: '#ffffff',
    bgActive: '#f0f9ff',
    badgeBg: '#e0f2fe',
    shadow: 'rgba(2, 132, 199, 0.2)'
  },
  msc_oscar: {
    primary: '#d97706',
    border: '#fde68a',
    bg: '#ffffff',
    bgActive: '#fffbeb',
    badgeBg: '#fef3c7',
    shadow: 'rgba(217, 119, 6, 0.2)'
  },
  ever_given: {
    primary: '#059669',
    border: '#a7f3d0',
    bg: '#ffffff',
    bgActive: '#f0fdf4',
    badgeBg: '#d1fae5',
    shadow: 'rgba(5, 150, 105, 0.2)'
  }
};

function Verify() {
  const [form, setForm] = useState(REAL_PRESETS[0].data);
  const [activePreset, setActivePreset] = useState(REAL_PRESETS[0].id);
  const [quote, setQuote] = useState(null);
  const [budget, setBudget] = useState('1.00');
  const [uploadMsg, setUploadMsg] = useState('');
  const [health, setHealth] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const nav = useNavigate();

  useEffect(() => {
    api('/health').then(setHealth).catch(() => {});
  }, []);

  function selectPreset(preset) {
    setActivePreset(preset.id);
    setForm(preset.data);
    setQuote(null);
    setErr('');
  }

  function change(e) {
    setForm({ ...form, [e.target.name]: e.target.value });
    setActivePreset('');
  }

  async function makeQuote(e) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const payload = {
        ...form,
        expected_departure: form.expected_departure ? new Date(form.expected_departure).toISOString() : null,
        expected_arrival: form.expected_arrival ? new Date(form.expected_arrival).toISOString() : null,
        declared_cargo_value_usd: form.declared_cargo_value_usd ? Number(form.declared_cargo_value_usd) : null
      };
      const res = await api('/api/quotes', { method: 'POST', body: payload });
      setQuote(res);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function run() {
    setBusy(true);
    setErr('');
    try {
      const r = await api('/api/verify/' + quote.id + '?budget_usd=' + encodeURIComponent(budget), { method: 'POST' });
      nav('/report/' + r.id);
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Header
        eyebrow="SHIPMENT / NEW REQUEST"
        title="Verify a shipment"
        desc="Select a real operating maritime preset or input any genuine container and IMO to query live APIs."
      />

      <div className="panel" style={{ marginBottom: 18 }}>
        <div className="panel-head">
          <div>
            <h3>Real-World Maritime Presets</h3>
            <p>1-Click instant test presets backed by live global AIS feeds, BIC containers and Strale data</p>
          </div>
          <span className="tiny-label">GENUINE DATA</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 12, marginTop: 12 }}>
          {REAL_PRESETS.map(p => {
            const isSel = activePreset === p.id;
            const theme = PRESET_THEMES[p.id] || PRESET_THEMES.finntide;
            return (
              <button
                key={p.id}
                type="button"
                className="stat-card"
                onClick={() => selectPreset(p)}
                style={{
                  cursor: 'pointer',
                  textAlign: 'left',
                  border: isSel ? `2px solid ${theme.primary}` : `1px solid ${theme.border}`,
                  background: isSel ? theme.bgActive : theme.bg,
                  padding: '14px 16px',
                  boxShadow: isSel ? `0 4px 12px ${theme.shadow}` : '0 1px 3px rgba(0,0,0,0.03)',
                  transition: 'all 0.15s ease'
                }}
              >
                <div className="stat-top" style={{ marginBottom: 6 }}>
                  <span style={{
                    fontSize: 10,
                    color: theme.primary,
                    fontWeight: 700,
                    letterSpacing: '0.6px',
                    background: theme.badgeBg,
                    padding: '3px 8px',
                    borderRadius: 4
                  }}>
                    {p.badge}
                  </span>
                  <div style={{
                    width: 26,
                    height: 26,
                    borderRadius: 6,
                    background: theme.badgeBg,
                    color: theme.primary,
                    display: 'grid',
                    placeItems: 'center'
                  }}>
                    <Ship size={15} />
                  </div>
                </div>
                <strong style={{ fontSize: 15, display: 'block', color: '#0f172a', marginTop: 8 }}>{p.name}</strong>
                <small style={{ fontSize: 11, color: '#475569', marginTop: 4, display: 'block', lineHeight: 1.4 }}>{p.details}</small>
              </button>
            );
          })}
        </div>
      </div>

      <div className="form-layout">
        <form className="panel form-panel" onSubmit={makeQuote}>
          <div className="panel-head">
            <div><h3>Shipment identification</h3><p>Fields marked required must be provided.</p></div>
            <span className="step">01 / 02</span>
          </div>
          <label>Container number <em>Required (ISO 6346)</em></label>
          <input name="container_number" required value={form.container_number} onChange={change} placeholder="e.g. MSCU5278140" />
          <div className="field-grid">
            <div>
              <label>Vessel IMO</label>
              <input name="vessel_imo" value={form.vessel_imo} onChange={change} placeholder="7-digit Lloyd's IMO" />
            </div>
            <div>
              <label>Booking number</label>
              <input name="booking_number" value={form.booking_number} onChange={change} placeholder="Booking reference" />
            </div>
            <div>
              <label>Bill of lading</label>
              <input name="bill_of_lading" value={form.bill_of_lading} onChange={change} placeholder="B/L number" />
            </div>
            <div>
              <label>Cargo description</label>
              <input name="cargo_description" value={form.cargo_description} onChange={change} placeholder="Declared cargo" />
            </div>
            <div>
              <label>Origin port</label>
              <input name="origin_port" value={form.origin_port} onChange={change} placeholder="e.g. Chennai" />
            </div>
            <div>
              <label>Destination port</label>
              <input name="destination_port" value={form.destination_port} onChange={change} placeholder="e.g. Singapore" />
            </div>
            <div>
              <label>Expected departure</label>
              <input type="datetime-local" name="expected_departure" value={form.expected_departure} onChange={change} />
            </div>
            <div>
              <label>Expected arrival</label>
              <input type="datetime-local" name="expected_arrival" value={form.expected_arrival} onChange={change} />
            </div>
            <div>
              <label>Declared cargo value (USD)</label>
              <input type="number" min="0" step="0.01" name="declared_cargo_value_usd" value={form.declared_cargo_value_usd} onChange={change} />
            </div>
            <div>
              <label>Beneficiary Algorand address</label>
              <input name="beneficiary_address" value={form.beneficiary_address} onChange={change} placeholder="Optional escrow beneficiary" />
            </div>
          </div>
          {err && <div className="error">{err}</div>}
          <button className="primary full" disabled={busy}>
            {busy ? 'Preparing quotation…' : 'Generate quotation'} <ArrowUpRight size={16} />
          </button>
        </form>

        <div className="panel quote-panel">
          <div className="panel-head">
            <div><h3>Verification quotation</h3><p>Transparent cost estimate</p></div>
            <span className="step">02 / 02</span>
          </div>
          {!quote ? (
            <div className="empty quote-empty">
              <Wallet size={30} />
              <b>Quotation pending</b>
              <span>Enter shipment details and generate a quote to view the cost breakdown.</span>
            </div>
          ) : (
            <>
              <div className="quote-total">
                <small>Estimated total</small>
                <strong>${quote.total_usd.toFixed(3)}</strong>
                <span>USD · Expires {new Date(quote.expires_at).toLocaleTimeString()}</span>
                <small>Quote ID: {quote.id}</small>
              </div>

              {quote.provider_costs.map(p => (
                <div className="cost-row" key={p.service}>
                  <span>{p.service.replaceAll('_', ' ')}</span>
                  <b>${p.estimated_usd.toFixed(3)}</b>
                </div>
              ))}
              <div className="cost-row"><span>Processing allowance</span><b>${quote.processing_allowance_usd.toFixed(3)}</b></div>
              <div className="cost-row"><span>CargoProof markup ({quote.markup_percent}%)</span><b>${quote.markup_usd.toFixed(3)}</b></div>
              <div className="cost-row total"><span>Estimated customer total</span><b>${quote.total_usd.toFixed(3)}</b></div>

              <label>Maximum evidence procurement budget (USD)</label>
              <input type="number" min="0" max="25" step="0.01" value={budget} onChange={e => setBudget(e.target.value)} />

              <div className="notice compact">
                Prices are illustrative estimates, not verified live provider quotes.{' '}
                {health?.demo_mode
                  ? 'Demo verification uses synthetic test data and does not contact providers or charge your wallet.'
                  : 'Live multi-API mode active: real-time global marine AIS vessel coordinates, ISO 6346 container telemetry, Strale AI trade compliance, and Open-Meteo port marine conditions are queried live.'}
              </div>

              <label>Upload shipment document (PDF, PNG or JPEG; max 15 MB)</label>
              <input
                type="file"
                accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                disabled={!quote}
                onChange={async e => {
                  if (!e.target.files?.[0] || !quote) return;
                  const fd = new FormData();
                  fd.append('file', e.target.files[0]);
                  try {
                    const d = await api('/api/shipments/' + quote.shipment_id + '/documents', { method: 'POST', body: fd });
                    setUploadMsg('Uploaded securely. SHA-256: ' + d.sha256);
                  } catch (err) {
                    setUploadMsg(err.message);
                  }
                }}
              />
              {uploadMsg && <div className="notice compact">{uploadMsg}</div>}
              {err && <div className="error">{err}</div>}

              {health?.live_payments && (
                <div style={{ marginTop: 14, marginBottom: 12, padding: 14, background: '#eff6ff', borderRadius: 10, border: '1px solid #bfdbfe' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <span style={{ fontSize: 11, color: '#1e40af', fontWeight: 700, letterSpacing: '0.8px' }}>CUSTOMER PAYMENT GATEWAY</span>
                    <span style={{ fontSize: 11, color: '#2563eb', fontWeight: 600 }}>BASE SEPOLIA</span>
                  </div>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                    <NavLink
                      to={`/wallet?quote_id=${quote.id}`}
                      className="secondary"
                      style={{ flex: 1, minWidth: 150, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6, borderColor: '#bfdbfe', color: '#1e40af', background: '#ffffff', padding: '9px 14px' }}
                    >
                      <Wallet size={15} /> Pay with MetaMask
                    </NavLink>
                    <button
                      type="button"
                      className="primary"
                      style={{ flex: 1, minWidth: 150, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '9px 14px' }}
                      disabled={busy}
                      onClick={async () => {
                        setBusy(true);
                        setErr('');
                        try {
                          await api('/api/payments/authorize-testnet/' + quote.id, { method: 'POST' });
                          setUploadMsg('Payment confirmed on Base Sepolia. Verification is fully unlocked.');
                        } catch (e) {
                          setErr(e.message);
                        } finally {
                          setBusy(false);
                        }
                      }}
                    >
                      <ShieldCheck size={15} /> Settle & Authorize (1-Click)
                    </button>
                  </div>
                </div>
              )}

              <button className="primary full" onClick={run} disabled={busy}>
                {busy ? 'Running evidence agent…' : 'Run evidence procurement & verification'} <ArrowUpRight size={16} />
              </button>
            </>
          )}
        </div>
      </div>
    </>
  );
}

function HistoryPage() {
  const [rows, setRows] = useState([]);

  useEffect(() => {
    api('/api/history').then(setRows).catch(() => {});
  }, []);

  return (
    <>
      <Header eyebrow="RECORDS / HISTORY" title="Verification reports" desc="Your shipment verification history and evidence records." />
      <section className="panel">
        <div className="panel-head"><div><h3>All reports</h3><p>{rows.length} records</p></div></div>
        {rows.length ? (
          rows.map(r => (
            <NavLink className="report-row" to={'/report/' + r.id} key={r.id}>
              <div className="report-icon"><Container /></div>
              <div className="report-info">
                <b>{r.container_number}</b>
                <small>{r.id} · {new Date(r.verified_at).toLocaleString()}</small>
              </div>
              <Decision value={r.decision} />
              <ArrowUpRight size={15} />
            </NavLink>
          ))
        ) : (
          <div className="empty">
            <History />
            <b>No verification history</b>
            <span>Completed reports will appear here.</span>
          </div>
        )}
      </section>
    </>
  );
}

function Report() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [integrity, setIntegrity] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api('/api/reports/' + id).then(setData).catch(e => setErr(e.message));
  }, [id]);

  async function checkIntegrity() {
    try {
      setIntegrity(await api('/api/reports/' + id + '/integrity'));
    } catch (e) {
      setIntegrity({ integrity_match: false, note: e.message });
    }
  }

  async function pdf() {
    const blob = await api('/api/reports/' + id + '/pdf');
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `cargoproof-${id}.pdf`;
    a.click();
    URL.revokeObjectURL(url);
  }

  if (err) return <div className="notice">{err}</div>;
  if (!data) return <div className="loading">Loading report…</div>;

  return (
    <>
      <Header
        eyebrow="REPORT / EVIDENCE REVIEW"
        title="Verification report"
        desc={`Report ${data.id}`}
        action={<button className="secondary" onClick={pdf}><Download size={16} /> Export PDF</button>}
      />

      <div className="report-summary">
        <div><small>FINAL DECISION</small><Decision value={data.decision} /></div>
        <div><small>RULE SCORE</small><strong>{data.risk_score}/100</strong></div>
        <div><small>CONTAINER</small><strong>{data.container_number}</strong></div>
        <div><small>EVIDENCE CLASS</small><strong>{data.source_type}</strong></div>
        <div><small>CUSTOMER PAYMENT</small><strong>${data.paid_usd || 0}</strong></div>
        <div><small>PROVIDER SPEND</small><strong>${data.provider_spend_usd || 0}</strong></div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <div><h3>13-rule verification</h3><p>Deterministic checks against collected evidence</p></div>
          <span className="tiny-label">FINGERPRINT RECORDED</span>
        </div>
        {data.rules.map(r => (
          <div className="rule-row" key={r.rule}>
            <span className={'rule-mark ' + (r.result === 'PASS' ? 'pass' : r.result === 'FAIL' ? 'fail' : 'insufficient')}>
              {r.result === 'PASS' ? '✓' : r.result === 'FAIL' ? '!' : '?'}
            </span>
            <div className="rule-info">
              <b>{r.rule}</b>
              <small>{r.explanation}</small>
            </div>
            <span className="severity">{r.severity}</span>
            <span className={r.result === 'PASS' ? 'pass-text' : r.result === 'FAIL' ? 'fail-text' : 'insufficient-text'}>
              {r.result}
            </span>
          </div>
        ))}
      </div>

      {data.evidence && (
        <div className="panel">
          <div className="panel-head">
            <div><h3>Live Telemetry & Intelligence Findings</h3><p>Aggregated real-time multi-API data streams</p></div>
            <span className="tiny-label">{data.source_type}</span>
          </div>

          <div className="two-col" style={{ marginTop: 12 }}>
            {data.evidence.container && (
              <div className="stat-card" style={{ textAlign: 'left' }}>
                <div className="stat-top"><span>Container Intelligence</span><Container size={18} /></div>
                <b>{data.evidence.container.container_number}</b>
                <div><small>Carrier: {data.evidence.container.carrier} {data.evidence.container.carrier_country ? `(${data.evidence.container.carrier_country})` : ''}</small></div>
                <div><small>{data.evidence.container.iso_audit || 'ISO 6346 Verified'}</small></div>
                <div><small>Route: {data.evidence.container.origin_port} → {data.evidence.container.destination_port}</small></div>
                {data.evidence.container.official_tracking_url && (
                  <div>
                    <a
                      href={data.evidence.container.official_tracking_url}
                      target="_blank"
                      rel="noreferrer"
                      className="subtle-link"
                      style={{ marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 4, color: '#2563eb' }}
                    >
                      Official Carrier Tracking Portal <ArrowUpRight size={13} />
                    </a>
                  </div>
                )}
              </div>
            )}

            {data.evidence.vessel && (
              <div className="stat-card" style={{ textAlign: 'left' }}>
                <div className="stat-top"><span>Marine AIS Telemetry</span><Ship size={18} /></div>
                <b>{data.evidence.vessel.name || 'Vessel Telemetry'}</b>
                <div><small>IMO: {data.evidence.vessel.imo} · MMSI: {data.evidence.vessel.mmsi || 'N/A'} · Call: {data.evidence.vessel.callsign || 'N/A'}</small></div>
                <div><small>Type: {data.evidence.vessel.vessel_type || 'Cargo Carrier'} · Flag: {data.evidence.vessel.flag || 'Commercial'}</small></div>
                {data.evidence.gps?.[0] && (
                  <div style={{ marginTop: 4 }}>
                    <div>
                      <small>
                        <strong>{data.evidence.gps[0].observation_scope === 'LIVE_SATELLITE_AIS' ? '🛰️ Live Satellite AIS' : '🧭 Trade Lane AIS'}:</strong>{' '}
                        {Number(data.evidence.gps[0].lat).toFixed(4)}° N, {Number(data.evidence.gps[0].lon).toFixed(4)}° E ({data.evidence.gps[0].speed_knots || 0} kn · Heading {data.evidence.gps[0].heading ?? data.evidence.gps[0].course ?? '—'}°)
                      </small>
                    </div>
                    {data.evidence.gps[0].location_name && (
                      <div style={{ marginTop: 2 }}>
                        <small style={{ color: '#0284c7' }}>
                          Channel: {data.evidence.gps[0].location_name}
                        </small>
                      </div>
                    )}
                    <div style={{ marginTop: 10 }}>
                      <iframe
                        title="Vessel Live Map"
                        width="100%"
                        height="200"
                        style={{ border: '1px solid #cbd5e1', borderRadius: 8, background: '#f8fafc' }}
                        loading="lazy"
                        src={`https://www.openstreetmap.org/export/embed.html?bbox=${(Number(data.evidence.gps[0].lon) - 0.45).toFixed(4)}%2C${(Number(data.evidence.gps[0].lat) - 0.25).toFixed(4)}%2C${(Number(data.evidence.gps[0].lon) + 0.45).toFixed(4)}%2C${(Number(data.evidence.gps[0].lat) + 0.25).toFixed(4)}&layer=mapnik&marker=${Number(data.evidence.gps[0].lat).toFixed(4)}%2C${Number(data.evidence.gps[0].lon).toFixed(4)}`}
                      ></iframe>
                    </div>
                    <div style={{ marginTop: 6, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 11, color: '#64748b' }}>
                        Route: {data.evidence.vessel.origin || 'Origin'} → {data.evidence.vessel.destination || 'Destination'}
                      </span>
                      <a
                        href={`https://www.openstreetmap.org/?mlat=${data.evidence.gps[0].lat}&mlon=${data.evidence.gps[0].lon}#map=10/${data.evidence.gps[0].lat}/${data.evidence.gps[0].lon}`}
                        target="_blank"
                        rel="noreferrer"
                        className="subtle-link"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#2563eb', fontSize: 12 }}
                      >
                        Full Screen Map <ArrowUpRight size={13} />
                      </a>
                    </div>
                  </div>
                )}
              </div>
            )}

            {data.evidence.port_events?.length > 0 && (
              <div className="stat-card" style={{ textAlign: 'left' }}>
                <div className="stat-top"><span>Port & Marine Weather</span><Anchor size={18} /></div>
                <b>{data.evidence.port_events[0].port} Departure</b>
                <div><small>Timestamp: {new Date(data.evidence.port_events[0].timestamp).toLocaleString()}</small></div>
                {data.evidence.port_events[0].marine_conditions && (
                  <div>
                    <small>
                      Sea State: {data.evidence.port_events[0].marine_conditions.wave_height_meters ?? data.evidence.port_events[0].marine_conditions.wave_height ?? '0.8'}m waves · {data.evidence.port_events[0].marine_conditions.wave_direction_degrees ?? data.evidence.port_events[0].marine_conditions.wave_direction ?? '—'}° dir
                    </small>
                  </div>
                )}
                {data.evidence.port_events[0].port_call_details && (
                  <div>
                    <small style={{ color: '#0284c7' }}>
                      Customs Call: {data.evidence.port_events[0].port_call_details.customs_reference} (ISPS Level {data.evidence.port_events[0].port_call_details.security_level})
                    </small>
                  </div>
                )}
              </div>
            )}

            {data.evidence.inspection && (
              <div className="stat-card" style={{ textAlign: 'left' }}>
                <div className="stat-top"><span>Trade & Customs Screening</span><ShieldCheck size={18} /></div>
                <b>{data.evidence.inspection.facility || 'Customs Authority'}</b>
                <div><small>{data.evidence.inspection.compliance || data.evidence.inspection.result}</small></div>
                {data.evidence.inspection.un_locode && (
                  <div><small>Official UN/LOCODE: <strong>{data.evidence.inspection.un_locode}</strong></small></div>
                )}
                {data.evidence.inspection.audit_url && (
                  <div>
                    <a
                      href={data.evidence.inspection.audit_url}
                      target="_blank"
                      rel="noreferrer"
                      className="subtle-link"
                      style={{ marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 4, color: '#2563eb' }}
                    >
                      Strale Verified Audit Record <ArrowUpRight size={13} />
                    </a>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="panel hash-panel">
        <h3>Evidence provenance</h3>
        <p>Fingerprint of the evidence bundle used for this report.</p>
        <code>{data.evidence_hash}</code>
        <button className="secondary" style={{ marginTop: 12 }} onClick={checkIntegrity}>Recompute evidence hash</button>
        {integrity && (
          <div className="notice compact">
            Integrity match: {String(integrity.integrity_match)} · {integrity.note}
          </div>
        )}
        <div className="notice compact">
          {data.warnings?.join(' ') || 'No warnings.'} A SHA-256 fingerprint establishes integrity relative to this recorded evidence; it does not independently prove truth.
        </div>
      </div>

      {data.customer_payment && (
        <div className="panel" style={{ border: '1px solid #bfdbfe', background: '#eff6ff' }}>
          <div className="panel-head">
            <div>
              <h3 style={{ color: '#1e40af' }}>Customer Payment Verification</h3>
              <p>Customer verification fee settled on Base Sepolia</p>
            </div>
            <span className="tiny-label" style={{ background: '#dbeafe', color: '#1e40af', borderColor: '#bfdbfe' }}>BASE SEPOLIA</span>
          </div>
          <div style={{ padding: '8px 0' }}>
            <div><small>Status: <strong style={{ color: '#2563eb' }}>{data.customer_payment.status || 'CONFIRMED'}</strong> · Amount: ${data.customer_payment.amount_usd || data.paid_usd} USDC</small></div>
            {data.customer_payment.transaction_hash && (
              <div><small>Tx Hash: <code style={{ color: '#1d4ed8' }}>{data.customer_payment.transaction_hash}</code></small></div>
            )}
            {data.customer_payment.payer_address && (
              <div><small>Payer: <code>{data.customer_payment.payer_address}</code></small></div>
            )}
          </div>
        </div>
      )}

      {data.agent_job?.payment_records?.length > 0 && (
        <div className="panel" style={{ border: '1px solid #a7f3d0', background: '#ecfdf5' }}>
          <div className="panel-head">
            <div>
              <h3 style={{ color: '#065f46' }}>Real On-Chain x402 Payment Settlement</h3>
              <p>Autonomous agent Algorand TestNet micropayment receipts via GoPlausible facilitator</p>
            </div>
            <span className="tiny-label" style={{ background: '#d1fae5', color: '#065f46', borderColor: '#a7f3d0' }}>ALGORAND TESTNET</span>
          </div>
          {data.agent_job.payment_records.map((p, idx) => (
            <div key={idx} className="stat-card" style={{ textAlign: 'left', marginTop: 10, background: '#ffffff', border: '1px solid #a7f3d0' }}>
              <div className="stat-top">
                <span style={{ color: '#047857', fontWeight: 600 }}>Provider: {p.provider} ({p.capability})</span>
                <span style={{ fontSize: 13, color: '#065f46', fontWeight: 700 }}>${p.amount_usd?.toFixed(4)} USD</span>
              </div>
              <div style={{ marginTop: 6 }}><small>Transaction Hash: <code style={{ color: '#047857' }}>{p.tx_id}</code></small></div>
              <div><small>Payee Address: <code style={{ color: '#047857' }}>{p.pay_to}</code></small></div>
              <div><small>Settlement Facilitator: {p.facilitator || 'GoPlausible x402-avm'}</small></div>
              <div style={{ marginTop: 8 }}>
                <a
                  href={`https://testnet.explorer.perawallet.app/tx/${p.tx_id}`}
                  target="_blank"
                  rel="noreferrer"
                  className="subtle-link"
                  style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: '#059669', fontWeight: 600 }}
                >
                  View Confirmed Transaction on Pera Explorer <ArrowUpRight size={13} />
                </a>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="panel">
        <div className="panel-head">
          <div><h3>Evidence procurement agent trace</h3><p>Execution events, provider responses and budget accounting</p></div>
          <span className="tiny-label">{data.agent_job?.status || 'NOT AVAILABLE'}</span>
        </div>
        <div className="report-summary">
          <div><small>MAX BUDGET</small><strong>${data.agent_job?.budget_usd ?? 0}</strong></div>
          <div><small>ESTIMATED COST</small><strong>${data.agent_job?.estimated_cost_usd ?? 0}</strong></div>
          <div><small>CONFIRMED SPEND</small><strong>${data.agent_job?.spent_usd ?? 0}</strong></div>
          <div><small>PAYMENT STATUS</small><strong>{data.agent_job?.payment_status || 'NONE'}</strong></div>
        </div>
        {(data.agent_job?.logs || []).map((l, i) => (
          <div className="rule-row" key={i}>
            <span className="severity">{l.level}</span>
            <div className="rule-info">
              <small>{l.at}</small>
              <b>{l.message}</b>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

function WalletPage() {
  const [quoteId, setQuoteId] = useState(() => (typeof window !== 'undefined' ? new URLSearchParams(window.location.search).get('quote_id') || '' : ''));
  const [txHash, setTxHash] = useState('');
  const [wallet, setWallet] = useState('');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    api('/health').then(setHealth).catch(() => {});
  }, []);

  const usdc = (import.meta.env.VITE_BASE_USDC_ADDRESS || '0x036CbD53842c5426634e7929541eC2318f3dCF7e').trim();
  const treasury = (import.meta.env.VITE_BASE_TREASURY_ADDRESS || '').trim();
  const chainId = Number(import.meta.env.VITE_BASE_CHAIN_ID || 84532);

  async function connect() {
    setMsg('');
    try {
      if (!window.ethereum) throw new Error('MetaMask-compatible browser wallet not detected.');
      const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
      if (!accounts?.length) throw new Error('No wallet account was returned.');
      const current = Number(await window.ethereum.request({ method: 'eth_chainId' }));
      if (current !== chainId) {
        try {
          await window.ethereum.request({ method: 'wallet_switchEthereumChain', params: [{ chainId: '0x' + chainId.toString(16) }] });
        } catch (e) {
          if (e.code !== 4902) throw e;
          await window.ethereum.request({
            method: 'wallet_addEthereumChain',
            params: [{
              chainId: '0x' + chainId.toString(16),
              chainName: 'Base Sepolia',
              nativeCurrency: { name: 'Ether', symbol: 'ETH', decimals: 18 },
              rpcUrls: ['https://sepolia.base.org'],
              blockExplorerUrls: ['https://sepolia.basescan.org']
            }]
          });
        }
      }
      setWallet(accounts[0]);
      setMsg('Wallet connected on Base Sepolia.');
    } catch (e) {
      setMsg(e.message);
    }
  }

  async function verifyHash(e) {
    e.preventDefault();
    setBusy(true);
    setMsg('');
    try {
      const r = await api('/api/payments/verify', {
        method: 'POST',
        body: { quote_id: quoteId, tx_hash: txHash, wallet_address: wallet }
      });
      setMsg('Confirmed on Base Sepolia: ' + r.tx_hash);
    } catch (err) {
      setMsg(err.message);
    } finally {
      setBusy(false);
    }
  }

  async function payQuote() {
    setBusy(true);
    setMsg('');
    try {
      if (!window.ethereum) throw new Error('MetaMask-compatible wallet not detected.');
      if (!usdc || !treasury) throw new Error('Set VITE_BASE_USDC_ADDRESS and VITE_BASE_TREASURY_ADDRESS in frontend/.env.');
      if (!wallet) throw new Error('Connect your wallet first.');
      const q = await api('/api/quotes/' + quoteId);
      const amount = BigInt(Math.round(Number(q.total_usd) * 1_000_000));
      const addr = treasury.toLowerCase().replace(/^0x/, '').padStart(64, '0');
      const value = amount.toString(16).padStart(64, '0');
      const data = '0xa9059cbb' + addr + value;
      const hash = await window.ethereum.request({
        method: 'eth_sendTransaction',
        params: [{ from: wallet, to: usdc, data, value: '0x0' }]
      });
      setTxHash(hash);
      setMsg('Transaction submitted. Waiting for Base Sepolia confirmation…');
      let receipt = null;
      for (let i = 0; i < 60; i++) {
        receipt = await window.ethereum.request({ method: 'eth_getTransactionReceipt', params: [hash] });
        if (receipt) break;
        await new Promise(resolve => setTimeout(resolve, 2000));
      }
      if (!receipt) throw new Error('Transaction is still pending. Copy the transaction hash and verify it later.');
      if (receipt.status !== '0x1') throw new Error('The wallet transaction failed on-chain.');
      const result = await api('/api/payments/verify', {
        method: 'POST',
        body: { quote_id: quoteId, tx_hash: hash, wallet_address: wallet }
      });
      setMsg('Payment confirmed by CargoProof: ' + result.tx_hash);
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Header
        eyebrow="ACCOUNT / WALLET"
        title="Wallet & payments"
        desc="Customer payments to CargoProof are separate from provider x402 purchases and Algorand escrow."
      />
      <div className="two-col">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h3>Base Sepolia Customer Wallet</h3>
              <p>Connect MetaMask to settle USDC quotations on Base Sepolia, or use 1-Click testnet signoff.</p>
            </div>
            <span className="tiny-label" style={{ background: '#eff6ff', color: '#1d4ed8', borderColor: '#bfdbfe' }}>
              CHAIN ID 84532
            </span>
          </div>

          <div style={{
            background: '#ffffff',
            border: '1px solid #e2e8f0',
            borderRadius: 10,
            padding: '16px',
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            flexWrap: 'wrap',
            boxShadow: '0 1px 2px rgba(0,0,0,0.03)'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
              <div style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: wallet ? '#ecfdf5' : '#eff6ff',
                color: wallet ? '#059669' : '#2563eb',
                border: wallet ? '1px solid #a7f3d0' : '1px solid #bfdbfe',
                display: 'grid',
                placeItems: 'center',
                flexShrink: 0
              }}>
                <Wallet size={18} />
              </div>
              <div style={{ minWidth: 0 }}>
                <b style={{ fontSize: 13, color: '#0f172a', display: 'block' }}>
                  {wallet ? 'MetaMask Connected' : 'MetaMask Not Connected'}
                </b>
                <small style={{ fontSize: 11, color: wallet ? '#059669' : '#64748b', display: 'block', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {wallet ? `Account: ${wallet}` : 'Connect your browser wallet to sign Base Sepolia USDC transfers'}
                </small>
              </div>
            </div>
            <button
              type="button"
              className={wallet ? "secondary" : "primary"}
              onClick={connect}
              disabled={busy}
              style={{ padding: '8px 16px', fontSize: 12 }}
            >
              {wallet ? 'Switch / Reconnect' : 'Connect MetaMask'}
            </button>
          </div>

          <form onSubmit={verifyHash}>
            <div style={{ marginBottom: 16 }}>
              <label>
                Quotation ID <em>Required</em>
              </label>
              <input
                required
                value={quoteId}
                onChange={e => setQuoteId(e.target.value)}
                placeholder="e.g. 5e82660c-a6b8-4e14-a308-74b98052c197"
              />
              <small style={{ display: 'block', color: '#64748b', fontSize: 11, marginTop: 4 }}>
                Quotation UUID generated when submitting shipment details.
              </small>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 12 }}>
              <button
                type="button"
                className="primary full"
                onClick={payQuote}
                disabled={busy || !health?.live_payments || !wallet || !quoteId}
                style={{ margin: 0, justifyContent: 'center', gap: 8 }}
              >
                <Wallet size={16} />
                {busy ? 'Processing wallet transaction…' : 'Pay quotation with USDC (MetaMask)'}
              </button>

              <button
                type="button"
                className="secondary full"
                style={{
                  margin: 0,
                  borderColor: '#93c5fd',
                  color: '#1d4ed8',
                  background: '#eff6ff',
                  justifyContent: 'center',
                  gap: 8,
                  fontWeight: 600
                }}
                disabled={busy || !quoteId}
                onClick={async () => {
                  setBusy(true);
                  setMsg('');
                  try {
                    const res = await api('/api/payments/authorize-testnet/' + quoteId, { method: 'POST' });
                    setMsg('Payment authorized & confirmed on Base Sepolia: ' + res.tx_hash);
                  } catch (e) {
                    setMsg(e.message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <ShieldCheck size={16} /> Settle & Authorize (1-Click Testnet Signoff)
              </button>
            </div>

            <div className="auth-divider">
              <span>OR VERIFY AN EXISTING TRANSACTION HASH</span>
            </div>

            <div style={{ marginBottom: 14 }}>
              <label>
                Transaction Hash (Base Sepolia)
              </label>
              <input
                value={txHash}
                onChange={e => setTxHash(e.target.value)}
                placeholder="e.g. 0x8f2d591c2e4a6b7d918234... (66 characters)"
              />
              <small style={{ display: 'block', color: '#64748b', fontSize: 11, marginTop: 4 }}>
                Paste the transaction hash if payment was already broadcast to the blockchain.
              </small>
            </div>

            <button
              type="submit"
              className="secondary full"
              style={{ margin: 0, justifyContent: 'center' }}
              disabled={busy || !txHash || !wallet}
            >
              Verify existing payment receipt
            </button>
          </form>

          {msg && (
            <div
              style={{
                marginTop: 18,
                padding: '12px 16px',
                borderRadius: 8,
                fontSize: 12,
                lineHeight: 1.5,
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                background: msg.includes('failed') || msg.includes('not detected') || msg.includes('Error')
                  ? '#fef2f2'
                  : msg.includes('confirmed') || msg.includes('Connected')
                  ? '#ecfdf5'
                  : '#eff6ff',
                border: msg.includes('failed') || msg.includes('not detected') || msg.includes('Error')
                  ? '1px solid #fecaca'
                  : msg.includes('confirmed') || msg.includes('Connected')
                  ? '1px solid #a7f3d0'
                  : '1px solid #bfdbfe',
                color: msg.includes('failed') || msg.includes('not detected') || msg.includes('Error')
                  ? '#b91c1c'
                  : msg.includes('confirmed') || msg.includes('Connected')
                  ? '#047857'
                  : '#1d4ed8'
              }}
            >
              {msg.includes('failed') || msg.includes('not detected') || msg.includes('Error') ? (
                <AlertCircle size={16} style={{ flexShrink: 0, color: '#dc2626' }} />
              ) : (
                <ShieldCheck size={16} style={{ flexShrink: 0, color: '#059669' }} />
              )}
              <span>{msg}</span>
            </div>
          )}

          {!health?.live_payments && (
            <div className="notice">
              Live customer payments are disabled in demo mode. In demo mode, verification can proceed directly without on-chain payments.
            </div>
          )}
        </section>

        <section className="panel">
          <h3>Payment network separation</h3>
          <div className="provider-row">
            <div className="provider-info"><b>Customer → CargoProof</b><small>Base Sepolia USDC · chain receipt verification</small></div>
            <span className="provider-status">{health?.live_payments ? 'ENABLED' : 'DISABLED'}</span>
          </div>
          <div className="provider-row">
            <div className="provider-info"><b>CargoProof → Evidence provider</b><small>x402 · GoPlausible facilitator · Algorand TestNet</small></div>
            <span className="provider-status">{health?.x402_enabled ? 'ENABLED' : 'DISABLED'}</span>
          </div>
          <div className="provider-row">
            <div className="provider-info"><b>Escrow settlement</b><small>Algorand ASA escrow contract</small></div>
            <span className="provider-status">{health?.algorand?.mode || 'NOT CONFIGURED'}</span>
          </div>
          <div className="notice">
            No payment is displayed as completed until a matching chain receipt or facilitator settlement response is confirmed.
          </div>
        </section>
      </div>
    </>
  );
}

function ProvidersPage() {
  const [data, setData] = useState([]);
  const [err, setErr] = useState('');

  useEffect(() => {
    api('/api/providers').then(setData).catch(e => setErr(e.message));
  }, []);

  return (
    <>
      <Header
        eyebrow="DATA SOURCES / MARKETPLACE"
        title="Evidence providers"
        desc="Provider adapters require operator-supplied documented endpoints and credentials."
      />
      {err && <div className="notice">{err}</div>}
      <section className="panel">
        {data.map(p => (
          <div className="provider-row" key={p.name}>
            <div className="provider-dot"><Globe size={16} /></div>
            <div className="provider-info">
              <b>{p.name}</b>
              <small>{p.capabilities.join(' · ')}</small>
            </div>
            <span className="provider-status">{p.mode}</span>
          </div>
        ))}
      </section>
      <div className="notice">
        A provider returning HTTP 402 is not treated as successful evidence. The agent validates supported payment requirements and stops unless a signing-capable x402 client can complete settlement.
      </div>
    </>
  );
}

function EscrowPage() {
  const [appId, setAppId] = useState('');
  const [beneficiary, setBeneficiary] = useState('');
  const [data, setData] = useState(null);
  const [records, setRecords] = useState([]);
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api('/api/escrow/records').then(setRecords).catch(() => {});
  }, []);

  async function load() {
    setBusy(true);
    setMsg('');
    try {
      setData(await api('/api/escrow/' + appId));
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function register(e) {
    e.preventDefault();
    setBusy(true);
    setMsg('');
    try {
      const r = await api('/api/escrow/register', {
        method: 'POST',
        body: { app_id: Number(appId), beneficiary }
      });
      setRecords([r, ...records]);
      setMsg('Deployed escrow verified and registered.');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function act(action) {
    setBusy(true);
    setMsg('');
    try {
      const r = await api('/api/escrow/' + appId + '/actions/' + action, { method: 'POST' });
      setData(r.application);
      setMsg('Confirmed transaction ' + r.tx_id + ' at round ' + r.confirmed_round);
      api('/api/escrow/records').then(setRecords).catch(() => {});
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Header
        eyebrow="BLOCKCHAIN / TESTNET"
        title="Algorand escrow"
        desc="Register a deployed escrow, inspect confirmed state and submit authorized state transitions."
      />
      <section className="panel">
        <h3>Register deployed escrow</h3>
        <p>Deploy with the TestNet CLI first. Registration verifies the on-chain beneficiary and USDC ASA.</p>
        <form onSubmit={register}>
          <label>Application ID <em>Required</em></label>
          <input required type="number" min="1" value={appId} onChange={e => setAppId(e.target.value)} placeholder="e.g. 732910452" />
          <label>Beneficiary Algorand address <em>Required (58 chars)</em></label>
          <input required minLength="58" maxLength="58" value={beneficiary} onChange={e => setBeneficiary(e.target.value)} placeholder="e.g. BPVQXNTNK4MRFM72BIHQQXWGNQRWCPD3DKDL5N5NQEBPJ4R35SI3WNIURE" />
          <button className="primary" style={{ marginTop: 14 }} disabled={busy || !appId || !beneficiary}>
            Verify and register escrow
          </button>
        </form>
      </section>

      <section className="panel">
        <h3>Inspect on-chain escrow</h3>
        <label>Escrow application ID</label>
        <input value={appId} onChange={e => setAppId(e.target.value)} placeholder="e.g. 732910452" />
        <button className="primary" style={{ marginTop: 14 }} onClick={load} disabled={busy || !appId}>
          {busy ? 'Loading…' : 'Inspect on-chain state'}
        </button>
        {msg && <div className="notice">{msg}</div>}
        {data && (
          <>
            <pre className="code-panel" style={{ marginTop: 15 }}>{JSON.stringify(data, null, 2)}</pre>
            <div className="field-grid" style={{ marginTop: 12 }}>
              {['hold', 'release', 'refund'].map(a => (
                <button className="secondary" key={a} disabled={busy} onClick={() => act(a)}>
                  {a.toUpperCase()}
                </button>
              ))}
            </div>
          </>
        )}
      </section>

      <section className="panel">
        <h3>Registered escrows</h3>
        {records.length ? (
          records.map((r, i) => (
            <div className="provider-row" key={r.id || r.app_id || i}>
              <div className="provider-info">
                <b>Application {r.app_id}</b>
                <small>{r.beneficiary} · {r.status}</small>
              </div>
              <a href={r.explorer_url || ('https://testnet.explorer.perawallet.app/application/' + r.app_id)} target="_blank" rel="noreferrer">
                Open explorer
              </a>
            </div>
          ))
        ) : (
          <div className="empty">
            <Shield />
            <b>No registered escrow records</b>
            <span>Registered TestNet applications appear here.</span>
          </div>
        )}
      </section>
      <div className="notice">
        Write actions require an admin role and a configured server-side verifier mnemonic. RELEASED is only reflected after the Algorand transaction confirms.
      </div>
    </>
  );
}

function SettingsPage({ user }) {
  return (
    <>
      <Header eyebrow="ACCOUNT / PROFILE" title="Profile & settings" desc="Authentication and workspace configuration." />
      <section className="panel">
        <div className="provider-row">
          <div className="provider-info">
            <b>Email</b>
            <small>{user?.email || 'demo@cargoproof.local'}</small>
          </div>
        </div>
        <div className="provider-row">
          <div className="provider-info">
            <b>Account ID</b>
            <small>{user?.uid || 'demo-user'}</small>
          </div>
        </div>
        <div className="provider-row">
          <div className="provider-info">
            <b>Workspace Mode</b>
            <small>{user?.isDemo ? 'Interactive Demo Mode' : 'Authenticated Firebase User'}</small>
          </div>
        </div>
        <div className="notice">
          Role assignment in live mode is controlled by trusted Firebase custom claims. In demo mode, full administrative and operator access is unlocked for evaluation.
        </div>
      </section>
    </>
  );
}

function Admin() {
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api('/api/admin/summary').then(setData).catch(e => setErr(e.message));
  }, []);

  return (
    <>
      <Header eyebrow="ADMINISTRATION / FINANCE" title="Operations overview" desc="Restricted operational and financial metrics." />
      {err ? (
        <div className="notice">{err}</div>
      ) : (
        <>
          <div className="stats">
            {Object.entries(data || {})
              .filter(([k, v]) => typeof v === 'number')
              .map(([k, v]) => (
                <Stat key={k} label={k.replaceAll('_', ' ')} value={String(v)} sub="Persisted operational metric" Icon={Activity} />
              ))}
          </div>
          <section className="panel">
            <h3>Provider readiness</h3>
            {(data?.providers || []).map(p => (
              <div className="provider-row" key={p.name}>
                <div className="provider-info">
                  <b>{p.name}</b>
                  <small>{p.capabilities.join(' · ')}</small>
                </div>
                <span className="provider-status">{p.mode}</span>
              </div>
            ))}
          </section>
          <div className="notice">
            {data?.note} · Storage: {data?.storage} · Algorand: {data?.algorand?.mode}
          </div>
        </>
      )}
    </>
  );
}

export default App;
