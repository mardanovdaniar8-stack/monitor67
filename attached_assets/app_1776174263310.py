import customtkinter as ctk
import requests
import time
import threading
import pystray
import sys
import json
import os
from PIL import Image, ImageDraw
from pynput import mouse, keyboard
from tkinter import messagebox

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

CONFIG_FILE = "monitor67_config.json"
SERVER_URL = "https://monitor-67--quwerix.replit.app"

class TaskWindow(ctk.CTkToplevel):
    def __init__(self, master, user_id, tasks):
        super().__init__(master)
        self.master = master
        self.user_id = user_id
        self.tasks = tasks
        self.title("Мои задачи")
        self.geometry("550x650")
        self.resizable(False, False)
        self.grab_set()
        self.frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.frame.pack(fill="both", expand=True, padx=20, pady=20)
        self.refresh_task_list()

    def refresh_task_list(self):
        for w in self.frame.winfo_children():
            w.destroy()
        active = [t for t in self.tasks if not t.get('is_done', False)]
        done = [t for t in self.tasks if t.get('is_done', False)]
        ctk.CTkLabel(self.frame, text="Активные", font=("Inter", 16, "bold")).pack(anchor="w", pady=(0, 10))
        if not active:
            ctk.CTkLabel(self.frame, text="Нет активных задач", text_color="#86868b").pack(anchor="w")
        for task in active:
            self.create_task_card(task)
        ctk.CTkLabel(self.frame, text="Завершённые", font=("Inter", 16, "bold")).pack(anchor="w", pady=(20, 10))
        if not done:
            ctk.CTkLabel(self.frame, text="Нет завершённых задач", text_color="#86868b").pack(anchor="w")
        for task in done:
            self.create_task_card(task, done=True)

    def create_task_card(self, task, done=False):
        card = ctk.CTkFrame(self.frame, fg_color="#ffffff", corner_radius=12, border_width=1, border_color="#e5e5ea")
        card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=16, pady=12)
        ctk.CTkLabel(inner, text=task['title'], font=("Inter", 14, "bold")).pack(anchor="w")
        ctk.CTkLabel(inner, text=f"Дедлайн: {task['deadline']}", font=("Inter", 12), text_color="#86868b").pack(anchor="w")
        if task.get('assignees'):
            assignees = ", ".join(task['assignees'])
            ctk.CTkLabel(inner, text=f"Исполнители: {assignees}", font=("Inter", 11), text_color="#86868b").pack(anchor="w")
        progress = task.get('progress', '0/0')
        ctk.CTkLabel(inner, text=f"Прогресс: {progress}", font=("Inter", 12), text_color="#007aff").pack(anchor="w")
        if not done and not task.get('completed_by_me', False):
            btn = ctk.CTkButton(inner, text="Отметить выполнение", command=lambda: self.mark_done(task['id']),
                                width=160, height=32, corner_radius=8)
            btn.pack(anchor="e", pady=(8, 0))
        elif not done:
            ctk.CTkLabel(inner, text="Вы уже отметили", font=("Inter", 12), text_color="#28a745").pack(anchor="e", pady=(8,0))

    def mark_done(self, task_id):
        def task():
            try:
                r = requests.post(f"{SERVER_URL}/api/task/{task_id}/done",
                                  json={"user_id": self.master.user_data['id']}, timeout=10)
                if r.status_code == 200:
                    self.master.load_tasks()
                    self.after(0, self.destroy)
            except Exception as e:
                print("Ошибка:", e)
        threading.Thread(target=task, daemon=True).start()


