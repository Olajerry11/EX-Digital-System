# EX-DIGITAL — Enterprise Attendance Management System

> A production-grade, autonomous, highly scalable attendance management system for universities. Built with FastAPI, React 18 PWA, PostgreSQL 15, and Docker.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                     React 18 PWA (Vite)                  │
│  Admin Dashboard │ Lecturer Dashboard │ Student Scanner  │
│  Glassmorphism + Tailwind CSS + Zustand + Framer Motion  │
└─────────────────────────┬────────────────────────────────┘
                          │ HTTPS / REST + SSE
        ┌─────────────────┴────────────────┐
        │        FastAPI Core API          │
        │  JWT Auth │ RBAC │ Async SQLAlch │
        │  Rate Limiting (slowapi)         │
        └──────────┬───────────────────────┘
                   │
    ┌──────────────┼─────────────────┐
    │              │                 │
┌───▼───┐   ┌──────▼──┐   ┌────────▼──────┐
│  PG   │   │  Redis  │   │ Flask Gateway │
│  15   │   │    7    │   │ HMAC ERP Sync │
└───────┘   └─────────┘   └───────────────┘
```

## Quick Start

### Prerequisites
- Docker Desktop (v24+)
- Docker Compose v2

### 1. Clone & Configure
```bash
git clone <repo-url> && cd EX-Digital-System
cp .env.example .env
# Edit .env — set JWT_SECRET, HMAC_SECRET, POSTGRES_PASSWORD
```

### 2. Launch
```bash
docker compose up --build -d
```

### 3. Services
| Service   | URL                          |
|-----------|------------------------------|
| Frontend  | http://localhost:3000        |
| API Docs  | http://localhost:8000/docs   |
| API       | http://localhost:8000        |
| Gateway   | http://localhost:5001        |

### 4. Seed Data (first run)
```bash
# Create admin user via API
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <admin_token>" \
  -d '{"email":"admin@ex.edu","password":"Admin1234","full_name":"System Admin","role":"admin"}'
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET` | ✅ | Min 32-char random secret for signing JWTs |
| `HMAC_SECRET` | ✅ | Secret for ERP webhook HMAC-SHA256 verification |
| `POSTGRES_PASSWORD` | ✅ | PostgreSQL database password |
| `DATABASE_URL` | ✅ | Async PostgreSQL URL (postgresql+asyncpg://...) |
| `GATEWAY_API_KEY` | ✅ | API key for ERP export endpoint |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | Default: 30 |
| `SESSION_DURATION_MINUTES` | Optional | Default: 10 |
| `SESSION_GRACE_PERIOD_MINUTES` | Optional | Default: 5 |
| `QR_SCAN_WINDOW_MINUTES` | Optional | Default: 5 |
| `CORS_ORIGINS` | Optional | JSON array of allowed origins |

---

## User Roles

| Role | Access |
|------|--------|
| **Admin** | Full system access: user CRUD, course management, attendance oversight, ERP sync |
| **Lecturer** | Start/end sessions, live monitor, manual marking, course history |
| **Student** | QR scanner (PWA), personal attendance history, offline sync |

---

## API Reference

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/auth/login` | None | Login (email or matric + password) → JWT |
| POST | `/auth/register` | Admin | Create user |
| GET | `/auth/me` | Any | Current user profile |
| POST | `/auth/reset-password` | Admin | Reset any user's password |
| POST | `/auth/bulk-import` | Admin | CSV bulk user creation |

### Courses
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/courses/` | Any | Role-scoped course list |
| POST | `/courses/` | Admin/Lecturer | Create course |
| PATCH | `/courses/{id}` | Admin | Update/archive course |
| POST | `/courses/{id}/enroll` | Admin | Enroll students |
| POST | `/courses/{id}/assign-lecturer` | Admin | Assign lecturer |
| GET | `/courses/{id}/attendance/stats` | Any | Attendance statistics |

### Sessions
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/sessions/start` | Lecturer | Start attendance session (returns QR UUID) |
| GET | `/sessions/active` | Lecturer | List active sessions |
| POST | `/sessions/{id}/end` | Lecturer | End session |
| GET | `/sessions/{id}/attendees` | Lecturer | Attendee list |
| GET | `/sessions/{id}/attendees/stream` | Lecturer | SSE live stream |

