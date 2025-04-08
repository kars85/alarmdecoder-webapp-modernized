# API Endpoints

All API routes are prefixed with `/api/v1`.

## Authentication

All routes require an API key:
- Pass via `Authorization` header
- Or `apikey` query parameter

Example:
```bash
curl -H "Authorization: your_api_key" http://localhost:5000/api/v1/zones
```

## Routes

### GET /alarmdecoder
Returns current panel state.

### POST /alarmdecoder/send
Send raw keypad data.

### GET|POST /zones
List or create zones.

### GET|PUT|DELETE /zones/<id>
CRUD individual zone.

... more in `api/views.py`
