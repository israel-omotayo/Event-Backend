# Event Registration API Documentation

Base URL while running locally:

```txt
http://127.0.0.1:8000/
```

Interactive API documentation:

```txt
GET /api/docs/
```

OpenAPI schema:

```txt
GET /api/schema/
```

`/api/schema/` returns the OpenAPI schema, usually as YAML. `/api/docs/` uses that schema to show the Swagger UI.

## Authentication

This project uses Django's built-in user model with JWT authentication.

For protected API requests, send this header:

```http
Authorization: Bearer your_access_token_here
```

Use the access token in the `Authorization` header. Use the refresh token only with `/auth/token/refresh/`.

JWT configuration:

| Setting | Value |
| --- | --- |
| Access token lifetime | 5 minutes |
| Refresh token lifetime | 1 day |
| Refresh token rotation | Enabled |
| Refresh token blacklist after rotation | Enabled |

When refreshing a token, replace the old refresh token with the new one returned by the API.

New accounts are created with the `attendee` role. To create, update, or delete events through the API, a user must have the `organizer` role. Promote users from the Django admin by editing their profile.

## Postman Headers

For public `GET` requests:

```http
Accept: application/json
```

For requests with JSON bodies:

```http
Content-Type: application/json
Accept: application/json
```

For protected requests:

```http
Authorization: Bearer your_access_token_here
Accept: application/json
```

## Main Endpoints

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/auth/register/` | No | Create a user and return JWT access/refresh tokens |
| `POST` | `/auth/token/` | No | Login with username/password and return JWT access/refresh tokens |
| `POST` | `/auth/token/refresh/` | No | Refresh an access token |
| `GET` | `/events/` | No | List events with pagination, search, and date filters |
| `POST` | `/events/` | Organizer | Create an event |
| `GET` | `/events/<id>/` | No | View one event |
| `PUT` | `/events/<id>/` | Organizer owner | Replace one of the authenticated organizer's events |
| `PATCH` | `/events/<id>/` | Organizer owner | Update one of the authenticated organizer's events |
| `DELETE` | `/events/<id>/` | Organizer owner | Delete one of the authenticated organizer's events |
| `POST` | `/events/<id>/register/` | Yes | Register the authenticated user for an event |
| `GET` | `/my-registrations/` | Yes | View active registrations for the authenticated user |
| `POST` | `/registrations/<id>/cancel/` | Yes | Cancel one of the authenticated user's registrations |

## Admin And Documentation Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/admin/` | Django admin panel |
| `GET` | `/api/docs/` | Swagger API documentation |
| `GET` | `/api/schema/` | OpenAPI schema |

For Postman or API clients, use `/auth/token/` and the `Authorization: Bearer ...` header.

## Example Flow

Create an account:

```http
POST /auth/register/
Content-Type: application/json
```

```json
{
  "username": "john",
  "email": "john@example.com",
  "password": "password123"
}
```

Example response:

```json
{
  "id": 1,
  "username": "john",
  "email": "john@example.com",
  "access": "your_access_token_here",
  "refresh": "your_refresh_token_here"
}
```

Login later:

```http
POST /auth/token/
Content-Type: application/json
```

```json
{
  "username": "john",
  "password": "password123"
}
```

Example response:

```json
{
  "access": "your_access_token_here",
  "refresh": "your_refresh_token_here"
}
```

Refresh an access token:

```http
POST /auth/token/refresh/
Content-Type: application/json
```

```json
{
  "refresh": "your_refresh_token_here"
}
```

Example response:

```json
{
  "access": "new_access_token_here",
  "refresh": "new_refresh_token_here"
}
```

List events:

```http
GET /events/
Accept: application/json
```

Example response:

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": 1,
      "title": "Django Workshop",
      "description": "Build APIs with Django REST Framework.",
      "location": "Lagos",
      "date_time": "2026-08-13T10:00:00Z",
      "capacity": 50,
      "created_at": "2026-08-06T10:00:00Z",
      "spots_left": 50
    }
  ]
}
```

Event list query parameters:

| Parameter | Example | Description |
| --- | --- | --- |
| `page` | `/events/?page=2` | Return a specific page |
| `page_size` | `/events/?page_size=5` | Set page size, up to 100 |
| `search` | `/events/?search=django` | Search title and description |
| `timeframe` | `/events/?timeframe=upcoming` | Use `upcoming` or `past` |
| `date_from` | `/events/?date_from=2026-08-01` | Events on or after this date/datetime |
| `date_to` | `/events/?date_to=2026-08-31` | Events on or before this date/datetime |

Create an event as an organizer:

```http
POST /events/
Authorization: Bearer your_access_token_here
Content-Type: application/json
```

```json
{
  "title": "Django Workshop",
  "description": "Build APIs with Django REST Framework.",
  "location": "Lagos",
  "date_time": "2026-08-13T10:00:00Z",
  "capacity": 50
}
```

Update your own event as an organizer:

```http
PUT /events/1/
Authorization: Bearer your_access_token_here
Content-Type: application/json
```

```json
{
  "title": "Updated Django Workshop",
  "description": "Build APIs with Django REST Framework.",
  "location": "Lagos",
  "date_time": "2026-08-13T10:00:00Z",
  "capacity": 50
}
```

Or partially update your own event:

```http
PATCH /events/1/
Authorization: Bearer your_access_token_here
Content-Type: application/json
```

```json
{
  "title": "Updated Django Workshop"
}
```

Register for an event:

```http
POST /events/1/register/
Authorization: Bearer your_access_token_here
Accept: application/json
```

No request body is required.

View your active registrations:

```http
GET /my-registrations/
Authorization: Bearer your_access_token_here
Accept: application/json
```

Cancel a registration:

```http
POST /registrations/1/cancel/
Authorization: Bearer your_access_token_here
Accept: application/json
```

No request body is required.

## Creating Events

Events are created by admins from the Django admin panel:

```txt
http://127.0.0.1:8000/admin/
```

Create a superuser first if needed:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

After logging in, go to `Events` and add an event with:

```txt
title
description
location
date_time
capacity
```

To promote a user to organizer, go to `Profiles` in the admin panel and change their role from `attendee` to `organizer`.

## Common Errors

`401 Unauthorized` on protected endpoints usually means the JWT access token header is missing or wrong.

`403 Forbidden` on event create/update/delete usually means the authenticated user is not an organizer, or is trying to update/delete an event they do not organize.

Correct:

```http
Authorization: Bearer your_access_token_here
```

Incorrect:

```http
Authorization: Token your_access_token_here
```
