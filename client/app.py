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

ctk.set_appearance_mode("Light")
ctk.set_default_color_theme("blue")

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "monitor67_config.json")
SERVER_URL = "https://monitor-67--quwerix.replit.app"

BLUE        = "#007aff"
BLUE_HOVER  = "#0062cc"
GREEN       = "#28a745"
GREEN_HOVER = "#1e7e34"
RED         = "#dc3545"
RED_HOVER   = "#c82333"
BG          = "#f5f5f7"
CARD_BG     = "#ffffff"
BORDER      = "#e5e5ea"
TEXT_MAIN   = "#1d1d1f"
TEXT_SEC    = "#86868b"
URGENT_BG   = "#fff5f5"
URGENT_TEXT = "#b30000"


def make_round_icon(size=64, bg=BLUE):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((0, 0, size - 1, size - 1), fill=bg)
    m = size // 4
    w = size // 8
    draw.rectangle((size // 2 - w // 2, m, size // 2 + w // 2, size - m), fill="white")
    draw.ellipse((size // 2 - w, m - w // 2, size // 2 + w, m + w // 2), fill="white")
    return img


def fmt_minutes(total_min):
    h = int(total_min // 60)
    m = int(total_min % 60)
    return f"{h} ч {m:02d} мин"


def fmt_earnings(total_min, rate):
    return f"{total_min / 60 * rate:,.2f} ₽".replace(",", " ")


class TaskWindow(ctk.CTkToplevel):
    def __init__(self, master, tasks):
        super().__init__(master)
        self.master = master
        self.tasks = tasks
        self.title("Задачи")
        self.geometry("560x680")
        self.resizable(False, True)
        self.configure(fg_color=BG)
        self.grab_set()

        header = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0, height=56)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="Мои задачи", font=("Inter", 18, "bold"),
                     text_color=TEXT_MAIN).pack(side="left", padx=24, pady=16)
        ctk.CTkButton(header, text="Закрыть", width=80, height=32,
                      fg_color="transparent", text_color=TEXT_SEC,
                      hover_color="#f0f0f2", command=self.destroy).pack(side="right", padx=16)

        self.frame = ctk.CTkScrollableFrame(self, fg_color="transparent",
                                            scrollbar_button_color=BORDER)
        self.frame.pack(fill="both", expand=True, padx=20, pady=16)
        self.render()

    def render(self):
        for w in self.frame.winfo_children():
            w.destroy()
        active = [t for t in self.tasks if not t.get("is_done")]
        done   = [t for t in self.tasks if t.get("is_done")]
        self._section("Активные", active)
        self._section("Завершённые", done)

    def _section(self, title, items):
        ctk.CTkLabel(self.frame, text=title, font=("Inter", 13, "bold"),
                     text_color=TEXT_SEC).pack(anchor="w", pady=(12, 4))
        if not items:
            ctk.CTkLabel(self.frame, text="Нет задач",
                         text_color=TEXT_SEC, font=("Inter", 12)).pack(anchor="w", padx=4)
            return
        for t in items:
            self._card(t)

    def _card(self, task):
        urgent = task.get("urgent", False)
        is_done = task.get("is_done", False)
        border_c = "#ffb3b3" if urgent and not is_done else BORDER

        card = ctk.CTkFrame(self.frame, fg_color=CARD_BG, corner_radius=14,
                            border_width=1, border_color=border_c)
        card.pack(fill="x", pady=5)

        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=18, pady=14)

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text=task["title"], font=("Inter", 14, "bold"),
                     text_color=URGENT_TEXT if urgent and not is_done else TEXT_MAIN).pack(side="left")
        if is_done:
            ctk.CTkLabel(row, text="Завершено", font=("Inter", 11),
                         text_color=GREEN).pack(side="right")

        ctk.CTkLabel(body, text=f"Дедлайн: {task['deadline']}",
                     font=("Inter", 11), text_color=URGENT_TEXT if urgent and not is_done else TEXT_SEC).pack(anchor="w", pady=(4, 0))

        if task.get("assignees"):
            ctk.CTkLabel(body, text="Исполнители: " + ", ".join(task["assignees"]),
                         font=("Inter", 11), text_color=TEXT_SEC).pack(anchor="w")

        # Progress bar
        prog_str = task.get("progress", "0/0")
        try:
            done_n, total_n = map(int, prog_str.split("/"))
            pct = done_n / total_n if total_n else 0
        except:
            done_n, total_n, pct = 0, 0, 0

        pb_bg = ctk.CTkFrame(body, height=6, corner_radius=3, fg_color="#f0f0f5")
        pb_bg.pack(fill="x", pady=(8, 2))
        pb_bg.pack_propagate(False)
        if pct > 0:
            pb_fill = ctk.CTkFrame(pb_bg, height=6, corner_radius=3,
                                   fg_color=GREEN if pct == 1 else BLUE)
            pb_fill.place(relx=0, rely=0, relwidth=pct, relheight=1)
        ctk.CTkLabel(body, text=f"{done_n}/{total_n} выполнили",
                     font=("Inter", 11), text_color=TEXT_SEC).pack(anchor="w")

        if not is_done and not task.get("completed_by_me"):
            ctk.CTkButton(body, text="Отметить выполнение",
                          command=lambda tid=task["id"]: self._mark(tid),
                          width=160, height=32, corner_radius=8,
                          fg_color=BLUE, hover_color=BLUE_HOVER,
                          font=("Inter", 12, "bold")).pack(anchor="e", pady=(10, 0))
        elif not is_done:
            ctk.CTkLabel(body, text="Вы выполнили",
                         font=("Inter", 12, "bold"), text_color=GREEN).pack(anchor="e", pady=(10, 0))

    def _mark(self, task_id):
        def run():
            try:
                r = requests.post(f"{SERVER_URL}/api/task/{task_id}/done",
                                  json={"user_id": self.master.user_data["id"]}, timeout=10)
                if r.status_code == 200:
                    self.master.load_tasks()
                    self.after(400, self.render)
            except Exception as e:
                print("mark_done error:", e)
        threading.Thread(target=run, daemon=True).start()


class AdminPanel(ctk.CTkToplevel):
    def __init__(self, master, org_id, admin_login, admin_password, current_user, on_refresh):
        super().__init__(master)
        self.master = master
        self.org_id = org_id
        self.admin_login = admin_login
        self.admin_password = admin_password
        self.current_user = current_user
        self.on_refresh = on_refresh
        self.title("Администрирование")
        self.geometry("520x600")
        self.resizable(False, False)
        self.configure(fg_color=BG)
        self.grab_set()
        self._build()
        self._load_sessions()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color=CARD_BG, corner_radius=0, height=72)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text=self.current_user.get("name", ""),
                     font=("Inter", 18, "bold"), text_color=TEXT_MAIN).pack(side="left", padx=24, pady=(14, 2), anchor="sw")
        ctk.CTkLabel(header, text=f"Ставка: {self.current_user.get('rate', 0)} ₽/ч",
                     font=("Inter", 12), text_color=TEXT_SEC).pack(side="left", padx=(0, 24), pady=(0, 14), anchor="sw")

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=20, pady=16)

        # Quick adjust buttons
        ctk.CTkLabel(scroll, text="Корректировка времени",
                     font=("Inter", 13, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 8))

        btn_grid = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_grid.pack(fill="x")
        buttons = [("+2 ч", 120), ("+1 ч", 60), ("+30 мин", 30),
                   ("-30 мин", -30), ("-1 ч", -60), ("-2 ч", -120)]
        for i, (label, mins) in enumerate(buttons):
            is_neg = mins < 0
            b = ctk.CTkButton(btn_grid, text=label, width=110, height=36,
                              corner_radius=10, font=("Inter", 13),
                              fg_color=RED if is_neg else BLUE,
                              hover_color=RED_HOVER if is_neg else BLUE_HOVER,
                              command=lambda m=mins: self._adjust(m))
            b.grid(row=i // 3, column=i % 3, padx=4, pady=4)

        # Custom input
        sep = ctk.CTkFrame(scroll, fg_color=BORDER, height=1)
        sep.pack(fill="x", pady=14)
        ctk.CTkLabel(scroll, text="Произвольно",
                     font=("Inter", 13, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 8))

        custom = ctk.CTkFrame(scroll, fg_color="transparent")
        custom.pack(fill="x")
        self.hours_e = ctk.CTkEntry(custom, width=70, height=36, corner_radius=10,
                                    placeholder_text="0 ч")
        self.hours_e.grid(row=0, column=0, padx=(0, 6))
        self.mins_e = ctk.CTkEntry(custom, width=70, height=36, corner_radius=10,
                                   placeholder_text="0 мин")
        self.mins_e.grid(row=0, column=1, padx=(0, 6))
        self.sign_cb = ctk.CTkComboBox(custom, values=["+", "-"], width=68, height=36)
        self.sign_cb.set("+")
        self.sign_cb.grid(row=0, column=2, padx=(0, 6))
        ctk.CTkButton(custom, text="Применить", height=36, corner_radius=10,
                      fg_color=BLUE, hover_color=BLUE_HOVER,
                      command=self._apply_custom).grid(row=0, column=3)

        self.reason_e = ctk.CTkEntry(scroll, placeholder_text="Причина (необязательно)",
                                     height=38, corner_radius=10)
        self.reason_e.pack(fill="x", pady=10)

        sep2 = ctk.CTkFrame(scroll, fg_color=BORDER, height=1)
        sep2.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(scroll, text="Последние сессии",
                     font=("Inter", 13, "bold"), text_color=TEXT_MAIN).pack(anchor="w", pady=(0, 6))

        self.sessions_frame = ctk.CTkScrollableFrame(scroll, height=160,
                                                     fg_color=CARD_BG, corner_radius=12)
        self.sessions_frame.pack(fill="x")

    def _load_sessions(self):
        def run():
            try:
                r = requests.post(f"{SERVER_URL}/api/admin/user_sessions/{self.current_user['id']}",
                                  json={"admin_login": self.admin_login,
                                        "admin_password": self.admin_password}, timeout=10)
                if r.status_code == 200:
                    self.after(0, lambda: self._show_sessions(r.json()))
            except Exception as e:
                print("sessions error:", e)
        threading.Thread(target=run, daemon=True).start()

    def _show_sessions(self, sessions):
        for w in self.sessions_frame.winfo_children():
            w.destroy()
        for s in sessions[:12]:
            row = ctk.CTkFrame(self.sessions_frame, fg_color="transparent", height=36)
            row.pack(fill="x")
            row.pack_propagate(False)
            h = s["minutes"] // 60
            m = s["minutes"] % 60
            label = f"{s['date']}   {h}ч {m:02d}мин"
            ctk.CTkLabel(row, text=label, font=("Inter", 12),
                         text_color=TEXT_MAIN).pack(side="left", padx=12)
            if s["manual"]:
                ctk.CTkLabel(row, text="корр.", font=("Inter", 10),
                             text_color=TEXT_SEC).pack(side="left")
                ctk.CTkButton(row, text="Удалить", width=64, height=24,
                              fg_color="transparent", text_color=RED,
                              hover_color=URGENT_BG, font=("Inter", 11),
                              command=lambda sid=s["id"]: self._del(sid)).pack(side="right", padx=8)

    def _adjust(self, minutes):
        reason = self.reason_e.get()
        def run():
            try:
                r = requests.post(f"{SERVER_URL}/api/admin/adjust_time",
                                  json={"user_id": self.current_user["id"],
                                        "minutes": minutes, "reason": reason,
                                        "admin_login": self.admin_login,
                                        "admin_password": self.admin_password}, timeout=10)
                if r.status_code == 200:
                    self.after(0, self._load_sessions)
                    self.on_refresh()
            except Exception as e:
                print("adjust error:", e)
        threading.Thread(target=run, daemon=True).start()

    def _apply_custom(self):
        try:
            h = int(self.hours_e.get() or 0)
            m = int(self.mins_e.get() or 0)
        except:
            return
        total = h * 60 + m
        if self.sign_cb.get() == "-":
            total = -total
        if abs(total) > 24 * 60:
            return
        self._adjust(total)

    def _del(self, sid):
        def run():
            try:
                r = requests.post(f"{SERVER_URL}/api/admin/delete_adjustment/{sid}",
                                  json={"admin_login": self.admin_login,
                                        "admin_password": self.admin_password}, timeout=10)
                if r.status_code == 200:
                    self.after(0, self._load_sessions)
                    self.on_refresh()
            except Exception as e:
                print("del error:", e)
        threading.Thread(target=run, daemon=True).start()


class ClientApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Монитор67")
        self.geometry("420x700")
        self.minsize(380, 600)
        self.resizable(True, True)
        self.configure(fg_color=BG)

        self.is_working = False
        self.total_min = 0
        self.user_data = {}
        self.tasks = []
        self.org_id = None
        self.org_name = None
        self.tray = None
        self.last_activity = time.time()
        self.activity_lock = threading.Lock()
        self._shift_start = None

        self._center()
        self._load_config()
        self._setup_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self.hide_window)

        if self.org_id:
            self._show_login()
        else:
            self._show_invite()

        self._start_activity_monitor()

    def _center(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 420, 700
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE) as f:
                    c = json.load(f)
                    self.org_id = c.get("org_id")
                    self.org_name = c.get("org_name")
            except:
                pass

    def _save_config(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump({"org_id": self.org_id, "org_name": self.org_name}, f)

    def _setup_hotkeys(self):
        self._ctrl = False
        self._z = False
        self.bind("<KeyPress-Control_L>",  lambda e: setattr(self, "_ctrl", True))
        self.bind("<KeyRelease-Control_L>", lambda e: setattr(self, "_ctrl", False))
        self.bind("<KeyPress-z>",  lambda e: setattr(self, "_z", True) if self._ctrl else None)
        self.bind("<KeyRelease-z>", lambda e: setattr(self, "_z", False))
        self.bind("<KeyPress-d>",  lambda e: self._show_admin_login() if self._ctrl and self._z else None)

    def _start_activity_monitor(self):
        def act(): self.last_activity = time.time()
        ml = mouse.Listener(on_move=lambda x, y: act(),
                            on_click=lambda x, y, b, p: act(),
                            on_scroll=lambda x, y, dx, dy: act())
        ml.daemon = True; ml.start()
        kl = keyboard.Listener(on_press=lambda k: act())
        kl.daemon = True; kl.start()

    def is_active(self):
        with self.activity_lock:
            return (time.time() - self.last_activity) < 1800

    def hide_window(self):
        self.withdraw()

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    # ── Invite screen ────────────────────────────────────────────────
    def _show_invite(self):
        self._clear()
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=36, pady=48)

        ctk.CTkLabel(outer, text="Монитор67",
                     font=("Inter", 34, "bold"), text_color=TEXT_MAIN).pack()
        ctk.CTkLabel(outer, text="Учёт рабочего времени",
                     font=("Inter", 14), text_color=TEXT_SEC).pack(pady=(4, 40))

        ctk.CTkLabel(outer, text="КОД ПРИГЛАШЕНИЯ",
                     font=("Inter", 11, "bold"), text_color=TEXT_SEC).pack(anchor="w")
        self._inv_entry = ctk.CTkEntry(outer, height=50, corner_radius=12,
                                       border_color=BORDER, fg_color=CARD_BG,
                                       font=("Inter", 18), justify="center")
        self._inv_entry.pack(fill="x", pady=(6, 16))

        self._inv_btn = ctk.CTkButton(outer, text="Продолжить", height=50,
                                      corner_radius=12, font=("Inter", 15, "bold"),
                                      fg_color=BLUE, hover_color=BLUE_HOVER,
                                      command=self._process_invite)
        self._inv_btn.pack(fill="x")

        self._inv_err = ctk.CTkLabel(outer, text="", text_color=RED, font=("Inter", 12))
        self._inv_err.pack(pady=8)
        self.bind("<Return>", lambda e: self._process_invite())

    def _process_invite(self):
        code = self._inv_entry.get().strip()
        if not code:
            self._inv_err.configure(text="Введите код приглашения")
            return
        self._inv_btn.configure(text="Проверка...", state="disabled")
        def run():
            try:
                r = requests.post(f"{SERVER_URL}/api/check_invite",
                                  json={"invite_code": code}, timeout=10)
                if r.status_code == 200:
                    d = r.json()
                    self.org_id = d["org_id"]
                    self.org_name = d["org_name"]
                    self._save_config()
                    self.after(0, self._show_login)
                else:
                    self.after(0, lambda: self._inv_err.configure(text="Неверный или истёкший код"))
            except:
                self.after(0, lambda: self._inv_err.configure(text="Ошибка соединения"))
            finally:
                self.after(0, lambda: self._inv_btn.configure(text="Продолжить", state="normal"))
        threading.Thread(target=run, daemon=True).start()

    # ── Login screen ─────────────────────────────────────────────────
    def _show_login(self):
        self._clear()
        outer = ctk.CTkFrame(self, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=36, pady=48)

        ctk.CTkLabel(outer, text="Монитор67",
                     font=("Inter", 28, "bold"), text_color=TEXT_MAIN).pack()
        ctk.CTkLabel(outer, text=self.org_name or "",
                     font=("Inter", 13), text_color=TEXT_SEC).pack(pady=(4, 36))

        for attr, ph, show in [("_log_e", "Логин", ""), ("_pass_e", "Пароль", "•")]:
            ctk.CTkLabel(outer, text=ph.upper(),
                         font=("Inter", 10, "bold"), text_color=TEXT_SEC).pack(anchor="w")
            e = ctk.CTkEntry(outer, height=46, corner_radius=12,
                             border_color=BORDER, fg_color=CARD_BG,
                             font=("Inter", 14), show=show if show else "")
            e.pack(fill="x", pady=(4, 12))
            setattr(self, attr, e)

        self._log_btn = ctk.CTkButton(outer, text="Войти", height=50,
                                      corner_radius=12, font=("Inter", 15, "bold"),
                                      fg_color=BLUE, hover_color=BLUE_HOVER,
                                      command=self._auth)
        self._log_btn.pack(fill="x", pady=(4, 0))

        self._log_err = ctk.CTkLabel(outer, text="", text_color=RED, font=("Inter", 12))
        self._log_err.pack(pady=8)

        ctk.CTkButton(outer, text="Сменить организацию",
                      fg_color="transparent", text_color=TEXT_SEC,
                      hover_color="#ececee", font=("Inter", 12),
                      height=32, command=self._reset_org).pack()
        self.bind("<Return>", lambda e: self._auth())

    def _reset_org(self):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        self.org_id = None
        self.org_name = None
        self._show_invite()

    def _auth(self):
        login = self._log_e.get()
        pw    = self._pass_e.get()
        if not login or not pw:
            self._log_err.configure(text="Введите логин и пароль")
            return
        self._log_btn.configure(text="Вход...", state="disabled")
        def run():
            try:
                r = requests.post(f"{SERVER_URL}/api/login",
                                  json={"org_id": self.org_id, "login": login, "password": pw},
                                  timeout=10)
                if r.status_code == 200:
                    self.user_data = r.json()
                    self.total_min = self.user_data.get("total_min", 0)
                    self.after(0, self._show_main)
                else:
                    msg = r.json().get("error", "Неверные данные")
                    self.after(0, lambda: self._log_err.configure(text=msg))
            except:
                self.after(0, lambda: self._log_err.configure(text="Ошибка соединения"))
            finally:
                if self._log_btn.winfo_exists():
                    self.after(0, lambda: self._log_btn.configure(text="Войти", state="normal"))
        threading.Thread(target=run, daemon=True).start()

    # ── Main screen ──────────────────────────────────────────────────
    def _show_main(self):
        self._clear()
        self.unbind("<Return>")
        root = ctk.CTkScrollableFrame(self, fg_color="transparent")
        root.pack(fill="both", expand=True)

        # ── Header card ──
        header_card = ctk.CTkFrame(root, fg_color=BLUE, corner_radius=0)
        header_card.pack(fill="x")

        hinner = ctk.CTkFrame(header_card, fg_color="transparent")
        hinner.pack(fill="x", padx=26, pady=20)

        name = self.user_data.get("name", "")
        ctk.CTkLabel(hinner, text=f"Привет, {name}",
                     font=("Inter", 22, "bold"), text_color="white").pack(anchor="w")
        rate = self.user_data.get("rate", 0)
        ctk.CTkLabel(hinner, text=f"Ставка: {rate} ₽/час  •  {self.org_name or ''}",
                     font=("Inter", 12), text_color="rgba(255,255,255,0.8)").pack(anchor="w", pady=(2, 0))

        # ── Time card ──
        time_card = ctk.CTkFrame(root, fg_color=CARD_BG, corner_radius=20,
                                 border_width=1, border_color=BORDER)
        time_card.pack(fill="x", padx=20, pady=(16, 0))

        tc_inner = ctk.CTkFrame(time_card, fg_color="transparent")
        tc_inner.pack(fill="x", padx=20, pady=18)

        ctk.CTkLabel(tc_inner, text="СЕГОДНЯ",
                     font=("Inter", 10, "bold"), text_color=TEXT_SEC).pack(anchor="w")

        self._time_lbl = ctk.CTkLabel(tc_inner, text=fmt_minutes(self.total_min),
                                      font=("Inter", 32, "bold"), text_color=BLUE)
        self._time_lbl.pack(anchor="w", pady=(4, 0))

        self._earn_lbl = ctk.CTkLabel(tc_inner, text=fmt_earnings(self.total_min, rate),
                                      font=("Inter", 16), text_color=TEXT_MAIN)
        self._earn_lbl.pack(anchor="w", pady=(2, 0))

        # Status dot
        self._status_row = ctk.CTkFrame(tc_inner, fg_color="transparent")
        self._status_row.pack(anchor="w", pady=(10, 0))
        self._status_dot = ctk.CTkLabel(self._status_row, text="  ",
                                        width=12, height=12, corner_radius=6,
                                        fg_color=TEXT_SEC)
        self._status_dot.pack(side="left")
        self._status_lbl = ctk.CTkLabel(self._status_row, text="Не в смене",
                                        font=("Inter", 12), text_color=TEXT_SEC)
        self._status_lbl.pack(side="left", padx=(6, 0))

        # ── Work button ──
        self._work_btn = ctk.CTkButton(root, text="Начать смену",
                                       height=54, corner_radius=16,
                                       font=("Inter", 16, "bold"),
                                       fg_color=GREEN, hover_color=GREEN_HOVER,
                                       command=self._toggle_work)
        self._work_btn.pack(fill="x", padx=20, pady=14)

        # ── Tasks section ──
        tasks_header = ctk.CTkFrame(root, fg_color="transparent")
        tasks_header.pack(fill="x", padx=20, pady=(4, 0))
        ctk.CTkLabel(tasks_header, text="Задачи",
                     font=("Inter", 16, "bold"), text_color=TEXT_MAIN).pack(side="left")
        ctk.CTkButton(tasks_header, text="Все задачи",
                      width=90, height=28, corner_radius=8,
                      fg_color="transparent", text_color=BLUE,
                      hover_color="#eaf3ff", font=("Inter", 12),
                      command=self._open_tasks).pack(side="right")

        self._tasks_frame = ctk.CTkFrame(root, fg_color="transparent")
        self._tasks_frame.pack(fill="x", padx=20, pady=(8, 20))
        self.load_tasks(callback=self._render_tasks_preview)

        # Start bg threads
        threading.Thread(target=self._sync_loop, daemon=True).start()
        threading.Thread(target=self._setup_tray, daemon=True).start()

    def load_tasks(self, callback=None):
        def run():
            try:
                r = requests.get(f"{SERVER_URL}/api/tasks",
                                 params={"user_id": self.user_data["id"]}, timeout=10)
                if r.status_code == 200:
                    self.tasks = r.json()
                    if callback:
                        self.after(0, callback)
            except:
                pass
        threading.Thread(target=run, daemon=True).start()

    def _render_tasks_preview(self):
        for w in self._tasks_frame.winfo_children():
            w.destroy()
        active = [t for t in self.tasks if not t.get("is_done")][:4]
        if not active:
            ctk.CTkLabel(self._tasks_frame, text="Нет активных задач",
                         text_color=TEXT_SEC, font=("Inter", 13)).pack(anchor="w", pady=8)
            return
        for task in active:
            self._task_mini_card(task)

    def _task_mini_card(self, task):
        urgent = task.get("urgent", False)
        card = ctk.CTkFrame(self._tasks_frame, fg_color=URGENT_BG if urgent else CARD_BG,
                            corner_radius=12, border_width=1,
                            border_color="#ffb3b3" if urgent else BORDER)
        card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkLabel(row, text=task["title"],
                     font=("Inter", 13, "bold"),
                     text_color=URGENT_TEXT if urgent else TEXT_MAIN).pack(side="left")
        prog = task.get("progress", "0/0")
        ctk.CTkLabel(row, text=prog, font=("Inter", 12),
                     text_color=BLUE).pack(side="right")

        deadline_color = URGENT_TEXT if urgent else TEXT_SEC
        suffix = "  (Срочно!)" if urgent else ""
        ctk.CTkLabel(inner, text=f"Дедлайн: {task['deadline']}{suffix}",
                     font=("Inter", 11), text_color=deadline_color).pack(anchor="w", pady=(2, 0))

    def _open_tasks(self):
        self.load_tasks()
        time.sleep(0.3)
        TaskWindow(self, self.tasks)

    def _toggle_work(self):
        self.is_working = not self.is_working
        if self.is_working:
            self._shift_start = time.time()
            self._work_btn.configure(text="Завершить смену",
                                     fg_color=RED, hover_color=RED_HOVER)
            self._status_dot.configure(fg_color=GREEN)
            self._status_lbl.configure(text="Смена идёт", text_color=GREEN)
            self.withdraw()
        else:
            self._shift_start = None
            self._work_btn.configure(text="Начать смену",
                                     fg_color=GREEN, hover_color=GREEN_HOVER)
            self._status_dot.configure(fg_color=TEXT_SEC)
            self._status_lbl.configure(text="Не в смене", text_color=TEXT_SEC)
            self.deiconify()

    def _sync_loop(self):
        while True:
            time.sleep(60)
            if self.is_working and self.user_data and self.is_active():
                try:
                    requests.post(f"{SERVER_URL}/api/sync",
                                  json={"user_id": self.user_data["id"]}, timeout=10)
                    self.total_min += 1
                    self.after(0, self._update_display)
                except:
                    pass

    def _sync_total(self):
        def run():
            try:
                r = requests.get(f"{SERVER_URL}/api/total_minutes",
                                 params={"user_id": self.user_data["id"]}, timeout=10)
                if r.status_code == 200:
                    self.total_min = r.json().get("total_min", self.total_min)
                    self.after(0, self._update_display)
            except:
                pass
        threading.Thread(target=run, daemon=True).start()

    def _update_display(self):
        rate = self.user_data.get("rate", 0)
        if hasattr(self, "_time_lbl") and self._time_lbl.winfo_exists():
            self._time_lbl.configure(text=fmt_minutes(self.total_min))
        if hasattr(self, "_earn_lbl") and self._earn_lbl.winfo_exists():
            self._earn_lbl.configure(text=fmt_earnings(self.total_min, rate))
        if self.tray:
            self.tray.title = f"Монитор67 | {fmt_minutes(self.total_min)}"

    # ── Admin login dialog ───────────────────────────────────────────
    def _show_admin_login(self):
        if not self.org_id or not self.user_data:
            return
        dlg = ctk.CTkToplevel(self)
        dlg.title("Вход администратора")
        dlg.geometry("320x280")
        dlg.resizable(False, False)
        dlg.configure(fg_color=BG)
        dlg.grab_set()

        outer = ctk.CTkFrame(dlg, fg_color="transparent")
        outer.pack(fill="both", expand=True, padx=28, pady=24)

        ctk.CTkLabel(outer, text="Администрирование",
                     font=("Inter", 17, "bold"), text_color=TEXT_MAIN).pack(pady=(0, 16))

        log_e = ctk.CTkEntry(outer, height=42, corner_radius=10,
                             placeholder_text="Логин", fg_color=CARD_BG)
        log_e.pack(fill="x", pady=4)
        pw_e = ctk.CTkEntry(outer, height=42, corner_radius=10,
                            placeholder_text="Пароль", show="•", fg_color=CARD_BG)
        pw_e.pack(fill="x", pady=4)
        err_lbl = ctk.CTkLabel(outer, text="", text_color=RED, font=("Inter", 11))
        err_lbl.pack(pady=4)

        def submit():
            login, pw = log_e.get(), pw_e.get()
            if not login or not pw:
                return
            def run():
                try:
                    r = requests.post(f"{SERVER_URL}/api/login",
                                      json={"org_id": self.org_id,
                                            "login": login, "password": pw}, timeout=10)
                    if r.status_code == 200:
                        u = r.json()
                        if u.get("role") == "admin":
                            self.after(0, lambda: [dlg.destroy(),
                                       AdminPanel(self, self.org_id, login, pw,
                                                  self.user_data, self._sync_total)])
                        else:
                            self.after(0, lambda: err_lbl.configure(text="Не администратор"))
                    else:
                        self.after(0, lambda: err_lbl.configure(text="Неверные данные"))
                except:
                    self.after(0, lambda: err_lbl.configure(text="Ошибка соединения"))
            threading.Thread(target=run, daemon=True).start()

        ctk.CTkButton(outer, text="Войти", height=44, corner_radius=10,
                      fg_color=BLUE, hover_color=BLUE_HOVER,
                      font=("Inter", 14, "bold"),
                      command=submit).pack(fill="x", pady=(6, 0))
        dlg.bind("<Return>", lambda e: submit())

    # ── Tray ─────────────────────────────────────────────────────────
    def _setup_tray(self):
        icon_img = make_round_icon(64, BLUE)
        menu = pystray.Menu(
            pystray.MenuItem("Развернуть", self.restore_window, default=True),
            pystray.MenuItem("Старт / Стоп смены", self._toggle_work),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Выход", self._quit),
        )
        self.tray = pystray.Icon("Монитор67", icon_img,
                                  f"Монитор67 | {fmt_minutes(self.total_min)}", menu)
        self.tray.run()

    def restore_window(self):
        self.after(0, self.deiconify)
        self.after(0, self.lift)
        self.after(0, self.focus_force)

    def _quit(self):
        if self.tray:
            self.tray.stop()
        self.destroy()
        sys.exit(0)


if __name__ == "__main__":
    app = ClientApp()
    app.mainloop()
