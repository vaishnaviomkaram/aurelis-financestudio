"""AURELIS production-oriented client portal and enquiry API.

Run locally: uvicorn backend.main:app --reload
Production: set DATABASE_URL, JWT_SECRET, COOKIE_SECURE=true and optional Resend vars.
"""
from __future__ import annotations
import os, re, secrets, hmac, hashlib, base64, json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, Response as RawResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import create_engine, String, Text, DateTime, ForeignKey, Boolean, select, desc
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session, relationship
import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{(DATA_DIR / 'aurelis.db').as_posix()}")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://") and "+psycopg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
JWT_SECRET = os.getenv("JWT_SECRET", "")
if not JWT_SECRET and os.getenv("APP_ENV") == "production":
    raise RuntimeError("JWT_SECRET must be set in production (use a long random secret).")
if not JWT_SECRET:
    JWT_SECRET = "local-development-only-change-this-secret-" + secrets.token_urlsafe(24)
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
COOKIE_NAME = "aurelis_session"
TOKEN_HOURS = int(os.getenv("TOKEN_HOURS", "72"))

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    enquiries: Mapped[list["EnquiryRecord"]] = relationship(back_populates="user")
class EnquiryRecord(Base):
    __tablename__ = "enquiries"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    service: Mapped[str] = mapped_column(String(120))
    business: Mapped[str] = mapped_column(String(160), default="")
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="Received")
    admin_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    user: Mapped[User] = relationship(back_populates="enquiries")
Base.metadata.create_all(bind=engine)
app = FastAPI(title="AURELIS Client Platform", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=[], allow_credentials=True, allow_methods=["GET", "POST", "PATCH"], allow_headers=["Content-Type"])
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

class RegisterInput(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
class EnquiryInput(BaseModel):
    service: str = Field(min_length=2, max_length=120)
    business: str = Field(default="", max_length=160)
    message: str = Field(min_length=10, max_length=5000)
class StatusInput(BaseModel):
    status: str = Field(pattern="^(Received|Reviewing|Proposal sent|In progress|Completed|Closed)$")
    admin_note: str = Field(default="", max_length=3000)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return "pbkdf2_sha256$600000$" + base64.urlsafe_b64encode(salt).decode().rstrip("=") + "$" + base64.urlsafe_b64encode(digest).decode().rstrip("=")
def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_text, digest_text = stored.split("$")
        if algorithm != "pbkdf2_sha256": return False
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        expected = base64.urlsafe_b64decode(digest_text + "=" * (-len(digest_text) % 4))
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception: return False
# Optional first-admin bootstrap. Set these secrets in the hosting dashboard, never in source control.
_boot_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
_boot_password = os.getenv("ADMIN_PASSWORD", "")
if _boot_email and len(_boot_password) >= 12:
    with SessionLocal() as _db:
        _owner = _db.scalar(select(User).where(User.email == _boot_email))
        if _owner:
            if not _owner.is_admin:
                _owner.is_admin = True
                _db.commit()
        else:
            _db.add(User(name=os.getenv("ADMIN_NAME", "AURELIS Administrator"), email=_boot_email,
                         password_hash=hash_password(_boot_password), is_admin=True))
            _db.commit()
def token_for(user: User) -> str:
    payload = {"sub": user.id, "exp": int((datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)).timestamp())}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return body + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")
def set_session(response: Response, user: User):
    response.set_cookie(COOKIE_NAME, token_for(user), httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=TOKEN_HOURS*3600, path="/")
def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token: raise HTTPException(401, "Please log in to continue.")
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest()
        supplied = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
        if not hmac.compare_digest(expected, supplied): raise ValueError("bad signature")
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()): raise ValueError("expired")
        uid = int(payload.get("sub", 0))
    except (ValueError, TypeError, KeyError, json.JSONDecodeError): raise HTTPException(401, "Your session has expired. Please log in again.")
    user = db.get(User, uid)
    if not user: raise HTTPException(401, "Account not found. Please log in again.")
    return user
def admin_user(user: User = Depends(current_user)) -> User:
    if not user.is_admin: raise HTTPException(403, "Administrator access required.")
    return user

def notify_owner(enquiry: EnquiryRecord, user: User):
    """Optional transactional notification through Resend. DB save succeeds even if email is unavailable."""
    api_key = os.getenv("RESEND_API_KEY")
    owner = os.getenv("OWNER_NOTIFICATION_EMAIL")
    sender = os.getenv("RESEND_FROM", "AURELIS <onboarding@resend.dev>")
    if not api_key or not owner: return
    body = {"from": sender, "to": [owner], "subject": f"New AURELIS enquiry #{enquiry.id}: {enquiry.service}",
            "text": f"New project enquiry\n\nClient: {user.name}\nEmail: {user.email}\nBusiness: {enquiry.business}\nService: {enquiry.service}\nReceived: {enquiry.created_at}\n\n{enquiry.message}"}
    try:
        httpx.post("https://api.resend.com/emails", json=body, headers={"Authorization": f"Bearer {api_key}"}, timeout=8).raise_for_status()
    except Exception:
        # Do not fail the customer's submission because an optional email provider is down.
        pass

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if os.getenv("APP_ENV") == "production": response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

