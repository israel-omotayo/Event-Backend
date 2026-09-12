# Event Registration API

Django REST Framework backend for event discovery, registration, waitlists, organizer event management, JWT auth, Google auth, email flows, and Supabase Storage event images.

## Stack

- Django / DRF
- PostgreSQL
- Simple JWT
- Huey
- Supabase Storage
- Sentry
- drf-spectacular

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` in the project root:

```env
SECRET_KEY=your-secret-key
DEBUG=True
POSTGRES_DB=event_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-postgres-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_SSLMODE=
DEFAULT_FROM_EMAIL=Event API <noreply@example.com>
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
RESEND_API_KEY=
GOOGLE_OAUTH_CLIENT_ID=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET=event-images
EVENT_IMAGE_MAX_UPLOAD_SIZE=5242880
HUEY_NAME=event-api
HUEY_IMMEDIATE=True
HUEY_WORKERS=1
HUEY_WORKER_TYPE=thread
SENTRY_DSN=
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0
```

Run:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

Docs:

```txt
http://127.0.0.1:8000/api/docs/
http://127.0.0.1:8000/api/schema/
```

## Render Free Deploy

Use:

```txt
Build command: bash render-build.sh
Start command: gunicorn reg_system.wsgi:application --workers 1 --threads 2 --timeout 120
```

Required production env:

```env
SECRET_KEY=your-production-secret
DEBUG=False
ALLOWED_HOSTS=your-service-name.onrender.com
POSTGRES_DB=postgres
POSTGRES_USER=your-supabase-pooler-user
POSTGRES_PASSWORD=your-supabase-password
POSTGRES_HOST=your-supabase-session-pooler-host
POSTGRES_PORT=5432
POSTGRES_SSLMODE=require
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=strong-password
DEFAULT_FROM_EMAIL=Event API <noreply@yourdomain.com>
RESEND_API_KEY=your-resend-key
GOOGLE_OAUTH_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_STORAGE_BUCKET=event-images
HUEY_IMMEDIATE=True
SENTRY_DSN=
SENTRY_ENVIRONMENT=production
```

`render-build.sh` installs dependencies, runs migrations, and creates or updates the admin user from `DJANGO_SUPERUSER_*`.

Render Free cannot run a separate always-on Huey worker, so keep `HUEY_IMMEDIATE=True`.

## Main Endpoints

See [API_DOCS.md](API_DOCS.md) for request examples.

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/auth/register/` | Register inactive user and send verification code |
| `POST` | `/auth/verify/` | Verify email |
| `POST` | `/auth/token/` | Login with email/password |
| `POST` | `/auth/google/` | Login/register with Google ID token |
| `POST` | `/auth/token/refresh/` | Refresh JWT |
| `POST` | `/auth/logout/` | Blacklist refresh token |
| `POST` | `/auth/password/change/` | Change password |
| `POST` | `/auth/password/reset/request/` | Request password reset |
| `POST` | `/auth/password/reset/confirm/` | Confirm password reset |
| `GET` | `/events/` | List events |
| `POST` | `/events/` | Create event as organizer |
| `GET` | `/events/<id>/` | Event detail |
| `PUT/PATCH/DELETE` | `/events/<id>/` | Manage own event |
| `PUT/DELETE` | `/events/<id>/image/` | Manage event cover image |
| `POST` | `/events/<id>/register/` | Register for event |
| `POST` | `/events/<id>/waitlist/` | Join waitlist |
| `GET` | `/my-registrations/` | Current user's registrations |
| `GET` | `/my-waitlist/` | Current user's waitlist entries |
| `POST` | `/registrations/<id>/cancel/` | Cancel registration |
| `POST` | `/waitlist/<id>/cancel/` | Cancel waitlist entry |

Protected endpoints use:

```http
Authorization: Bearer <access_token>
```

New users are attendees. Promote organizers from Django admin by editing their profile.

## Storage

Event images upload through:

```txt
PUT /events/<id>/image/
multipart field: image
```

Allowed: JPEG, PNG, WebP. Default max size: 5 MB. The backend validates actual image bytes before uploading to Supabase Storage.

## Tests

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test --keepdb
.\.venv\Scripts\python.exe tools\load_test_event_flow.py
```