### Attendance
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/attendance/rapid-scan` | Student | **Core endpoint** — batch QR scan sync |
| POST | `/attendance/manual` | Lecturer | Manually mark a student present |
| GET | `/attendance/my` | Student | Personal attendance history |

### Admin
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/admin/dashboard/stats` | Admin | System-wide statistics |
| GET | `/admin/users` | Admin | List all users |
| PATCH | `/admin/users/{id}` | Admin | Update user |
| DELETE | `/admin/users/{id}` | Admin | Deactivate user (soft delete) |

### Gateway (Flask :5001)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/webhook/erp-sync` | HMAC sig | Receive signed ERP attendance data |
| GET | `/erp/attendance-export` | X-API-Key | Export unsynced records to ERP |
| POST | `/erp/trigger-sync` | X-API-Key | Trigger manual ERP sync |

---

## Offline-First PWA

The student interface works fully offline:

1. **Scans** are stored in **IndexedDB** (via `idb`) with session UUID + timestamp
2. **Background sync** fires on `window.addEventListener('online', ...)` and every 30 seconds
3. Scans are flushed to `/attendance/rapid-scan` in **batches of 50**
4. A **sync progress indicator** shows pending/synced/failed counts
5. The server-side rapid-scan endpoint is **idempotent** — duplicate scans are detected and skipped

---

## Security

- Passwords hashed with **bcrypt** (work factor 12)
- JWTs signed with **HS256**, 30-minute expiry
- **Rate limiting**: 10/min on login, 30/min on rapid-scan (slowapi)
- **HMAC-SHA256** with 5-minute timestamp tolerance on gateway webhook
- **RBAC** enforced via `require_role()` FastAPI dependency
- Input validated via **Pydantic v2** field_validators
- Non-root Docker containers
- Production secret validation on startup (exits if defaults detected)

---

## Development

### Backend (local)
```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend (local)
```bash
cd frontend
npm install
npm run dev   # → http://localhost:5173
```

### Database Migrations
```bash
cd backend
alembic upgrade head          # apply all migrations
alembic revision --autogenerate -m "description"  # generate new migration
alembic downgrade -1          # roll back one step
```

---

## Project Structure

```
EX-Digital-System/
├── backend/
│   ├── app/
│   │   ├── main.py              ← FastAPI factory + lifespan (auto-migrate)
│   │   ├── config.py            ← Pydantic Settings + startup validation
│   │   ├── database.py          ← Async engine + session factory
│   │   ├── models/__init__.py   ← SQLAlchemy ORM models (6 tables)
│   │   ├── schemas/__init__.py  ← Pydantic v2 request/response schemas
│   │   ├── routers/
│   │   │   ├── auth.py          ← Login, register, bulk import
│   │   │   ├── courses.py       ← Course CRUD + enrollment
│   │   │   ├── sessions.py      ← Session lifecycle + SSE stream
│   │   │   ├── attendance.py    ← Rapid scan (offline sync), manual mark
│   │   │   └── admin.py         ← Admin dashboard + user management
│   │   └── utils/
│   │       ├── security.py      ← JWT + bcrypt + RBAC dependency
│   │       └── helpers.py       ← Session key generator, HMAC utils
│   ├── alembic/
│   │   ├── env.py               ← Async Alembic environment
│   │   └── versions/
│   │       └── 0001_initial.py  ← Complete initial schema migration
│   ├── Dockerfile
│   ├── alembic.ini
│   └── requirements.txt
├── gateway/
│   ├── app.py                   ← Flask HMAC webhook + ERP endpoints
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── main.tsx             ← App entry + router + toast
│   │   ├── index.css            ← Glassmorphism design system
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx    ← Dual-mode login (email/matric)
│   │   │   ├── AdminDashboard.tsx
│   │   │   ├── LecturerDashboard.tsx
│   │   │   └── StudentDashboard.tsx ← QR scanner + offline queue
│   │   ├── components/
│   │   │   ├── NetworkStatusPill.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   ├── store/
│   │   │   └── authStore.ts     ← Zustand + persist middleware
│   │   └── lib/
│   │       ├── apiClient.ts     ← Axios + JWT interceptor + retry
│   │       ├── offlineQueue.ts  ← IndexedDB queue + background sync
│   │       └── useNetworkStatus.ts
│   ├── public/manifest.json     ← PWA manifest
│   ├── vite.config.ts           ← Vite + PWA plugin (Workbox)
│   ├── tailwind.config.js       ← Design tokens
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## License

MIT © 2026 EX-DIGITAL