@app.get("/api/health")
def health(): return {"status": "ok", "service": "AURELIS client platform"}
@app.post("/api/auth/register", status_code=201)
def register(data: RegisterInput, response: Response, db: Session = Depends(get_db)):
    email = str(data.email).lower().strip()
    if db.scalar(select(User).where(User.email == email)): raise HTTPException(409, "An account with this email already exists. Please log in.")
    user = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password))
    db.add(user)
    try: db.commit()
    except Exception: db.rollback(); raise HTTPException(500, "Could not create your account. Please try again.")
    db.refresh(user); set_session(response, user)
    return {"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin}
@app.post("/api/auth/login")
def login(data: LoginInput, response: Response, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(data.email).lower().strip()))
    if not user or not verify_password(data.password, user.password_hash): raise HTTPException(401, "Email or password is incorrect.")
    set_session(response, user)
    return {"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin}
@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=COOKIE_SECURE, samesite="lax")
    return {"ok": True}
@app.get("/api/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email, "is_admin": user.is_admin}
@app.post("/api/enquiries", status_code=201)
def create_enquiry(data: EnquiryInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    record = EnquiryRecord(user_id=user.id, service=data.service.strip(), business=data.business.strip(), message=data.message.strip())
    db.add(record); db.commit(); db.refresh(record)
    notify_owner(record, user)
    return {"id": record.id, "service": record.service, "status": record.status, "created_at": record.created_at.isoformat(), "message": "Your request has been received. You can track it in your client dashboard."}
@app.get("/api/enquiries")
def my_enquiries(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(EnquiryRecord).where(EnquiryRecord.user_id == user.id).order_by(desc(EnquiryRecord.created_at))).all()
    return [{"id": r.id, "service": r.service, "business": r.business, "message": r.message, "status": r.status, "admin_note": r.admin_note, "created_at": r.created_at.isoformat()} for r in rows]
@app.get("/api/admin/enquiries")
def all_enquiries(_: User = Depends(admin_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(EnquiryRecord).order_by(desc(EnquiryRecord.created_at))).all()
    return [{"id": r.id, "client": r.user.name, "email": r.user.email, "service": r.service, "business": r.business, "message": r.message, "status": r.status, "admin_note": r.admin_note, "created_at": r.created_at.isoformat()} for r in rows]
@app.patch("/api/admin/enquiries/{enquiry_id}")
def update_enquiry(enquiry_id: int, data: StatusInput, _: User = Depends(admin_user), db: Session = Depends(get_db)):
    record = db.get(EnquiryRecord, enquiry_id)
    if not record: raise HTTPException(404, "Enquiry not found.")
    record.status = data.status; record.admin_note = data.admin_note.strip(); db.commit()
    return {"id": record.id, "status": record.status, "admin_note": record.admin_note}

# Existing demo CSV analysis remains available, with strict file size and content checks.
import csv, io
from fastapi import UploadFile, File
@app.post("/api/analyze-csv")
async def analyze_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"): raise HTTPException(400, "Upload a CSV file.")
    raw = await file.read()
    if len(raw) > 5 * 1024 * 1024: raise HTTPException(413, "File exceeds the 5 MB limit.")
    try:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        required = {"month", "revenue", "cogs", "operating_expenses"}
        if not reader.fieldnames or not required.issubset({x.strip().lower() for x in reader.fieldnames}): raise ValueError("Required headers: month,revenue,cogs,operating_expenses")
        rows=[]
        for line,row in enumerate(reader, start=2):
            n={k.strip().lower():v for k,v in row.items() if k}
            revenue=float(n["revenue"] or 0); cogs=float(n["cogs"] or 0); opex=float(n["operating_expenses"] or 0)
            if min(revenue,cogs,opex)<0: raise ValueError(f"Negative values are not supported (line {line}).")
            rows.append({"month":n["month"],"revenue":revenue,"cogs":cogs,"operating_expenses":opex,"gross_profit":revenue-cogs,"operating_profit":revenue-cogs-opex})
        if not rows: raise ValueError("The CSV contains no data rows.")
    except (UnicodeDecodeError, KeyError, ValueError) as exc: raise HTTPException(400,str(exc))
    tr=sum(x["revenue"] for x in rows); gp=sum(x["gross_profit"] for x in rows); op=sum(x["operating_profit"] for x in rows)
    return {"periods":len(rows),"totals":{"revenue":tr,"gross_profit":gp,"operating_profit":op,"gross_margin_pct":gp/tr*100 if tr else 0,"operating_margin_pct":op/tr*100 if tr else 0},"monthly":rows,"notice":"Descriptive analysis only. Validate source records and accounting classifications."}

@app.get("/", include_in_schema=False)
def website(): return FileResponse(ROOT / "index.html")
@app.get("/portal", include_in_schema=False)
def portal(): return FileResponse(ROOT / "portal.html")
@app.get("/privacy", include_in_schema=False)
def privacy(): return FileResponse(ROOT / "privacy.html")
@app.get("/terms", include_in_schema=False)
def terms(): return FileResponse(ROOT / "terms.html")
@app.get("/robots.txt", include_in_schema=False)
def robots():
    host = os.getenv("SITE_URL", "").rstrip("/")
    sitemap_line = f"\nSitemap: {host}/sitemap.xml" if host else ""
    return RawResponse("User-agent: *\nAllow: /\nDisallow: /portal\nDisallow: /api/" + sitemap_line + "\n", media_type="text/plain")
@app.get("/sitemap.xml", include_in_schema=False)
def sitemap():
    host = os.getenv("SITE_URL", "").rstrip("/")
    if not host and os.getenv("RENDER_EXTERNAL_HOSTNAME"):
        host = "https://" + os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
    if not host: return RawResponse("SITE_URL is not configured yet.", status_code=503, media_type="text/plain")
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{host}/</loc><changefreq>monthly</changefreq><priority>1.0</priority></url></urlset>'
    return RawResponse(xml, media_type="application/xml")
