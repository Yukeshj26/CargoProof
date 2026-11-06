import { initializeApp } from 'firebase/app';
import { getAuth, GoogleAuthProvider } from 'firebase/auth';
import { createClient } from '@supabase/supabase-js';

// Firebase handles user authentication. Supabase remains available for PostgreSQL storage.
const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID,
};
const hasFirebaseConfig = Boolean(firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.projectId && firebaseConfig.appId);
export const firebaseApp = hasFirebaseConfig ? initializeApp(firebaseConfig) : null;
export const auth = firebaseApp ? getAuth(firebaseApp) : null;
export const googleProvider = new GoogleAuthProvider();

// Kept only for existing database/storage integrations; it is no longer used for login.
const url = import.meta.env.VITE_SUPABASE_URL;
const key = import.meta.env.VITE_SUPABASE_ANON_KEY;
export const supabase = url && key ? createClient(url, key) : null;
let rawApi = (import.meta.env.VITE_API_URL || 'http://localhost:8000').trim().replace(/\/+$/, '');
if (rawApi && !rawApi.startsWith('http://') && !rawApi.startsWith('https://')) {
  rawApi = `https://${rawApi}`;
}
export const API = rawApi;

export async function api(path, options = {}) {
  const user = auth?.currentUser;
  let token = null;
  if (user) {
    try {
      token = await user.getIdToken();
    } catch {
      token = null;
    }
  }
  if (!token && typeof localStorage !== 'undefined' && localStorage.getItem('cargoproof_demo_user')) {
    token = 'demo-token';
  }
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;
  const headers = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  const body = (options.body && !isFormData && typeof options.body === 'object')
    ? JSON.stringify(options.body)
    : options.body;

  const res = await fetch(`${API}${path}`, { ...options, headers, body });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: 'Request failed' }));
    let errorDetail = data.detail || 'Request failed';
    if (typeof errorDetail === 'object') {
      errorDetail = JSON.stringify(errorDetail);
    }
    throw new Error(errorDetail);
  }
  return res.headers.get('content-type')?.includes('application/pdf') ? res.blob() : res.json();
}
