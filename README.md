# Event Registration System

A Django REST Framework backend for managing events and user registrations.

This project is a reusable API/backend template for event registration, built with Django REST Framework.

## Features

- Event listing, event detail, pagination, search, and date filtering
- User registration and JWT login
- Attendee and organizer roles
- Organizer-only event creation and owner-only event updates/deletes
- Authenticated event registration
- Authenticated view of a user's active registrations
- Authenticated registration cancellation
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
  accounts/
    models.py
    admin.py
    permissions.py
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
```

Run migrations:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
```

Create an admin user:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

Start the development server:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

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
| `POST` | `/auth/register/` | Create a user and return JWT access/refresh tokens |
| `POST` | `/auth/token/` | Login and return JWT access/refresh tokens |
| `POST` | `/auth/token/refresh/` | Refresh a JWT access token |
| `GET` | `/events/` | List paginated events with optional search/date filters |
| `POST` | `/events/` | Create an event as an organizer |
| `GET` | `/events/<id>/` | View event details |
| `PUT` | `/events/<id>/` | Replace an event as its organizer |
| `PATCH` | `/events/<id>/` | Update an event as its organizer |
| `DELETE` | `/events/<id>/` | Delete an event as its organizer |
| `POST` | `/events/<id>/register/` | Register for an event |
| `GET` | `/my-registrations/` | View current user's active registrations |
| `POST` | `/registrations/<id>/cancel/` | Cancel a registration |
| `GET` | `/admin/` | Django admin panel |

JWT login returns an `access` token and a `refresh` token. Protected endpoints require:

```http
Authorization: Bearer your_access_token_here
```

JWT access tokens last 5 minutes. Refresh tokens last 1 day, rotate on refresh, and old refresh tokens are blacklisted after rotation.

Event list examples:

```http
GET /events/?page=1&page_size=10
GET /events/?search=django
GET /events/?timeframe=upcoming
GET /events/?date_from=2026-08-01&date_to=2026-08-31
```

New users start as attendees. To create, update, or delete events through the API, promote the user to organizer from the Django admin profile page.

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
