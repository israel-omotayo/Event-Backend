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

This project uses Django's built-in user model with Django REST Framework token authentication.

For protected API requests, send this header:

```http
Authorization: Token your_token_here
```

Use `Token`, not `Bearer`.

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
Authorization: Token your_token_here
Accept: application/json
```

## Main Endpoints

| Method | Endpoint | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/auth/register/` | No | Create a user and return an API token |
| `POST` | `/auth/token/` | No | Login with username/password and return an API token |
| `GET` | `/events/` | No | List all events |
| `GET` | `/events/<id>/` | No | View one event |
| `POST` | `/events/<id>/register/` | Yes | Register the authenticated user for an event |
| `GET` | `/my-registrations/` | Yes | View active registrations for the authenticated user |
| `POST` | `/registrations/<id>/cancel/` | Yes | Cancel one of the authenticated user's registrations |

## Admin And Documentation Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/admin/` | Django admin panel |
| `GET` | `/api/docs/` | Swagger API documentation |
| `GET` | `/api/schema/` | OpenAPI schema |
| `GET` | `/api-auth/login/` | DRF browsable API session login page |
| `POST` | `/api-auth/login/` | DRF browsable API session login form |
| `GET` | `/api-auth/logout/` | DRF browsable API session logout page |
| `POST` | `/api-auth/logout/` | DRF browsable API session logout form |

The `/api-auth/` routes are mainly for the browser-based DRF interface. For Postman, use `/auth/token/` and the `Authorization: Token ...` header.

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
  "token": "your_token_here"
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
  "token": "your_token_here"
}
```

List events:

```http
GET /events/
Accept: application/json
```

Register for an event:

```http
POST /events/1/register/
Authorization: Token your_token_here
Accept: application/json
```

No request body is required.

View your active registrations:

```http
GET /my-registrations/
Authorization: Token your_token_here
Accept: application/json
```

Cancel a registration:

```http
POST /registrations/1/cancel/
Authorization: Token your_token_here
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

## Common Errors

`401 Unauthorized` on protected endpoints usually means the token header is missing or wrong.

Correct:

```http
Authorization: Token your_token_here
```

Incorrect:

```http
Authorization: Bearer your_token_here
```
