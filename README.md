# AlarmDecoder WebApp (Refactored)

This is a Python 3.11+ modernization of the AlarmDecoder WebApp.

## What's New

- Python 3.11+ compatibility
- Flask 2.3+ and modern extension usage
- Modular refactor across all major subsystems
- `pytest`-based testing with `tox` and `Makefile`
- Secure certificate management, camera integration, REST API, and admin UX

## Quickstart

```bash
make install
make test
make run
```

## Requirements

- Python 3.11
- `pip install -r requirements.txt`
- Optional: Java (`keytool`) for BKS certificate exports

## Structure

- `ad2web/` – App modules
- `tests/` – Unit tests
- `alembic/` – Database migrations
- `static/`, `templates/` – Frontend assets

Happy hacking! 🔒📷🔔
