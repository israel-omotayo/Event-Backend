# API Reference

Local base URL:

```txt
http://127.0.0.1:8000
```

Interactive docs:

```txt
/api/docs/
/api/schema/
```

Protected endpoints require:

```http
Authorization: Bearer <access_token>
```

## Auth

| Method | Endpoint | Auth | Body |
| --- | --- | --- | --- |
| `POST` | `/auth/register/` | No | `username`, `email`, `password`, optional name fields |
| `POST` | `/auth/verify/` | No | `email`, `code`, `verification_token` |
| `POST` | `/auth/verification/resend/` | No | `email`, `verification_token` |
| `POST` | `/auth/token/` | No | `email`, `password` |
| `POST` | `/auth/google/` | No | `id_token` |
| `POST` | `/auth/token/refresh/` | No | `refresh` |
| `POST` | `/auth/logout/` | Yes | `refresh` |
| `POST` | `/auth/password/change/` | Yes | `old_password`, `new_password`, `confirm_new_password`, `refresh` |
| `POST` | `/auth/password/reset/request/` | No | `email` |
| `POST` | `/auth/password/reset/confirm/` | No | `uid`, `token`, `new_password`, `confirm_new_password` |

Register:

```json
{
  "username": "john",
  "email": "john@example.com",
  "password": "StrongPass123!"
}
```

Registration returns a `verification_token`. Keep it client-side only for the pending verification screen.

Verify:

```json
{
  "email": "john@example.com",
  "code": "123456",
  "verification_token": "token-from-register-response"
}
```

Resend verification code:

```json
{
  "email": "john@example.com",
  "verification_token": "token-from-register-response"
}
```

Login:

```json
{
  "email": "john@example.com",
  "password": "StrongPass123!"
}
```

Successful login returns:

```json
{
  "access": "...",
  "refresh": "..."
}
```

Google auth expects a Google ID token, not a Google access token:

```json
{
  "id_token": "google_id_token_from_frontend"
}
```

## Events

| Method | Endpoint | Auth | Notes |
| --- | --- | --- | --- |
| `GET` | `/events/` | No | Pagination, search, date filters |
| `POST` | `/events/` | Organizer | Create event |
| `GET` | `/events/<id>/` | No | Event detail |
| `PUT` | `/events/<id>/` | Organizer owner | Replace event |
| `PATCH` | `/events/<id>/` | Organizer owner | Partial update |
| `DELETE` | `/events/<id>/` | Organizer owner | Delete event |
| `PUT` | `/events/<id>/image/` | Organizer owner | Multipart upload |
| `DELETE` | `/events/<id>/image/` | Organizer owner | Delete cover image |

Event body:

```json
{
  "title": "Django Workshop",
  "description": "Build APIs with DRF.",
  "location": "Lagos",
  "date_time": "2026-08-13T10:00:00Z",
  "capacity": 50
}
```

List filters:

```http
GET /events/?page=1&page_size=10
GET /events/?search=django
GET /events/?timeframe=upcoming
GET /events/?date_from=2026-08-01&date_to=2026-08-31
```

Image upload:

```http
PUT /events/1/image/
Content-Type: multipart/form-data
```

Form field:

```txt
image
```

Allowed image types: JPEG, PNG, WebP. Default max size: 5 MB.

## Registrations And Waitlist

| Method | Endpoint | Auth | Notes |
| --- | --- | --- | --- |
| `POST` | `/events/<id>/register/` | Yes | Register for event |
| `POST` | `/events/<id>/waitlist/` | Yes | Join waitlist for full event |
| `GET` | `/my-registrations/` | Yes | Active registrations |
| `GET` | `/my-waitlist/` | Yes | Active waitlist entries |
| `POST` | `/registrations/<id>/cancel/` | Yes | Requires confirmation |
| `POST` | `/waitlist/<id>/cancel/` | Yes | Cancel waitlist entry |

Register and waitlist endpoints do not need a request body.

Full event registration response:

```json
{
  "detail": "Event is full. Join the waitlist instead.",
  "code": "event_full"
}
```

Cancel registration:

```json
{
  "confirm": true
}
```

If `confirm` is missing or false:

```json
{
  "detail": "Cancelling releases your spot. It will not be reserved for you.",
  "code": "confirmation_required"
}
```

## Roles

New users start as attendees. Organizers can create and manage their own events. Promote a user to organizer in Django admin by editing the user's profile.

## Common Errors

| Status | Meaning |
| --- | --- |
| `400` | Validation error |
| `401` | Missing or invalid JWT |
| `403` | Authenticated but not allowed |
| `404` | Resource not found |
| `502` | Storage/email provider failed temporarily |
