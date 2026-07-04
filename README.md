# A Commie

A small-scale REST API for private cofue's projects: image manipulation
(Pillow-based filters) plus a real, authenticated read/write layer over the
B-Commie bot's data (MongoDB Atlas + PostgreSQL/Neon).

## What changed from the original version

- `MONGO_URI`/`MONGO_DB` were declared in `config.py` but never actually
  used anywhere (`core/manager.py` was an empty placeholder). They are now
  wired up for real via `MongoManager`.
- Added PostgreSQL support (`POSTGRES_DSN`), matching the same tables the
  bot uses: `reminders`, `giveaways`, `user_timezones`, `audit_log`.
- `API_KEY` existed in config but was never checked anywhere. It's now
  enforced (`core/security.py`) on every `/json` route via the
  `X-API-Key` header. Image routes remain public, unchanged.
- Added new `/json` endpoints (see below) to read/update the bot's guild
  config, tags, reminders, and audit log.
- `/health` now actually reports Mongo/Postgres connectivity instead of a
  hardcoded "ok".
- Unused `schemas/requests.py` placeholder (`FraseCreate`) replaced with
  the request model actually used by the new endpoints.

Nothing about the existing image endpoints (`/image/blur`, `/image/simp`,
`/image/sonic`) or `/json/calendar` changed in behavior.

## Endpoints

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/image/blur` | none | Blur an image (unchanged) |
| GET | `/image/simp` | none | Simp filter (unchanged) |
| GET | `/image/sonic` | none | Sonic filter (unchanged) |
| GET | `/json/calendar` | none | Month calendar (unchanged) |
| GET | `/json/guilds/{guild_id}` | API key | Full guild config document |
| PATCH | `/json/guilds/{guild_id}` | API key | Partially update guild config |
| GET | `/json/guilds/{guild_id}/tags` | API key | List all tags in a guild |
| GET | `/json/guilds/{guild_id}/tags/{tag_name}` | API key | Get one tag |
| DELETE | `/json/guilds/{guild_id}/tags/{tag_name}` | API key | Delete a tag |
| GET | `/json/users/{user_id}/reminders` | API key | List a user's pending reminders |
| GET | `/json/guilds/{guild_id}/reminders` | API key | List a guild's pending reminders |
| DELETE | `/json/reminders/{reminder_id}` | API key | Cancel a reminder |
| GET | `/json/guilds/{guild_id}/audit-log` | API key | Recent moderation actions |

Full interactive docs at `/docs` once running.

## Setup

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# fill in API_KEY, MONGO_URI, POSTGRES_DSN
uvicorn main:app --host 0.0.0.0 --port 8000
```

Call authenticated endpoints with:
```bash
curl -H "X-API-Key: your-key" http://localhost:8000/json/guilds/123456789
```

## Keeping this in sync with the bot

This API reads/writes the *same* MongoDB collections (`guilds`, `tags`) and
PostgreSQL tables (`reminders`, `giveaways`, `user_timezones`, `audit_log`)
as the B-Commie bot. If the bot's document/table shape changes
(`src/bcommie/cogs/*.py`, `migrations/*.sql`), update `core/manager.py` and
the affected router here to match.
