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
| Access token lifetime | 60 minutes |
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
| `POST` | `/auth/register/` | No | Create an inactive user and send a verification code |
| `POST` | `/auth/verify/` | No | Verify email and activate the user |
| `POST` | `/auth/verification/resend/` | No | Resend verification code for an inactive user |
| `POST` | `/auth/token/` | No | Login with email/password and return JWT access/refresh tokens |
| `POST` | `/auth/google/` | No | Login/register with a verified Google ID token and return JWT tokens |
| `POST` | `/auth/token/refresh/` | No | Refresh an access token |
| `POST` | `/auth/logout/` | Yes | Logout by blacklisting a refresh token |
| `POST` | `/auth/password/change/` | Yes | Change the authenticated user's password |
| `POST` | `/auth/password/reset/request/` | No | Request a password reset token by email |
| `POST` | `/auth/password/reset/confirm/` | No | Confirm password reset with uid/token |
| `GET` | `/events/` | No | List events with pagination, search, and date filters |
| `POST` | `/events/` | Organizer | Create an event |
| `GET` | `/events/<id>/` | No | View one event |
| `PUT` | `/events/<id>/` | Organizer owner | Replace one of the authenticated organizer's events |
| `PATCH` | `/events/<id>/` | Organizer owner | Update one of the authenticated organizer's events |
| `DELETE` | `/events/<id>/` | Organizer owner | Delete one of the authenticated organizer's events |
| `PUT` | `/events/<id>/image/` | Organizer owner | Upload or replace an event cover image |
| `DELETE` | `/events/<id>/image/` | Organizer owner | Delete an event cover image |
| `POST` | `/events/<id>/register/` | Yes | Register the authenticated user for an event |
| `POST` | `/events/<id>/waitlist/` | Yes | Join the waitlist for a full event |
| `GET` | `/my-registrations/` | Yes | View active registrations for the authenticated user |
| `GET` | `/my-waitlist/` | Yes | View active waitlist entries for the authenticated user |
| `POST` | `/registrations/<id>/cancel/` | Yes | Cancel one of the authenticated user's registrations |
| `POST` | `/waitlist/<id>/cancel/` | Yes | Cancel one of the authenticated user's waitlist entries |

## Admin And Documentation Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/admin/` | Django admin panel |
| `GET` | `/api/docs/` | Swagger API documentation |
| `GET` | `/api/schema/` | OpenAPI schema |

For Postman or API clients, use `/auth/token/` and the `Authorization: Bearer ...` header.

## Example Flow

Create an account. This creates the user as inactive and sends an email verification code:

```http
POST /auth/register/
Content-Type: application/json
```

```json
{
  "username": "john",
  "email": "john@example.com",
  "password": "StrongPass123!"
}
```

Example response:

```json
{
  "id": 1,
  "username": "john",
  "email": "john@example.com",
  "detail": "Verification code sent to your email."
}
```

Verify the account:

```http
POST /auth/verify/
Content-Type: application/json
```

```json
{
  "email": "john@example.com",
  "code": "123456"
}
```

Example response:

```json
{
  "detail": "Account verified. You can now log in."
}
```

Resend a verification code:

```http
POST /auth/verification/resend/
Content-Type: application/json
```

```json
{
  "email": "john@example.com"
}
```

Example response:

```json
{
  "detail": "If an unverified account exists, a new code has been sent."
}
```

Login after verification:

```http
POST /auth/token/
Content-Type: application/json
```

```json
{
  "email": "john@example.com",
  "password": "StrongPass123!"
}
```

Example response:

```json
{
  "access": "your_access_token_here",
  "refresh": "your_refresh_token_here"
}
```

Login or register with Google:

```http
POST /auth/google/
Content-Type: application/json
```

```json
{
  "id_token": "google_id_token_from_frontend"
}
```

Example response:

```json
{
  "access": "your_access_token_here",
  "refresh": "your_refresh_token_here",
  "user": {
    "id": 1,
    "username": "john",
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com"
  }
}
```

The backend verifies the ID token with Google's official Python auth library, checks the token audience against `GOOGLE_OAUTH_CLIENT_ID`, requires `email_verified=true`, stores Google's stable `sub` on the local profile, and issues this API's normal JWT tokens.

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

Logout:

```http
POST /auth/logout/
Authorization: Bearer your_access_token_here
Content-Type: application/json
```

```json
{
  "refresh": "your_refresh_token_here"
}
```

Change password:

```http
POST /auth/password/change/
Authorization: Bearer your_access_token_here
Content-Type: application/json
```

```json
{
  "old_password": "OldPass123!",
  "new_password": "NewStrongPass123!",
  "confirm_new_password": "NewStrongPass123!",
  "refresh": "your_refresh_token_here"
}
```

Request password reset:

```http
POST /auth/password/reset/request/
Content-Type: application/json
```

```json
{
  "email": "john@example.com"
}
```

Example response:

```json
{
  "detail": "If an account exists for this email, a password reset email has been sent."
}
```

Confirm password reset:

```http
POST /auth/password/reset/confirm/
Content-Type: application/json
```

```json
{
  "uid": "MQ",
  "token": "django-reset-token",
  "new_password": "NewStrongPass123!",
  "confirm_new_password": "NewStrongPass123!"
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
      "image_path": "",
      "image_url": "",
      "created_at": "2026-08-06T10:00:00Z",
      "spots_left": 50,
      "is_full": false
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

Upload or replace your own event cover image as an organizer:

```http
PUT /events/1/image/
Authorization: Bearer your_access_token_here
Content-Type: multipart/form-data
```

Form field:

```txt
image
```

Allowed upload types are JPEG, PNG, and WebP. The default max file size is 5 MB. The API verifies the real image bytes before uploading. Event responses include `image_path` and `image_url`.

Delete your own event cover image:

```http
DELETE /events/1/image/
Authorization: Bearer your_access_token_here
Accept: application/json
```

Register for an event:

```http
POST /events/1/register/
Authorization: Bearer your_access_token_here
Accept: application/json
```

No request body is required.

If the event is full, the response is:

```json
{
  "detail": "Event is full. Join the waitlist instead.",
  "code": "event_full"
}
```

Join the waitlist for a full event:

```http
POST /events/1/waitlist/
Authorization: Bearer your_access_token_here
Accept: application/json
```

No request body is required.

View your active waitlist entries:

```http
GET /my-waitlist/
Authorization: Bearer your_access_token_here
Accept: application/json
```

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
Content-Type: application/json
```

```json
{
  "confirm": true
}
```

If `confirm` is missing or false, the API warns that the spot will not be reserved:

```json
{
  "detail": "Cancelling releases your spot. It will not be reserved for you.",
  "code": "confirmation_required"
}
```

Cancel a waitlist entry:

```http
POST /waitlist/1/cancel/
Authorization: Bearer your_access_token_here
Accept: application/json
```

No request body is required.

## Creating Events

Events can be created by organizers through the API or by admins from the Django admin panel:

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
