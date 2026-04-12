# Монитор67 - Employee Time & Task Tracking

## Overview
A web-based employee time and task tracking system built with Flask (Python). It allows organizations to manage users, assign tasks with deadlines, track work sessions, and generate Excel reports on earnings based on hourly rates.

## Tech Stack
- **Backend:** Python 3.12 / Flask
- **Database:** SQLite via Flask-SQLAlchemy (`instance/company.db`)
- **Templating:** Jinja2
- **Frontend:** Vanilla JS, CSS, Chart.js (CDN), Inter font (Google Fonts)
- **Reporting:** openpyxl (Excel export)

## Project Structure
- `server.py` — Main application entry point with all routes, models, and API endpoints
- `static/` — CSS and icon assets
- `templates/` — Jinja2 HTML templates
  - `login.html` / `register.html` — Authentication
  - `admin_dashboard.html` — Admin interface for managing users and tasks
  - `user_dashboard.html` — Employee work tracking view
  - `setup.html` — Organization setup

## Key Features
- Organization registration with invite codes
- Role-based access (admin vs user)
- Task management with deadlines and multi-user assignment
- Work session tracking with time sync API
- Excel report generation for payroll/attendance

## Running the App
The app runs via the "Start application" workflow:
```
python server.py
```
Listens on `0.0.0.0:5000`.

## Dependencies
Installed via pip: `flask`, `flask-sqlalchemy`, `openpyxl`, `gunicorn`
