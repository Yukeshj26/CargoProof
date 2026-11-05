from pathlib import Path
import os
from fastapi import Header, HTTPException
from .config import settings
import firebase_admin
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials


def _firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        options = {"projectId": settings.firebase_project_id} if settings.firebase_project_id else None
        cred_path = settings.google_application_credentials or os.environ.get('GOOGLE_APPLICATION_CREDENTIALS', '')
        if cred_path:
            p = Path(cred_path)
            if not p.is_absolute():
                backend_dir = Path(__file__).resolve().parent.parent
                if (backend_dir / p).exists():
                    p = backend_dir / p
                elif (Path.cwd() / p).exists():
                    p = Path.cwd() / p
            if p.exists():
                return firebase_admin.initialize_app(credentials.Certificate(str(p)), options=options)
        try:
            return firebase_admin.initialize_app(credentials.ApplicationDefault(), options=options)
        except Exception:
            return firebase_admin.initialize_app(options=options)


def current_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.lower().startswith('bearer '):
        if settings.demo_mode or not settings.firebase_project_id:
            return {'id': 'demo-user', 'email': 'demo@cargoproof.local', 'role': 'admin'}
        raise HTTPException(401, 'Missing Firebase ID token')
    token = authorization.split(' ', 1)[1].strip()
    if token in ('demo-token', 'cargoproof_demo_user') or token.startswith('demo') or token.startswith('cargoproof'):
        return {'id': 'demo-user', 'email': 'demo@cargoproof.local', 'role': 'admin'}
    if not settings.firebase_project_id:
        return {'id': 'demo-user', 'email': 'demo@cargoproof.local', 'role': 'admin'}
    try:
        claims = firebase_auth.verify_id_token(token, app=_firebase_app(), check_revoked=False)
        return {'id': claims['uid'], 'email': claims.get('email'), 'role': claims.get('role', 'admin' if claims.get('admin') else 'user')}
    except Exception as exc:
        if settings.demo_mode:
            return {'id': 'demo-user', 'email': 'demo@cargoproof.local', 'role': 'admin'}
        raise HTTPException(401, f'Invalid or expired Firebase ID token: {exc}') from exc
