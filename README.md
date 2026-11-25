# AURELIS — Financial Intelligence Studio

AURELIS is a FastAPI-powered financial consulting website with a client account portal, private enquiry tracking and an owner-only enquiry inbox.

## What works in this project

- Public marketing website at `/` with services, demo dashboard, calculators and CSV P&L analysis.
- Client registration and login at `/portal`.
- Passwords stored as salted PBKDF2-HMAC-SHA256 hashes (never plaintext).
- Signed session token in an HttpOnly, SameSite=Lax cookie.
- Authenticated project enquiries stored in a SQL database.
- Clients can view only their own enquiries and see status and owner notes.
- Owner-only inbox to review enquiries, change status and leave client-visible updates.
- Optional email notification to the owner through Resend.
- SQLite for local development; PostgreSQL for hosted production.
- Privacy and terms starter pages at `/privacy` and `/terms`.
- Excel template and sample CSV retained.

## Local setup (Windows)

Install Python 3.11 or newer. Open this folder in VS Code and run in PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:APP_ENV="development"
uvicorn backend.main:app --reload
```

Open `http://127.0.0.1:8000` and `http://127.0.0.1:8000/portal`.

Local development uses `data/aurelis.db`. To create an owner/admin account locally before starting the server, set these variables in the same PowerShell session:

```powershell
$env:ADMIN_EMAIL="your-real-email@example.com"
$env:ADMIN_PASSWORD="a-long-unique-password-at-least-12-chars"
$env:ADMIN_NAME="Your Name"
uvicorn backend.main:app --reload
```

On first startup the account is created as the owner. If that email already registered, it is promoted to admin. Do not use a password you use anywhere else.

## Publish it online — recommended low-cost setup

The app needs a Python web host and a persistent PostgreSQL database. A simple setup is **Render (web hosting) + Neon (PostgreSQL) + a domain registrar + Resend (optional email notifications)**. Free hosting tiers can sleep, have usage limits or change; use a paid always-on service for a business-critical website.

### 1. Create a GitHub repository

1. Create/sign in to GitHub.
2. Create a private repository named `aurelis-financial-studio`.
3. Upload the contents of this project ZIP into the repository root (not an extra nested folder).
4. Confirm `render.yaml`, `requirements.txt`, `backend/`, `static/`, `index.html` and `portal.html` are visible at the repository root.
5. Never upload `.env`, passwords, API keys, customer data or `data/aurelis.db`.

### 2. Create a PostgreSQL database on Neon

1. Create a project at https://neon.tech/.
2. Open the project's **Connect** panel.
3. Copy the PostgreSQL connection string. Keep `sslmode=require` and use the pooled connection string for a typical web service.
4. Store it privately. It contains database credentials. Do not paste it into source code or send it in chat.

The app converts `postgresql://` into the psycopg SQLAlchemy driver format automatically.

### 3. Deploy the app on Render

1. Create an account at https://render.com/ and connect GitHub.
2. Choose **New → Blueprint** and select your `aurelis-financial-studio` repository. Or choose **New → Web Service** and use the values below.
3. Runtime: Python. Build command: `pip install -r requirements.txt`. Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`. Health check: `/api/health`.
4. Add these environment variables in Render's Environment section:

| Variable | Value |
|---|---|
| `APP_ENV` | `production` |
| `SITE_URL` | Your canonical public URL, e.g. `https://your-domain.com` |
| `COOKIE_SECURE` | `true` |
| `JWT_SECRET` | A long random secret (Render can generate one) |
| `DATABASE_URL` | Your Neon PostgreSQL connection string |
| `ADMIN_EMAIL` | Your own business email |
| `ADMIN_PASSWORD` | A unique password of at least 12 characters |
| `ADMIN_NAME` | Your name or business owner name |
| `OWNER_NOTIFICATION_EMAIL` | Where you want new enquiry alerts sent |
| `RESEND_API_KEY` | Optional; API key from Resend |
| `RESEND_FROM` | A sender address on a domain verified with Resend |