class AdminPanel(ctk.CTkToplevel):
    def __init__(self, master, org_id, admin_login, admin_password, current_user, on_time_changed):
        super().__init__(master)
        self.master = master
        self.org_id = org_id
        self.admin_login = admin_login
        self.admin_password = admin_password
        self.current_user = current_user
        self.on_time_changed = on_time_changed
        self.title("Админ-панель")
        self.geometry("500x550")
        self.resizable(False, False)
        self.grab_set()
        self.build_ui()
        self.load_sessions()

    def build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Администрирование", font=("Inter", 20, "bold")).pack(pady=20)
        ctk.CTkLabel(self, text=f"Сотрудник: {self.current_user.get('name', '')}", font=("Inter", 14)).pack()
        ctk.CTkLabel(self, text=f"Ставка: {self.current_user.get('rate', 0)} ₽/ч", font=("Inter", 12)).pack(pady=5)

        self.adj_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.adj_frame.pack(pady=20)
        buttons = [
            ("+1 ч", 60), ("+2 ч", 120), ("+30 мин", 30),
            ("-1 ч", -60), ("-2 ч", -120), ("-30 мин", -30)
        ]
        for i, (text, mins) in enumerate(buttons):
            btn = ctk.CTkButton(self.adj_frame, text=text, width=100,
                                command=lambda m=mins: self.adjust_time(m))
            btn.grid(row=i//3, column=i%3, padx=5, pady=5)

        custom_frame = ctk.CTkFrame(self, fg_color="transparent")
        custom_frame.pack(pady=10)
        ctk.CTkLabel(custom_frame, text="Часы:").grid(row=0, column=0, padx=5)
        self.hours_entry = ctk.CTkEntry(custom_frame, width=60)
        self.hours_entry.grid(row=0, column=1, padx=5)
        self.hours_entry.insert(0, "0")
        ctk.CTkLabel(custom_frame, text="Минуты:").grid(row=0, column=2, padx=5)
        self.minutes_entry = ctk.CTkEntry(custom_frame, width=60)
        self.minutes_entry.grid(row=0, column=3, padx=5)
        self.minutes_entry.insert(0, "0")
        ctk.CTkLabel(custom_frame, text="±").grid(row=0, column=4, padx=5)
        self.sign_combo = ctk.CTkComboBox(custom_frame, values=["+", "-"], width=60)
        self.sign_combo.grid(row=0, column=5, padx=5)
        self.sign_combo.set("+")
        ctk.CTkButton(custom_frame, text="Применить", command=self.apply_custom).grid(row=0, column=6, padx=5)

        self.reason_entry = ctk.CTkEntry(self, placeholder_text="Причина (необязательно)", width=300)
        self.reason_entry.pack(pady=10)

        self.sessions_frame = ctk.CTkScrollableFrame(self, height=150, fg_color="#f0f0f0")
        self.sessions_frame.pack(fill="x", padx=20, pady=10)

    def load_sessions(self):
        def task():
            try:
                r = requests.post(f"{SERVER_URL}/api/admin/user_sessions/{self.current_user['id']}",
                                  json={"admin_login": self.admin_login, "admin_password": self.admin_password}, timeout=10)
                if r.status_code == 200:
                    sessions = r.json()
                    self.after(0, lambda: self.display_sessions(sessions))
                else:
                    self.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось загрузить сессии"))
            except Exception as e:
                print(e)
        threading.Thread(target=task, daemon=True).start()

    def display_sessions(self, sessions):
        for w in self.sessions_frame.winfo_children():
            w.destroy()
        for s in sessions[:10]:
            frame = ctk.CTkFrame(self.sessions_frame, fg_color="white")
            frame.pack(fill="x", pady=2)
            text = f"{s['date']}: {s['minutes']} мин"
            if s['manual']:
                text += " ✎"
            ctk.CTkLabel(frame, text=text).pack(side="left", padx=5)
            if s['manual']:
                ctk.CTkButton(frame, text="Удалить", width=60, height=20,
                              command=lambda sid=s['id']: self.delete_adjustment(sid)).pack(side="right", padx=5)

    def adjust_time(self, minutes):
        reason = self.reason_entry.get()
        def task():
            try:
                r = requests.post(f"{SERVER_URL}/api/admin/adjust_time",
                                  json={"user_id": self.current_user['id'], "minutes": minutes, "reason": reason,
                                        "admin_login": self.admin_login, "admin_password": self.admin_password}, timeout=10)
                if r.status_code == 200:
                    self.after(0, self.load_sessions)
                    self.on_time_changed()
                else:
                    self.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось изменить время"))
            except Exception as e:
                print(e)
        threading.Thread(target=task, daemon=True).start()

    def apply_custom(self):
        try:
            h = int(self.hours_entry.get() or 0)
            m = int(self.minutes_entry.get() or 0)
        except:
            return
        total = h * 60 + m
        if self.sign_combo.get() == "-":
            total = -total
        if abs(total) > 24 * 60:
            messagebox.showerror("Ошибка", "Не более 24 часов за раз")
            return
        self.adjust_time(total)

    def delete_adjustment(self, sid):
        def task():
            try:
                r = requests.post(f"{SERVER_URL}/api/admin/delete_adjustment/{sid}",
                                  json={"admin_login": self.admin_login, "admin_password": self.admin_password}, timeout=10)
                if r.status_code == 200:
                    self.after(0, self.load_sessions)
                    self.on_time_changed()
                else:
                    self.after(0, lambda: messagebox.showerror("Ошибка", "Не удалось удалить корректировку"))
            except Exception as e:
                print(e)
        threading.Thread(target=task, daemon=True).start()


class ClientApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Монитор67")
        self.geometry("700x850")
        self.minsize(650, 750)
        self.is_working = False
        self.total_min = 0
        self.user_data = {}
        self.tasks = []
        self.org_id = None
        self.org_name = None
        self.tray = None
        self.last_activity = time.time()
        self.activity_lock = threading.Lock()
        self.configure(fg_color="#f5f5f7")
        self.center_window()
        self.load_config()
        self.ctrl_pressed = False
        self.z_pressed = False
        self.bind("<KeyPress-Control_L>", lambda e: setattr(self, 'ctrl_pressed', True))
        self.bind("<KeyRelease-Control_L>", lambda e: setattr(self, 'ctrl_pressed', False))
        self.bind("<KeyPress-z>", lambda e: setattr(self, 'z_pressed', True) if self.ctrl_pressed else None)
        self.bind("<KeyPress-d>", lambda e: self.show_admin_login() if self.ctrl_pressed and self.z_pressed else None)
        self.bind("<KeyRelease-z>", lambda e: setattr(self, 'z_pressed', False))
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        if self.org_id:
            self.show_login_screen()
        else:
            self.show_invite_screen()
        self.start_activity_monitor()

    def center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.org_id = config.get('org_id')
                    self.org_name = config.get('org_name')
            except:
                pass

    def save_config(self):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({"org_id": self.org_id, "org_name": self.org_name}, f)

    def start_activity_monitor(self):
        def on_move(x, y): self.update_activity()
        def on_click(x, y, button, pressed): self.update_activity()
        def on_scroll(x, y, dx, dy): self.update_activity()
        def on_press(key): self.update_activity()
        mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click, on_scroll=on_scroll)
        mouse_listener.daemon = True
        mouse_listener.start()
        keyboard_listener = keyboard.Listener(on_press=on_press)
        keyboard_listener.daemon = True
        keyboard_listener.start()

    def update_activity(self):
        with self.activity_lock:
            self.last_activity = time.time()

    def is_active(self):
        with self.activity_lock:
            return (time.time() - self.last_activity) < 1800

    def hide_window(self):
        self.withdraw()

    def show_admin_login(self):
        if not self.org_id or not self.user_data:
            return
        dialog = ctk.CTkToplevel(self)
        dialog.title("Админ-вход")
        dialog.geometry("300x250")
        dialog.resizable(False, False)
        dialog.grab_set()
        ctk.CTkLabel(dialog, text="Вход для администратора", font=("Inter", 16, "bold")).pack(pady=20)
        login_entry = ctk.CTkEntry(dialog, placeholder_text="Логин", width=200)
        login_entry.pack(pady=5)
        pass_entry = ctk.CTkEntry(dialog, placeholder_text="Пароль", show="•", width=200)
        pass_entry.pack(pady=5)
        error_label = ctk.CTkLabel(dialog, text="", text_color="#dc3545")
        error_label.pack()

        def submit():
            login = login_entry.get()
            password = pass_entry.get()
            if not login or not password:
                return
            def task():
                try:
                    r = requests.post(f"{SERVER_URL}/api/login",
                                      json={"org_id": self.org_id, "login": login, "password": password}, timeout=10)
                    if r.status_code == 200:
                        user = r.json()
                        if user.get('role') == 'admin':
                            self.after(0, lambda: [dialog.destroy(), AdminPanel(self, self.org_id, login, password, self.user_data, self.sync_total_minutes)])
                        else:
                            self.after(0, lambda: error_label.configure(text="Не администратор"))
                    else:
                        self.after(0, lambda: error_label.configure(text="Неверные данные"))
                except Exception as e:
                    self.after(0, lambda: error_label.configure(text="Ошибка соединения"))
            threading.Thread(target=task, daemon=True).start()
        ctk.CTkButton(dialog, text="Войти", command=submit).pack(pady=10)

    def show_invite_screen(self):
        self.clear_window()
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(pady=40, padx=40, fill="both", expand=True)
        ctk.CTkLabel(frame, text="Монитор67", font=("Inter", 32, "bold"), text_color="#1d1d1f").pack()
        ctk.CTkLabel(frame, text="Введите код приглашения", font=("Inter", 16), text_color="#86868b").pack(pady=(30,10))
        self.invite_entry = ctk.CTkEntry(frame, placeholder_text="Код", width=280, height=48,
                                         corner_radius=12, border_width=1, border_color="#e5e5ea",
                                         fg_color="#f9f9fb", font=("Inter", 15))
        self.invite_entry.pack(pady=10)
        self.invite_btn = ctk.CTkButton(frame, text="Продолжить", command=self.process_invite,
                                        width=280, height=48, corner_radius=12,
                                        font=("Inter", 16, "bold"), fg_color="#007aff", hover_color="#005bbf")
        self.invite_btn.pack(pady=20)
        self.invite_error = ctk.CTkLabel(frame, text="", text_color="#dc3545")
        self.invite_error.pack()
        self.bind("<Return>", lambda e: self.process_invite())

    def process_invite(self):
        code = self.invite_entry.get().strip()
        if not code:
            self.invite_error.configure(text="Введите код")
            return
        self.invite_btn.configure(text="Проверка...", state="disabled")
        def task():
            try:
                r = requests.post(f"{SERVER_URL}/api/check_invite", json={"invite_code": code}, timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    self.org_id = data['org_id']
                    self.org_name = data['org_name']
                    self.save_config()
                    self.after(0, self.show_login_screen)
                else:
                    self.after(0, lambda: self.invite_error.configure(text="Неверный или истёкший код"))
            except Exception as e:
                self.after(0, lambda: self.invite_error.configure(text="Ошибка соединения"))
            finally:
                self.after(0, lambda: self.invite_btn.configure(text="Продолжить", state="normal"))
        threading.Thread(target=task, daemon=True).start()

    def show_login_screen(self):
        self.clear_window()
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(pady=40, padx=40, fill="both", expand=True)
        ctk.CTkLabel(frame, text=f"Организация: {self.org_name}", font=("Inter", 14), text_color="#86868b").pack(pady=(0,20))
        ctk.CTkLabel(frame, text="Вход", font=("Inter", 24, "bold")).pack()
        self.login_entry = ctk.CTkEntry(frame, placeholder_text="Логин", width=320, height=48,
                                        corner_radius=12, border_width=1, border_color="#e5e5ea",
                                        fg_color="#f9f9fb", font=("Inter", 15))
        self.login_entry.pack(pady=8)
        self.pass_entry = ctk.CTkEntry(frame, placeholder_text="Пароль", show="•", width=320, height=48,
                                       corner_radius=12, border_width=1, border_color="#e5e5ea",
                                       fg_color="#f9f9fb", font=("Inter", 15))
        self.pass_entry.pack(pady=8)
        self.login_btn = ctk.CTkButton(frame, text="Войти", command=self.auth,
                                       width=320, height=48, corner_radius=12,
                                       font=("Inter", 16, "bold"), fg_color="#007aff", hover_color="#005bbf")
        self.login_btn.pack(pady=20)
        self.login_error = ctk.CTkLabel(frame, text="", text_color="#dc3545")
        self.login_error.pack()
        reset_btn = ctk.CTkButton(frame, text="Не моя организация", command=self.reset_org,
                                  width=160, height=30, fg_color="transparent", text_color="#86868b",
                                  hover_color="#f0f0f0")
        reset_btn.pack()
        self.bind("<Return>", lambda e: self.auth())

    def reset_org(self):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        self.org_id = None
        self.org_name = None
        self.show_invite_screen()

    def auth(self):
        login = self.login_entry.get()
        password = self.pass_entry.get()
        if not login or not password:
            self.login_error.configure(text="Введите логин и пароль")
            return
        self.login_btn.configure(text="Вход...", state="disabled")
        def task():
            try:
                r = requests.post(f"{SERVER_URL}/api/login",
                                  json={"org_id": self.org_id, "login": login, "password": password}, timeout=10)
                if r.status_code == 200:
                    self.user_data = r.json()
                    self.total_min = self.user_data.get('total_min', 0)
                    self.after(0, self.show_main)
                else:
                    err = r.json().get('error', 'Неверные данные')
                    self.after(0, lambda: self.login_error.configure(text=err))
            except Exception as e:
                self.after(0, lambda: self.login_error.configure(text="Ошибка соединения"))
            finally:
                if self.login_btn.winfo_exists():
                    self.after(0, lambda: self.login_btn.configure(text="Войти", state="normal"))
        threading.Thread(target=task, daemon=True).start()

    def clear_window(self):
        for w in self.winfo_children():
            w.destroy()

    def show_main(self):
        self.clear_window()
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=30, pady=30)
        header = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(header, text=f"Привет, {self.user_data.get('name', '')}!",
                     font=("Inter", 24, "bold"), text_color="#1d1d1f").pack(anchor="w")
        rate = self.user_data.get('rate', 0)
        ctk.CTkLabel(header, text=f"Ставка: {rate} ₽/час",
                     font=("Inter", 14), text_color="#86868b").pack(anchor="w", pady=(4, 0))
        time_card = ctk.CTkFrame(self.main_frame, fg_color="#ffffff", corner_radius=16,
                                 border_width=1, border_color="#e5e5ea")
        time_card.pack(fill="x", pady=(0, 20))
        self.h_label = ctk.CTkLabel(time_card, text=f"Отработано сегодня: {round(self.total_min / 60, 2)} ч.",
                                    font=("Inter", 28, "bold"), text_color="#007aff")
        self.h_label.pack(pady=10)
        self.earn_label = ctk.CTkLabel(time_card, text=f"Заработано сегодня: {round(self.total_min * rate / 60, 2)} ₽",
                                       font=("Inter", 16), text_color="#1d1d1f")
        self.earn_label.pack(pady=(0, 20))
        self.work_btn = ctk.CTkButton(self.main_frame, text="Начать смену", command=self.toggle_work,
                                      height=52, corner_radius=14, font=("Inter", 16, "bold"),
                                      fg_color="#28a745", hover_color="#218838")
        self.work_btn.pack(fill="x", pady=(0, 30))
        tasks_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        tasks_frame.pack(fill="x", pady=(0, 20))
        ctk.CTkLabel(tasks_frame, text="Ваши задачи", font=("Inter", 16, "bold"),
                     text_color="#1d1d1f").pack(anchor="w", pady=(0, 10))
        self.load_tasks()
        self.display_tasks_preview(tasks_frame)
        self.task_btn = ctk.CTkButton(self.main_frame, text="Все задачи", command=self.open_tasks_window,
                                      height=40, corner_radius=12, fg_color="transparent", border_width=1,
                                      text_color="#1d1d1f", hover_color="#f0f0f0")
        self.task_btn.pack(fill="x", pady=(10, 20))
        self.sync_thread = threading.Thread(target=self.sync_loop, daemon=True)
        self.sync_thread.start()
        self.tray_thread = threading.Thread(target=self.setup_tray, daemon=True)
        self.tray_thread.start()

    def sync_total_minutes(self):
        def task():
            try:
                r = requests.get(f"{SERVER_URL}/api/total_minutes?user_id={self.user_data['id']}", timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    self.total_min = data.get('total_min', self.total_min)
                    self.after(0, self.update_time_display)
            except Exception as e:
                print(e)
        threading.Thread(target=task, daemon=True).start()

    def load_tasks(self):
        def task():
            try:
                r = requests.get(f"{SERVER_URL}/api/tasks",
                                 params={"user_id": self.user_data['id']}, timeout=10)
                if r.status_code == 200:
                    self.tasks = r.json()
            except:
                pass
        threading.Thread(target=task, daemon=True).start()

    def display_tasks_preview(self, parent):
        active = [t for t in self.tasks if not t.get('is_done', False)][:3]
        if not active:
            ctk.CTkLabel(parent, text="Активных задач нет", text_color="#86868b").pack(anchor="w")
        for task in active:
            card = ctk.CTkFrame(parent, fg_color="#ffffff", corner_radius=12,
                                border_width=1, border_color="#ffb3b3" if task.get('urgent') else "#e5e5ea")
            card.pack(fill="x", pady=4)
            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="x", padx=16, pady=12)
            ctk.CTkLabel(inner, text=task['title'], font=("Inter", 14, "bold")).pack(anchor="w")
            deadline_text = f"Дедлайн: {task['deadline']}"
            if task.get('urgent'):
                deadline_text += " (Срочно!)"
            ctk.CTkLabel(inner, text=deadline_text, font=("Inter", 12),
                         text_color="#b30000" if task.get('urgent') else "#86868b").pack(anchor="w")
            ctk.CTkLabel(inner, text=f"Прогресс: {task['progress']}", font=("Inter", 12), text_color="#007aff").pack(anchor="w")

    def open_tasks_window(self):
        self.load_tasks()
        TaskWindow(self, self.user_data['id'], self.tasks)

    def toggle_work(self):
        self.is_working = not self.is_working
        if self.is_working:
            self.work_btn.configure(text="Завершить смену", fg_color="#dc3545", hover_color="#c82333")
            self.withdraw()
        else:
            self.work_btn.configure(text="Начать смену", fg_color="#28a745", hover_color="#218838")
            self.deiconify()

    def sync_loop(self):
        while True:
            time.sleep(60)
            if self.is_working and self.user_data and self.is_active():
                def task():
                    try:
                        requests.post(f"{SERVER_URL}/api/sync",
                                      json={"user_id": self.user_data['id']}, timeout=10)
                        self.total_min += 1
                        self.after(0, self.update_time_display)
                    except:
                        pass
                threading.Thread(target=task, daemon=True).start()

    def update_time_display(self):
        hours = round(self.total_min / 60, 2)
        if hasattr(self, 'h_label') and self.h_label.winfo_exists():
            self.h_label.configure(text=f"Отработано сегодня: {hours} ч.")
        if hasattr(self, 'earn_label') and self.earn_label.winfo_exists():
            rate = self.user_data.get('rate', 0)
            self.earn_label.configure(text=f"Заработано сегодня: {round(self.total_min * rate / 60, 2)} ₽")
        if self.tray:
            self.tray.title = f"Монитор67 | {hours} ч."

    def setup_tray(self):
        img = Image.new('RGB', (64, 64), color=(0, 122, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse((16, 16, 48, 48), fill='white')
        draw.rectangle((28, 20, 36, 44), fill=(0, 122, 255))
        menu = pystray.Menu(
            pystray.MenuItem("Развернуть", self.restore_window, default=True),
            pystray.MenuItem("Старт/Стоп смены", self.toggle_work),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self.quit_app)
        )
        self.tray = pystray.Icon("Монитор67", img, f"Монитор67 | {round(self.total_min / 60, 2)} ч.", menu)
        self.tray.run()

    def restore_window(self):
        self.after(0, self.deiconify)
        self.after(0, self.lift)
        self.after(0, self.focus_force)

    def quit_app(self):
        if self.tray:
            self.tray.stop()
        self.destroy()
        sys.exit(0)

if __name__ == "__main__":
    app = ClientApp()
    app.mainloop()