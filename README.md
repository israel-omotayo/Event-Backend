# Event Registration System

A Django REST Framework backend for managing events and user registrations.

This project is a reusable API/backend template for event registration, built with Django REST Framework.

## Features

- Event listing, event detail, pagination, search, and date filtering
- Email verification before JWT login
- Password change, logout, and password reset endpoints
- Google ID-token auth that returns local JWT tokens
- Attendee and organizer roles
- Organizer-only event creation and owner-only event updates/deletes
- Supabase Storage event cover images
- Authenticated event registration
- Explicit waitlist flow for full events
- Authenticated view of a user's active registrations
- Authenticated registration cancellation
- Background email delivery with Huey
- Sentry-ready error logging
- Django admin panel for creating and managing events
- PostgreSQL database configuration
- Swagger/OpenAPI documentation
- API test coverage for the main flows

## Tech Stack

- Python
- Django
- Django REST Framework
- PostgreSQL
- JWT Authentication
- Google ID token verification
- Huey for background tasks
- Sentry SDK for error monitoring
- Supabase Storage for event cover images
- drf-spectacular for Swagger/OpenAPI docs

## Project Structure

```txt
event_reg/
  manage.py
  requirements.txt
  README.md
  API_DOCS.md
  reg_system/
    settings.py
    urls.py
  events/
    models.py
    serializers.py
    views.py
    urls.py
    admin.py
    tests.py
    tasks.py
    storage.py
  accounts/
    models.py
    admin.py
    permissions.py
    tasks.py
```

## Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key
DEBUG=True
POSTGRES_DB=event_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-postgres-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DEFAULT_FROM_EMAIL=Event API <noreply@example.com>
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
RESEND_API_KEY=
GOOGLE_OAUTH_CLIENT_ID=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_STORAGE_BUCKET=event-images
EVENT_IMAGE_MAX_UPLOAD_SIZE=5242880
HUEY_NAME=event-api
HUEY_WORKERS=1
HUEY_WORKER_TYPE=thread
HUEY_IMMEDIATE=True
SENTRY_DSN=
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0
```

For Render Free + Supabase session pooler, use the Supabase pooler values:

```env
DEBUG=False
POSTGRES_DB=postgres
POSTGRES_USER=your-pooler-user
POSTGRES_PASSWORD=your-supabase-password
POSTGRES_HOST=your-supabase-session-pooler-host
POSTGRES_PORT=5432
POSTGRES_SSLMODE=require
DEFAULT_FROM_EMAIL=Event API <noreply@yourdomain.com>
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
RESEND_API_KEY=your-resend-api-key
GOOGLE_OAUTH_CLIENT_ID=your-google-web-client-id.apps.googleusercontent.com
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=strong-password
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
SUPABASE_STORAGE_BUCKET=event-images
EVENT_IMAGE_MAX_UPLOAD_SIZE=5242880
HUEY_NAME=event-api
HUEY_IMMEDIATE=True
HUEY_WORKERS=1
HUEY_WORKER_TYPE=thread
SENTRY_DSN=your-sentry-dsn
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0
```

Render Free cannot run a separate always-on background worker. Keep `HUEY_IMMEDIATE=True` on Free so email tasks execute after the database transaction commits inside the web service process. When you upgrade to a paid Render plan and add a background worker, change production to `HUEY_IMMEDIATE=False`.

Run migrations:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

Create an admin user:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

For Render Free, use the deployment build script because pre-deploy commands are not available on the Free web service plan:

```txt
Build command: bash render-build.sh
Start command: gunicorn reg_system.wsgi:application --workers 1 --threads 2 --timeout 120
```

`render-build.sh` installs dependencies, runs migrations, and creates or updates the superuser when these env vars are set:

```env
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=strong-password
```

The superuser setup is idempotent, so rerunning deploys will update the same admin user instead of creating duplicates.

Start the development server:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Run the Huey worker in a separate terminal if you set `HUEY_IMMEDIATE=False` locally:

```powershell
.\.venv\Scripts\python.exe manage.py run_huey
```

With the default local `HUEY_IMMEDIATE=True`, Huey tasks execute immediately in-process for easier development.

## API Documentation

Swagger UI:

```txt
http://127.0.0.1:8000/api/docs/
```

OpenAPI schema:

```txt
http://127.0.0.1:8000/api/schema/
```

Detailed endpoint examples are in `API_DOCS.md`.

## Main Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/auth/register/` | Create an inactive user and send verification code |
| `POST` | `/auth/verify/` | Verify email and activate the user |
| `POST` | `/auth/verification/resend/` | Resend verification code for an inactive user |
| `POST` | `/auth/token/` | Login with email/password and return JWT access/refresh tokens |
| `POST` | `/auth/google/` | Login/register with a verified Google ID token and return JWT tokens |
| `POST` | `/auth/token/refresh/` | Refresh a JWT access token |
| `POST` | `/auth/logout/` | Logout by blacklisting a refresh token |
| `POST` | `/auth/password/change/` | Change password for the authenticated user |
| `POST` | `/auth/password/reset/request/` | Request a password reset token by email |
| `POST` | `/auth/password/reset/confirm/` | Confirm password reset with uid/token |
| `GET` | `/events/` | List paginated events with optional search/date filters |
| `POST` | `/events/` | Create an event as an organizer |
| `GET` | `/events/<id>/` | View event details |
| `PUT` | `/events/<id>/` | Replace an event as its organizer |
| `PATCH` | `/events/<id>/` | Update an event as its organizer |
| `DELETE` | `/events/<id>/` | Delete an event as its organizer |
| `PUT` | `/events/<id>/image/` | Upload or replace an event cover image as its organizer |
| `DELETE` | `/events/<id>/image/` | Delete an event cover image as its organizer |
| `POST` | `/events/<id>/register/` | Register for an event |
| `POST` | `/events/<id>/waitlist/` | Join waitlist for a full event |
| `GET` | `/my-registrations/` | View current user's active registrations |
| `GET` | `/my-waitlist/` | View current user's active waitlist entries |
| `POST` | `/registrations/<id>/cancel/` | Cancel a registration |
| `POST` | `/waitlist/<id>/cancel/` | Cancel a waitlist entry |
| `GET` | `/admin/` | Django admin panel |

