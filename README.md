# Secret Santa Backend 🎅

The API behind a family Secret Santa: events, wish lists and the draw. Built with FastAPI, SQLModel and PostgreSQL, for the [Secret Santa frontend](https://github.com/zockerei/secret-santa-frontend).

## How It Works

- **🎁 Events**: the admin creates an event (e.g. "Christmas 2026" on 2026-12-24). Everyone can join it and write a wish list.
- **🎲 The draw**: when everyone has joined, the admin starts the draw. Then each participant sees who they give a gift to, and that person's wish list.
- **🔁 No repeats**: nobody gets someone they had in their last 2 events. If that is impossible (small groups), fewer events are avoided.
- **✍️ Wish lists** can be changed until the day of the event, so your Secret Santa always sees the latest one.

### Spoiler-Free Admin

The admin manages users and events, but the API never shows the admin who gives to whom or anyone's wish list. The admin sees who joined an event and whether they wrote a wish list, nothing more. So the admin can take part like everyone else without being spoiled.

The admin can:
- create, change and delete users (there is no public registration)
- create, change and delete events, and add or remove participants before the draw
- start the draw, and undo it before the event day (e.g. if someone drops out). Joining, leaving and removing participants only work while an event isn't drawn.

Past draws can't be undone, because the repeat check needs them.

Whoever runs the database can of course still read everything, the API just doesn't show it.

## Running

Copy `.env.example` to `.env` and fill it in:

```
DATABASE_URL=postgresql://user:password@host:5432/database
SECRET_KEY=a_long_random_string
```

To create the first admin, also set `INITIAL_ADMIN_NAME`, `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD`. The admin is only created if there is no admin yet.

**On the NAS** (Docker): `docker compose up -d`. GitHub Actions builds the image on every push to `main` and Watchtower updates it. Also set `BACKEND_IP` for the `br0` network.

The backend stays on the LAN and is not published to the internet. The frontend's nginx forwards `/api` to it, so the browser only ever talks to the frontend (no CORS needed). The interactive docs are at `http://<BACKEND_IP>:8000/docs`.

**Locally** (Windows): `run.bat` creates a virtual environment, installs the packages and starts the API with auto reload. The interactive docs are at http://localhost:8000/docs.

Logs go to the console and to `logs/api.log` (errors also to `logs/errors.log`). Wish lists are never logged.

## Security

- Passwords are hashed with bcrypt, logins return a JWT that lasts 7 days (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- After 5 failed logins an email is locked for 15 minutes
- Emails are stored lowercase, so logins don't depend on how someone typed theirs
- An admin can't take away their own admin rights or delete themselves, so there is always an admin

## Database and Migrations

The API owns the database schema. `app/models.py` describes the tables and `alembic/versions` holds the migrations that change them. The API applies new migrations itself when it starts.

To change the schema:

1. Change `app/models.py`
2. Create a migration: `alembic revision --autogenerate -m "describe the change"`
3. Check the generated file in `alembic/versions` (autogenerate doesn't see everything, e.g. check constraints)
4. Update `schema.dbml`

On startup the API also compares the database with `app/models.py` and logs a warning for every difference it finds.

`schema.dbml` shows the schema as an ER diagram on [dbdiagram.io](https://dbdiagram.io).

## Tests

The draw algorithm has tests:

```
pip install pytest
python -m pytest
```
