"""Create/promote the AURELIS owner account using the configured database.
Set ADMIN_EMAIL, ADMIN_PASSWORD and DATABASE_URL, then run: python -m backend.create_admin
"""
import os
from sqlalchemy import select
from backend.main import SessionLocal, User, hash_password
email=os.environ.get('ADMIN_EMAIL','').strip().lower()
password=os.environ.get('ADMIN_PASSWORD','')
name=os.environ.get('ADMIN_NAME','AURELIS Administrator').strip()
if not email or len(password)<12: raise SystemExit('Set ADMIN_EMAIL and ADMIN_PASSWORD (at least 12 characters).')
with SessionLocal() as db:
    user=db.scalar(select(User).where(User.email==email))
    if user:
        user.is_admin=True
        if os.getenv('RESET_ADMIN_PASSWORD','false').lower()=='true': user.password_hash=hash_password(password)
    else:
        user=User(name=name,email=email,password_hash=hash_password(password),is_admin=True)
        db.add(user)
    db.commit()
print(f'Admin account ready: {email}')