JWT login returns an `access` token and a `refresh` token. Protected endpoints require:

```http
Authorization: Bearer your_access_token_here
```

JWT access tokens last 60 minutes. Refresh tokens last 1 day, rotate on refresh, and old refresh tokens are blacklisted after rotation.

Password change requires the current password and refresh token:

```json
{
  "old_password": "OldPass123!",
  "new_password": "NewStrongPass123!",
  "confirm_new_password": "NewStrongPass123!",
  "refresh": "your_refresh_token_here"
}
```

Logout requires the refresh token:

```json
{
  "refresh": "your_refresh_token_here"
}
```

Password reset uses Django's built-in reset token generator. Request reset with an email, then confirm with the emailed `uid` and `token`.

Google auth expects an ID token from Google Identity Services:

```json
{
  "id_token": "google_id_token_from_frontend"
}
```

The backend verifies the token against `GOOGLE_OAUTH_CLIENT_ID`, requires Google's `email_verified` claim, creates or links the local user by email, stores Google's stable `sub` on the profile, and returns normal JWT `access` and `refresh` tokens.

Event list examples:

```http
GET /events/?page=1&page_size=10
GET /events/?search=django
GET /events/?timeframe=upcoming
GET /events/?date_from=2026-08-01&date_to=2026-08-31
```

New users start as attendees. To create, update, or delete events through the API, promote the user to organizer from the Django admin profile page.

Registration cancellation requires confirmation:

```json
{
  "confirm": true
}
```

If an event is full, `POST /events/<id>/register/` returns `event_full`; clients should show a join-waitlist action and call `POST /events/<id>/waitlist/`.

## Event Images

Event cover images are stored in Supabase Storage. The API stores the object path in `Event.image_path` and returns a computed public `image_url` in event responses.

Create a public Supabase Storage bucket named by `SUPABASE_STORAGE_BUCKET`, defaulting to:

```txt
event-images
```

Upload or replace a cover image as the event organizer:

```http
PUT /events/1/image/
Authorization: Bearer your_access_token_here
Content-Type: multipart/form-data
```

Use form field:

```txt
image
```

Allowed types are JPEG, PNG, and WebP. The default max size is 5 MB. The API verifies the real image bytes with Pillow before uploading. The backend uploads with `SUPABASE_SERVICE_ROLE_KEY`, so never expose that key in frontend code.

## Background Emails

Email tasks are triggered with Huey only after the surrounding database transaction commits.

On Render Free, use one web service:

```txt
Web Service
Build command: pip install -r requirements.txt
Start command: gunicorn reg_system.wsgi
```

Set:

```env
HUEY_IMMEDIATE=True
```

With `HUEY_IMMEDIATE=True`, email tasks run in the web service process after commit. This works on the Free tier, but it is not as durable as a separate worker because the web process can restart.

When you upgrade to a paid Render plan, create two services from the same repo:

```txt
Web Service
Build command: pip install -r requirements.txt
Start command: gunicorn reg_system.wsgi
```

```txt
Background Worker
Build command: pip install -r requirements.txt
Start command: python manage.py run_huey
```

Then set:

```env
HUEY_IMMEDIATE=False
```

Huey uses Postgres storage when not running in immediate mode and has result storage disabled because email tasks do not need return values.

## Logging and Sentry

Logs are written to stdout/stderr so Render can collect them. Set `SENTRY_DSN` to send Django exceptions and error-level logs to Sentry.

On Render Free, Sentry events come from the web service. If you later add a paid Huey worker, that worker will also send its own errors to Sentry as long as it has the same `SENTRY_DSN`.

Useful logging env vars:

```env
SENTRY_DSN=your-sentry-dsn
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0
```

## Creating Events

Events can be created by organizers through the API or by admins in the Django admin panel:

```txt
http://127.0.0.1:8000/admin/
```

Log in with a superuser account, then add events from the `Events` section.

## Running Tests

```powershell
.\.venv\Scripts\python.exe manage.py test
```

## System Check

```powershell
.\.venv\Scripts\python.exe manage.py check
```
