# 🎭 LIMA Backend — API for Improv Theater Management

[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green?logo=fastapi)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%20async-orange)](https://docs.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?logo=postgresql)](https://www.postgresql.org/)
[![Railway](https://img.shields.io/badge/Deployed%20on-Railway-purple?logo=railway)](https://railway.app)
[![Tests](https://img.shields.io/badge/Tests-95%20passing-brightgreen)](./tests/)
[![License](https://img.shields.io/badge/License-MIT-blue)](./LICENSE)

> Production-ready REST API backend for **LIMA** (Ligue d'Improvisation du Maine-et-Loire), an improv theater association managing 60+ members, show seasons, event scheduling, and cast assignments.

---

## ✨ Features

- 🔐 **JWT Authentication** — Secure login, account activation via email, password reset
- 👥 **Member Management** — Full CRUD, HelloAsso CSV import, role management, commission assignment
- 📅 **Season & Event Management** — Season lifecycle, event scheduling, Excel calendar import
- 🎭 **Show Alignments** — Cast assignment grid (players, MJ, MC, DJ, Coach, Referee per show)
- 🎪 **Show Plans** — Flexible show configuration with JSON metadata
- 📊 **Activity Tracking** — Per-user request logging, admin analytics dashboard (DAU, top pages, errors)
- 📧 **Email Service** — Async SMTP (aiosmtplib), activation, password reset, and 24h reminder emails
- 🛡️ **Rate Limiting** — slowapi on all auth endpoints
- 🔍 **Admin Stats API** — Recent activity, login stats, daily active users

---

## 🏗️ Architecture

```
React Frontend (limaimpro.duckdns.org)
        │
        ▼
FastAPI (Railway) ─── PostgreSQL 16 (Railway)
        │
        ├── /auth          JWT auth, activation, password reset
        ├── /members       Member CRUD, CSV import
        ├── /seasons       Season management
        ├── /events        Event scheduling, Excel import, cast
        ├── /alignments    Show casting grid
        ├── /show-plans    Show configuration
        ├── /commissions   Commission management
        ├── /settings      Association settings (DB-persisted)
        └── /admin         Activity tracking, analytics
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- PostgreSQL 16 (or SQLite for dev)

### Local Development

```bash
# Clone
git clone https://github.com/versila22/lima-backend.git
cd lima-backend

# Setup venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Environment
cp .env.example .env
# Edit .env: DATABASE_URL, JWT_SECRET, SMTP settings

# Run migrations
alembic upgrade head

# Start
uvicorn app.main:app --reload --port 8001
```

API available at `http://localhost:8001` · Docs at `http://localhost:8001/docs`

---

## 📡 API Reference

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login → JWT token |
| POST | `/auth/activate` | Activate account with token + password |
| POST | `/auth/forgot-password` | Request password reset |
| POST | `/auth/reset-password` | Reset with token + new password |
| GET | `/auth/me` | Current user profile |

### Members
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/members` | List members (filterable by season) |
| POST | `/members` | Create member (admin) |
| POST | `/members/import` | Import from HelloAsso CSV |
| PUT | `/members/{id}/role` | Update member role (admin) |

### Events & Alignments
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/events` | List events |
| POST | `/events` | Create event (admin) |
| GET | `/events/{id}/cast` | Get show cast assignments |
| POST | `/events/import-calendar` | Import Excel calendar |
| GET | `/alignments` | List casting grids |
| POST | `/alignments/{id}/assign` | Assign player to event role |

### Admin Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/activity/recent` | Recent activity logs |
| GET | `/admin/activity/stats` | DAU, top pages, errors, avg response time |
| GET | `/admin/activity/logins` | Login attempts (success/failure) |

---

## 🔒 Security

- **JWT** — HS256, configurable expiry, startup validation (rejects insecure defaults in production)
- **Passwords** — pbkdf2_sha256 (passlib) — bcrypt-compatible, Python 3.13 safe
- **Rate Limiting** — slowapi: 5 req/min on `/auth/login`, 3 req/min on `/auth/forgot-password`
- **CORS** — Explicit allowed origins (no wildcard in production)
- **Activity Logging** — Every request logged with user, path, status, response time

---

## 🧪 Tests

```bash
JWT_SECRET=test-secret python -m pytest tests/ -v
```

**95 tests** covering:
- Auth flows (login, activation, password reset, token expiry)
- Members, seasons, events, venues, alignments, commissions, show plans
- Admin activity endpoints
- Rate limiting, 401/403/404 handling, IDOR protection

---

## 🌐 Deployment (Railway)

```bash
# Required env vars on Railway
JWT_SECRET=<strong-random-secret>
DATABASE_URL=postgresql://...
SMTP_HOST=smtp.example.com
SMTP_USER=noreply@lima.asso.fr
SMTP_PASSWORD=...
FRONTEND_URL=https://limaimpro.duckdns.org
```

Railway auto-deploys on push to `main`. Migration runs automatically at startup (`alembic upgrade head`).

### Scheduled reminder emails

A daily script sends reminder emails to members assigned to **published** events happening in the next 24 hours.

```bash
cd /data/.openclaw/workspace/lima/backend
python scripts/send_reminders.py
```

Recommended setup:
- run it once per day via cron or Railway scheduled job
- keep `SMTP_*` variables configured so emails are actually delivered
- keep `FRONTEND_URL` pointing to the public members app so the email CTA opens `/mon-planning`

Example cron (every day at 09:00):

```cron
0 9 * * * cd /data/.openclaw/workspace/lima/backend && /usr/bin/python3 scripts/send_reminders.py >> /var/log/lima-reminders.log 2>&1
```

---

## 📊 Tech Stack

| Tool | Purpose | Version |
|------|---------|---------|
| FastAPI | Web framework | 0.111 |
| SQLAlchemy | ORM (async) | 2.0 |
| Alembic | DB migrations | latest |
| PostgreSQL | Database | 16 |
| asyncpg | Async PG driver | 0.29 |
| passlib | Password hashing | 1.7 |
| python-jose | JWT | 3.3 |
| slowapi | Rate limiting | 0.1 |
| aiosmtplib | Async SMTP | latest |
| pytest + pytest-asyncio | Testing | latest |

---

## 🗺️ Roadmap

- [ ] WebSocket for real-time alignment updates
- [ ] Google Calendar integration
- [ ] Push notifications (email/Telegram)
- [ ] Availability management for players
- [ ] AI-powered show plan generation (Gemini)
- [ ] HelloAsso webhook auto-import

---

## 🤝 Contributing

PRs welcome! Especially interested in:
- **Gemini integration** for automated show plan suggestions
- **HelloAsso webhook** for real-time member sync
- **i18n** (currently French-only)

---

## 📄 License

MIT — See [LICENSE](./LICENSE)

> Built with ❤️ for the LIMA improv community in Angers, France.
