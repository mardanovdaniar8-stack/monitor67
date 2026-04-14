# Монитор67 - Employee Time & Task Tracking

## Overview
A web-based employee time and task tracking system built with Flask (Python). Supports multiple organizations, role-based access, work session tracking, task management with deadlines, Excel reporting, and a mobile client API.

## Tech Stack
- **Backend:** Python 3.12 / Flask
- **Database:** SQLite via Flask-SQLAlchemy (`instance/company.db`)
- **Templating:** Jinja2
- **Frontend:** Vanilla JS, CSS, Chart.js (CDN), Inter font (Google Fonts)
- **Reporting:** openpyxl (Excel export)

## Project Structure
- `server.py` — All routes, models, API endpoints
- `static/tracker.css` — Apple-inspired UI with Inter font, --accent: #007aff
- `static/icons/` — UI icons (clock, done, delete, edit, logout, plus, stats, task, user)
- `templates/login.html` — Login page
- `templates/register.html` — Organization registration (no emojis)
- `templates/admin_dashboard.html` — Full admin interface
- `templates/user_dashboard.html` — Employee work view

## Key Features
- Multi-org registration; invite codes with 15-min expiry (shown in local browser time)
- **Permissions system**: `permissions='*'` = superadmin; `'tasks,profiles,org'` = sub-admin
- Superadmin can create sub-admins with specific rights (tasks / profiles / org settings)
- Employee ID shown in table and edit modal
- **Reveal employee password**: admin enters own password to see employee's password
- No emojis anywhere — icons from `/static/icons/` and HTML entities (&#10005;)
- Admin name/last name editable in Org Settings tab
- User dashboard accessible only by logging in with employee credentials (no admin preview route)
- Stats by period (week/month/quarter/year/alltime/custom) with daily/monthly chart grouping
- Excel report with ID column and ИТОГО totals row
- Client API for mobile use (admins blocked from `/api/login`)

## Data Model
- `Organization` — id, name, invite_code, invite_code_expires
- `User` — id, first/last name, login, password, hourly_rate, role (admin/user), permissions, org_id
- `Task` — id, title, deadline, is_done, org_id + many-to-many users
- `TaskCompletion` — per-user completion state
- `WorkSession` — user_id, date, duration_minutes, manual_adjustment, reason

## Permissions
- `permissions='*'` — superadmin: full access + can create/edit/delete other admins
- `permissions='tasks,profiles,org'` — sub-admin: access to specific sections only
- `permissions=None` — regular employee

## Test DB
- Register with org name `test_db` → seeds "Ромашка" with 10 employees, 10 tasks, 9+ months history
- Admin: login `admin` / password `admin123`, org ID: 1

## Running the App
```
python server.py
```
Listens on `0.0.0.0:5000`. Production: `gunicorn --bind=0.0.0.0:5000 --reuse-port server:app`

## Dependencies
`flask`, `flask-sqlalchemy`, `openpyxl`, `gunicorn`
