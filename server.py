import os
import secrets
from datetime import datetime, date, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from io import BytesIO
from flask import Flask, render_template, request, redirect, jsonify, session, url_for, send_file
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SECRET_KEY'] = 'dev-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///company.db'
db = SQLAlchemy(app)

class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    invite_code = db.Column(db.String(10), unique=True, nullable=True)
    invite_code_expires = db.Column(db.DateTime, nullable=True)
    users = db.relationship('User', backref='organization', lazy=True)
    tasks = db.relationship('Task', backref='organization', lazy=True)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    login = db.Column(db.String(50))
    password = db.Column(db.String(50))
    hourly_rate = db.Column(db.Float)
    role = db.Column(db.String(10), default='user')
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'))
    __table_args__ = (db.UniqueConstraint('login', 'organization_id', name='_user_login_org_uc'),)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100))
    deadline = db.Column(db.Date)
    is_done = db.Column(db.Boolean, default=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organization.id'))
    users = db.relationship('User', secondary='task_assignees', backref='tasks')
    completions = db.relationship('TaskCompletion', backref='task', lazy=True)

class TaskCompletion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    completed = db.Column(db.Boolean, default=False)
    __table_args__ = (db.UniqueConstraint('task_id', 'user_id'),)

task_assignees = db.Table('task_assignees',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('task_id', db.Integer, db.ForeignKey('task.id'))
)

class WorkSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    date = db.Column(db.Date, default=date.today)
    duration_minutes = db.Column(db.Integer, default=0)
    manual_adjustment = db.Column(db.Boolean, default=False)
    adjusted_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    adjust_reason = db.Column(db.String(200), nullable=True)

def generate_invite_code():
    return secrets.token_hex(4).upper()

def get_current_organization():
    if 'org_id' in session:
        return Organization.query.get(session['org_id'])
    return None

# ---------- Регистрация ----------
@app.route('/register', methods=['GET', 'POST'])
def register_org():
    if request.method == 'POST':
        org = Organization(name=request.form['org_name'])
        db.session.add(org)
        db.session.flush()
        admin = User(
            first_name=request.form['first_name'],
            last_name=request.form['last_name'],
            login=request.form['login'],
            password=request.form['password'],
            hourly_rate=0,
            role='admin',
            organization_id=org.id
        )
        db.session.add(admin)
        db.session.commit()
        session['user_id'] = admin.id
        session['org_id'] = org.id
        return render_template('register.html', created=True, org_id=org.id, org_name=org.name)
    return render_template('register.html', created=False)

@app.route('/')
def home():
    return redirect(url_for('login_page'))

@app.route('/login', methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        org_id = request.form.get('org_id')
        login = request.form['login']
        password = request.form['password']
        user = User.query.filter_by(login=login, password=password, organization_id=org_id).first()
        if user:
            session['user_id'] = user.id
            session['org_id'] = user.organization_id
            return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    user = User.query.get(session['user_id'])
    org = Organization.query.get(session['org_id'])
    if user.role == 'admin':
        return redirect(url_for('admin_panel'))
    return render_template('user_dashboard.html', user=user, org=org)

@app.route('/admin')
def admin_panel():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    admin = User.query.get(session['user_id'])
    if admin.role != 'admin':
        return redirect(url_for('dashboard'))
    org = Organization.query.get(session['org_id'])
    users = User.query.filter_by(organization_id=org.id, role='user').all()
    tasks = Task.query.filter_by(organization_id=org.id).all()
    now = datetime.utcnow()
    error = request.args.get('error')
    return render_template('admin_dashboard.html', org=org, users=users, tasks=tasks, now=now, error=error)

@app.route('/admin/update_org', methods=['POST'])
def update_org():
    org = get_current_organization()
    admin = User.query.get(session['user_id'])
    if not org or admin.role != 'admin':
        return redirect(url_for('login_page'))
    org.name = request.form['name']
    if request.form.get('password'):
        admin.password = request.form['password']
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_user', methods=['POST'])
def add_user():
    org = get_current_organization()
    admin_user = User.query.get(session['user_id'])
    if not org or admin_user.role != 'admin':
        return redirect(url_for('login_page'))
    login = request.form['login']
    if User.query.filter_by(login=login, organization_id=org.id).first():
        return redirect(url_for('admin_panel', error=f"Логин '{login}' уже занят в этой организации."))
    u = User(
        first_name=request.form['f_name'],
        last_name=request.form['l_name'],
        login=login,
        password=request.form['password'],
        hourly_rate=float(request.form['rate']),
        role='user',
        organization_id=org.id
    )
    db.session.add(u)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/edit_user/<int:uid>', methods=['POST'])
def edit_user(uid):
    org = get_current_organization()
    admin = User.query.get(session['user_id'])
    if not org or admin.role != 'admin':
        return redirect(url_for('login_page'))
    u = User.query.get_or_404(uid)
    if u.organization_id != org.id:
        return "Forbidden", 403
    new_login = request.form['login']
    if new_login != u.login and User.query.filter_by(login=new_login, organization_id=org.id).first():
        return redirect(url_for('admin_panel', error=f"Логин '{new_login}' уже занят."))
    u.first_name = request.form['f_name']
    u.last_name = request.form['l_name']
    u.login = new_login
    if request.form['password']:
        u.password = request.form['password']
    u.hourly_rate = float(request.form['rate'])
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_user/<int:uid>', methods=['POST'])
def delete_user(uid):
    org = get_current_organization()
    admin = User.query.get(session['user_id'])
    if not org or admin.role != 'admin':
        return redirect(url_for('login_page'))
    u = User.query.get_or_404(uid)
    if u.organization_id != org.id:
        return "Forbidden", 403
    WorkSession.query.filter_by(user_id=uid).delete()
    db.session.delete(u)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/add_task', methods=['POST'])
def add_task():
    org = get_current_organization()
    admin = User.query.get(session['user_id'])
    if not org or admin.role != 'admin':
        return redirect(url_for('login_page'))
    dl = datetime.strptime(request.form['deadline'], '%Y-%m-%d').date()
    t = Task(title=request.form['title'], deadline=dl, organization_id=org.id)
    db.session.add(t)
    db.session.flush()
    for uid in request.form.getlist('user_ids'):
        u = User.query.get(int(uid))
        if u and u.organization_id == org.id:
            t.users.append(u)
            tc = TaskCompletion(task_id=t.id, user_id=u.id, completed=False)
            db.session.add(tc)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/edit_task/<int:tid>', methods=['POST'])
def edit_task(tid):
    org = get_current_organization()
    admin = User.query.get(session['user_id'])
    if not org or admin.role != 'admin':
        return redirect(url_for('login_page'))
    t = Task.query.get_or_404(tid)
    if t.organization_id != org.id:
        return "Forbidden", 403
    t.title = request.form['title']
    t.deadline = datetime.strptime(request.form['deadline'], '%Y-%m-%d').date()
    new_user_ids = set(int(uid) for uid in request.form.getlist('user_ids'))
    current_user_ids = {u.id for u in t.users}
    for uid in current_user_ids - new_user_ids:
        u = User.query.get(uid)
        t.users.remove(u)
        TaskCompletion.query.filter_by(task_id=t.id, user_id=uid).delete()
    for uid in new_user_ids - current_user_ids:
        u = User.query.get(uid)
        if u and u.organization_id == org.id:
            t.users.append(u)
            tc = TaskCompletion(task_id=t.id, user_id=uid, completed=False)
            db.session.add(tc)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/admin/delete_task/<int:tid>', methods=['POST'])
def delete_task(tid):
    org = get_current_organization()
    admin = User.query.get(session['user_id'])
    if not org or admin.role != 'admin':
        return redirect(url_for('login_page'))
    t = Task.query.get_or_404(tid)
    if t.organization_id != org.id:
        return "Forbidden", 403
    TaskCompletion.query.filter_by(task_id=tid).delete()
    db.session.delete(t)
    db.session.commit()
    return redirect(url_for('admin_panel'))

@app.route('/task/done/<int:tid>')
def mark_done_web(tid):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    user = User.query.get(session['user_id'])
    task = Task.query.get_or_404(tid)
    if user not in task.users:
        return "Forbidden", 403
    tc = TaskCompletion.query.filter_by(task_id=tid, user_id=user.id).first()
    if tc:
        tc.completed = True
        db.session.commit()
        total = task.users.count()
        completed_count = TaskCompletion.query.filter_by(task_id=tid, completed=True).count()
        if completed_count == total:
            task.is_done = True
            db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/admin/generate_invite', methods=['POST'])
def generate_invite():
    org = get_current_organization()
    admin = User.query.get(session['user_id'])
    if not org or admin.role != 'admin':
        return jsonify({"error": "forbidden"}), 403
    org.invite_code = generate_invite_code()
    org.invite_code_expires = datetime.utcnow() + timedelta(minutes=15)
    db.session.commit()
    return jsonify({"invite_code": org.invite_code, "expires": org.invite_code_expires.strftime('%H:%M')})

# ---------- API Статистика ----------
@app.route('/api/stats')
def get_stats():
    if 'user_id' not in session:
        return jsonify({"error": "unauthorized"}), 401
    user = User.query.get(session['user_id'])
    period = request.args.get('period', 'week')
    date_str = request.args.get('date')
    today = date.today()
    if date_str:
        try:
            day = datetime.strptime(date_str, '%Y-%m-%d').date()
            sessions = WorkSession.query.filter(WorkSession.user_id == user.id, WorkSession.date == day).all()
            total_min = sum(s.duration_minutes for s in sessions)
            return jsonify({
                "date": day.strftime('%d.%m.%Y'),
                "hours": round(total_min / 60, 2),
                "earnings": round((total_min / 60) * user.hourly_rate, 2)
            })
        except:
            return jsonify({"error": "invalid date"}), 400
    if period == 'week':
        start = today - timedelta(days=today.weekday())
    elif period == 'month':
        start = today.replace(day=1)
    elif period == 'year':
        start = today.replace(month=1, day=1)
    else:
        start = today - timedelta(days=30)
    sessions = WorkSession.query.filter(WorkSession.user_id == user.id, WorkSession.date >= start).all()
    total_min = sum(s.duration_minutes for s in sessions)
    total_hours = total_min / 60
    earnings = total_hours * user.hourly_rate
    dates = []
    minutes = []
    current = start
    while current <= today:
        day_sessions = [s for s in sessions if s.date == current]
        day_min = sum(s.duration_minutes for s in day_sessions)
        dates.append(current.strftime('%d.%m'))
        minutes.append(day_min / 60)
        current += timedelta(days=1)
    return jsonify({
        "labels": dates,
        "values": minutes,
        "total_hours": round(total_hours, 2),
        "earnings": round(earnings, 2),
        "rate": user.hourly_rate
    })

@app.route('/api/admin/all_stats')
def admin_all_stats():
    if 'user_id' not in session:
        return jsonify({"error": "unauthorized"}), 401
    admin = User.query.get(session['user_id'])
    if admin.role != 'admin':
        return jsonify({"error": "forbidden"}), 403
    org = get_current_organization()
    users = User.query.filter_by(organization_id=org.id, role='user').all()
    period = request.args.get('period', 'week')
    today = date.today()
    if period == 'week':
        start = today - timedelta(days=today.weekday())
    elif period == 'month':
        start = today.replace(day=1)
    elif period == 'year':
        start = today.replace(month=1, day=1)
    else:
        start = today - timedelta(days=30)
    result = []
    for u in users:
        sessions = WorkSession.query.filter(WorkSession.user_id == u.id, WorkSession.date >= start).all()
        total_min = sum(s.duration_minutes for s in sessions)
        total_hours = total_min / 60
        earnings = total_hours * u.hourly_rate
        dates = []
        minutes = []
        current = start
        while current <= today:
            day_sessions = [s for s in sessions if s.date == current]
            day_min = sum(s.duration_minutes for s in day_sessions)
            dates.append(current.strftime('%d.%m'))
            minutes.append(day_min / 60)
            current += timedelta(days=1)
        result.append({
            "id": u.id,
            "name": f"{u.first_name} {u.last_name}",
            "labels": dates,
            "values": minutes,
            "total_hours": round(total_hours, 2),
            "earnings": round(earnings, 2)
        })
    return jsonify(result)

# ---------- API для клиента ----------
@app.route('/api/check_invite', methods=['POST'])
def check_invite():
    data = request.json
    code = data.get('invite_code')
    org = Organization.query.filter_by(invite_code=code).first()
    if org and org.invite_code_expires and org.invite_code_expires > datetime.utcnow():
        return jsonify({"valid": True, "org_id": org.id, "org_name": org.name})
    return jsonify({"valid": False}), 400

@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.json
    org_id = d.get('org_id')
    login = d.get('login')
    password = d.get('password')
    if not org_id or not login or not password:
        return jsonify({"error": "missing data"}), 400
    org = Organization.query.get(org_id)
    if not org:
        return jsonify({"error": "Invalid organization"}), 401
    u = User.query.filter_by(login=login, password=password, organization_id=org.id).first()
    if u:
        tasks = []
        if u.role != 'admin':
            for t in u.tasks:
                total = len(t.users)
                completed = TaskCompletion.query.filter_by(task_id=t.id, completed=True).count()
                tasks.append({
                    "id": t.id,
                    "title": t.title,
                    "deadline": str(t.deadline),
                    "urgent": (t.deadline - date.today()).days <= 2 and not t.is_done,
                    "assignees": [f"{user.first_name} {user.last_name}" for user in t.users],
                    "completed_by_me": TaskCompletion.query.filter_by(task_id=t.id, user_id=u.id, completed=True).first() is not None,
                    "progress": f"{completed}/{total}",
                    "is_done": t.is_done
                })
        hist = WorkSession.query.filter_by(user_id=u.id).order_by(WorkSession.date.desc()).limit(5).all()
        chart = {
            "labels": [s.date.strftime('%d.%m') for s in reversed(hist)],
            "values": [round(s.duration_minutes / 60, 2) for s in reversed(hist)]
        }
        return jsonify({
            "id": u.id,
            "name": u.first_name,
            "rate": u.hourly_rate,
            "role": u.role,
            "total_min": sum(s.duration_minutes for s in WorkSession.query.filter_by(user_id=u.id).all()),
            "tasks": tasks,
            "chart": chart
        })
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/sync', methods=['POST'])
def sync_time():
    d = request.json
    ws = WorkSession.query.filter_by(user_id=d['user_id'], date=date.today()).first()
    if not ws:
        ws = WorkSession(user_id=d['user_id'])
        db.session.add(ws)
    ws.duration_minutes += 1
    db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/tasks', methods=['GET'])
def get_tasks_api():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    u = User.query.get(int(user_id))
    if not u:
        return jsonify({"error": "user not found"}), 404
    tasks = []
    for t in u.tasks:
        total = len(t.users)
        completed = TaskCompletion.query.filter_by(task_id=t.id, completed=True).count()
        tasks.append({
            "id": t.id,
            "title": t.title,
            "deadline": str(t.deadline),
            "is_done": t.is_done,
            "urgent": (t.deadline - date.today()).days <= 2 and not t.is_done,
            "assignees": [f"{user.first_name} {user.last_name}" for user in t.users],
            "completed_by_me": TaskCompletion.query.filter_by(task_id=t.id, user_id=u.id, completed=True).first() is not None,
            "progress": f"{completed}/{total}"
        })
    return jsonify(tasks)

@app.route('/api/task/<int:task_id>/done', methods=['POST'])
def mark_task_done_api(task_id):
    d = request.json or {}
    user_id = d.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    u = User.query.get(int(user_id))
    task = Task.query.get_or_404(task_id)
    if u not in task.users:
        return jsonify({"error": "forbidden"}), 403
    tc = TaskCompletion.query.filter_by(task_id=task_id, user_id=u.id).first()
    if tc:
        tc.completed = True
        db.session.commit()
        total = len(task.users)
        completed = TaskCompletion.query.filter_by(task_id=task_id, completed=True).count()
        if completed == total:
            task.is_done = True
            db.session.commit()
        return jsonify({"status": "ok"})
    return jsonify({"error": "completion record not found"}), 404

# ---------- Админские API для клиента ----------
@app.route('/api/admin/adjust_time', methods=['POST'])
def admin_adjust_time():
    data = request.json
    user_id = data.get('user_id')
    minutes = data.get('minutes')
    reason = data.get('reason', '')
    admin_login = data.get('admin_login')
    admin_password = data.get('admin_password')
    if not all([user_id, minutes is not None, admin_login, admin_password]):
        return jsonify({"error": "missing data"}), 400
    admin = User.query.filter_by(login=admin_login, password=admin_password).first()
    if not admin or admin.role != 'admin':
        return jsonify({"error": "forbidden"}), 403
    u = User.query.get(user_id)
    if not u or u.organization_id != admin.organization_id:
        return jsonify({"error": "user not found"}), 404
    today = date.today()
    ws = WorkSession.query.filter_by(user_id=user_id, date=today).first()
    if not ws:
        ws = WorkSession(user_id=user_id, date=today, duration_minutes=0)
        db.session.add(ws)
    ws.duration_minutes = max(0, ws.duration_minutes + minutes)
    ws.manual_adjustment = True
    ws.adjusted_by = admin.id
    ws.adjust_reason = reason
    db.session.commit()
    return jsonify({"status": "ok", "new_total": ws.duration_minutes})

@app.route('/api/admin/delete_adjustment/<int:sid>', methods=['POST'])
def admin_delete_adjustment(sid):
    data = request.json
    admin_login = data.get('admin_login')
    admin_password = data.get('admin_password')
    if not admin_login or not admin_password:
        return jsonify({"error": "missing data"}), 400
    admin = User.query.filter_by(login=admin_login, password=admin_password).first()
    if not admin or admin.role != 'admin':
        return jsonify({"error": "forbidden"}), 403
    ws = WorkSession.query.get(sid)
    if not ws or ws.adjusted_by != admin.id:
        return jsonify({"error": "not found"}), 404
    if ws.manual_adjustment:
        db.session.delete(ws)
        db.session.commit()
    return jsonify({"status": "ok"})

@app.route('/api/admin/user_sessions/<int:uid>', methods=['POST'])
def admin_user_sessions(uid):
    data = request.json
    admin_login = data.get('admin_login')
    admin_password = data.get('admin_password')
    if not admin_login or not admin_password:
        return jsonify({"error": "missing data"}), 400
    admin = User.query.filter_by(login=admin_login, password=admin_password).first()
    if not admin or admin.role != 'admin':
        return jsonify({"error": "forbidden"}), 403
    u = User.query.get(uid)
    if not u or u.organization_id != admin.organization_id:
        return jsonify({"error": "user not found"}), 404
    sessions = WorkSession.query.filter_by(user_id=uid).order_by(WorkSession.date.desc()).limit(30).all()
    return jsonify([{
        "id": s.id,
        "date": s.date.strftime('%d.%m.%Y'),
        "minutes": s.duration_minutes,
        "manual": s.manual_adjustment,
        "reason": s.adjust_reason
    } for s in sessions])

@app.route('/api/admin/users', methods=['POST'])
def admin_users():
    data = request.json
    org_id = data.get('org_id')
    login = data.get('login')
    password = data.get('password')
    if not org_id or not login or not password:
        return jsonify({"error": "missing data"}), 400
    org = Organization.query.get(org_id)
    if not org:
        return jsonify({"error": "Invalid organization"}), 401
    admin = User.query.filter_by(login=login, password=password, organization_id=org.id, role='admin').first()
    if not admin:
        return jsonify({"error": "Forbidden"}), 403
    users = User.query.filter_by(organization_id=org.id, role='user').all()
    return jsonify([{"id": u.id, "name": f"{u.first_name} {u.last_name}", "rate": u.hourly_rate} for u in users])

@app.route('/api/total_minutes')
def total_minutes():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    sessions = WorkSession.query.filter_by(user_id=user_id, date=date.today()).all()
    total = sum(s.duration_minutes for s in sessions)
    return jsonify({"total_min": total})

@app.route('/api/admin/monthly_report')
def monthly_report():
    if 'user_id' not in session:
        return jsonify({"error": "unauthorized"}), 401
    admin = User.query.get(session['user_id'])
    if admin.role != 'admin':
        return jsonify({"error": "forbidden"}), 403
    org = get_current_organization()
    month_str = request.args.get('month')
    if month_str:
        try:
            year, month = map(int, month_str.split('-'))
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
        except:
            today = date.today()
            start_date = today.replace(day=1)
            end_date = (start_date + timedelta(days=32)).replace(day=1)
    else:
        today = date.today()
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1)

    users = User.query.filter_by(organization_id=org.id, role='user').all()
    wb = Workbook()
    ws = wb.active
    ws.title = f"Отчёт {start_date.strftime('%B %Y')}"
    headers = ['Сотрудник', 'Отработано часов', 'Заработано (₽)']
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal='center')

    for u in users:
        sessions = WorkSession.query.filter(
            WorkSession.user_id == u.id,
            WorkSession.date >= start_date,
            WorkSession.date < end_date
        ).all()
        total_min = sum(s.duration_minutes for s in sessions)
        hours = total_min / 60
        earnings = hours * u.hourly_rate
        ws.append([f"{u.first_name} {u.last_name}", round(hours, 2), round(earnings, 2)])

    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = (max_length + 2)
        ws.column_dimensions[column_letter].width = adjusted_width

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"report_{start_date.strftime('%Y_%m')}.xlsx"
    return send_file(output, download_name=filename, as_attachment=True,
                     mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)