5. The `ADMIN_EMAIL` and `ADMIN_PASSWORD` variables bootstrap the owner account on first start. Keep them private. The owner account is created automatically if it does not exist; an existing matching account is promoted to admin without changing its password.
6. Deploy. Render will give you a temporary address similar to `https://your-service.onrender.com`.
7. Test `/api/health`, `/`, `/portal`, registration, login, enquiry submission and the admin inbox before adding a custom domain.

Render free web services can spin down after inactivity and take time to wake; check the current plan details before choosing it for a live client-facing business. Do not use ephemeral local SQLite storage for a production deployment. Use Neon/Postgres as `DATABASE_URL`.

### 4. Create your domain

Choose and purchase a domain through a registrar such as Namecheap, Cloudflare Registrar (where available) or another reputable registrar. Domain names below are only ideas; availability and trademark rights have not been checked:

- `aurelisfinance.com`
- `aurelisintelligence.com`
- `aurelisstudio.com`
- `aurelisfinancial.com`

Before buying, check domain availability, social handles, company-name and trademark conflicts. A domain purchase and legal brand clearance are separate things.

In Render: open your web service → **Settings → Custom Domains → Add Custom Domain** and enter the domain you purchased. Follow the exact DNS records Render displays at your registrar. For a `www` hostname, this is generally a CNAME to your exact `onrender.com` service hostname. Root-domain records vary by DNS provider; use Render's displayed instructions. Remove conflicting AAAA records if Render's current instructions require it. Verify the domain in Render; Render provisions TLS/HTTPS after successful verification.

### 5. Get email notifications when a client submits a request

The platform saves every request to PostgreSQL and shows it in your admin inbox even if email notifications are not configured.

For email alerts:
1. Create an account at https://resend.com/.
2. Add a domain you own and complete the DNS verification records Resend provides.
3. Create an API key.
4. Set `RESEND_API_KEY`, `RESEND_FROM` (on your verified domain) and `OWNER_NOTIFICATION_EMAIL` in Render.
5. Redeploy and submit a test enquiry from a separate client account.

Never put the Resend API key in frontend JavaScript or GitHub.

### 6. Admin and client workflows

- Clients visit `/portal`, register and log in.
- They submit a project enquiry from the **New enquiry** tab.
- They can view their own request and status in **My requests**.
- The owner logs into `/portal` using the `ADMIN_EMAIL` account and sees **Admin inbox**.
- The owner can change status and add an update visible to that client.
- New enquiry email notifications are optional; the database inbox remains the source of truth.

## Pre-launch checklist — do not skip

- Replace `[INSERT VERIFIED BUSINESS EMAIL]` and `[INSERT LEGAL BUSINESS NAME]` in `privacy.html` and `terms.html`.
- Review the privacy notice, terms, retention/deletion process and client engagement letter with a qualified professional for your jurisdiction.
- Verify the AURELIS name and domain are legally available before using the brand commercially.
- Configure a real business email and test email delivery.
- Use a strong, unique admin password and a stable, random `JWT_SECRET`.
- Confirm the database is PostgreSQL and backups are enabled.
- Test client A cannot see client B's enquiries; test a non-admin account cannot access `/api/admin/enquiries`.
- Use HTTPS only in production (`COOKIE_SECURE=true`).
- Set up database backups, access reviews, monitoring and a process to delete/retain client records.
- Do not collect bank passwords, card data or unnecessary sensitive personal information through the enquiry form. Agree a secure document-transfer process before collecting client financial records.
- Review every financial calculation and model before delivering paid work. Demo dashboard numbers are fictional.

## Important limitations

This is a deployable MVP, not a fully audited enterprise platform. It currently provides email/password registration without email verification or self-service password reset. It does not include payments, document uploads, live Power BI embedding, automated invoicing, calendar booking, multi-staff roles or client email notifications for every status change. Add and test those features before promising them to customers. The CSV analyzer is descriptive only and is not an audit or complete financial model.

The privacy and terms pages are starter drafts and must be completed and reviewed before public commercial use.

## Power BI

The project includes a Power BI-friendly CSV schema and Excel template, but no live Power BI tenant or embedded report. Live embedding requires your own Microsoft account, workspace, licensing and secure embedding configuration. Never place Power BI secrets or access tokens in browser JavaScript.
