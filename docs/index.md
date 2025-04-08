# AlarmDecoder WebApp (Modernized)

Welcome to the documentation for the refactored AlarmDecoder WebApp.

## Overview

This web application provides:

- Alarm system integration via AlarmDecoder hardware
- Realtime notifications via Email, Twilio, Pushover, Matrix, and more
- REST API for third-party integrations
- Admin dashboard, user management, certificate-based auth
- Flask-based backend and Bootstrap frontend

---

## Project Structure

```
ad2web/                # Core application modules
tests/                 # Unit and integration tests
templates/, static/    # UI assets
alembic/               # DB migrations
docs/                  # This documentation
```

---

## Key Technologies

- Python 3.11
- Flask 2.3+
- SQLAlchemy, Alembic
- Flask-SocketIO
- OpenSSL (cert-based auth)
- Twilio, Matrix, Pushover, Growl support
