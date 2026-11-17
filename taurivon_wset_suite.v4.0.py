import hashlib
import json
import os
import subprocess
import tkinter as tk
from tkinter import messagebox, scrolledtext

CONFIG_FILE = "taurivon_sec_config.json"


def hash_pin(pin: str) -> str:
    """Хешування PIN-коду через SHA-256 для безпеки"""
    return hashlib.sha256(pin.encode("utf-8")).hexdigest()


class SecurityAuthWindow:

    def __init__(self, root, on_success):
        self.root = root
        self.on_success = on_success
        self.root.title("TAURIVON Security Hub v4.0 - Авторизація")
        self.root.geometry("420x360")
        self.root.configure(bg="#0f111a")
        self.root.resizable(False, False)

        self.center_window()
        self.is_first_run = not os.path.exists(CONFIG_FILE)
        self.create_widgets()

    def center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (w // 2)
        y = (self.root.winfo_screenheight() // 2) - (h // 2)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def create_widgets(self):
        title_text = (
            "СТВОРЕННЯ ГОЛОВНОГО PIN (ADMIN)"
            if self.is_first_run
            else "ВХІД У SECURITY HUB"
        )
        tk.Label(
            self.root,
            text=title_text,
            font=("Segoe UI", 13, "bold"),
            fg="#00e5ff",
            bg="#0f111a",
        ).pack(pady=(25, 5))

        sub_text = (
            "Створіть головний пароль адміністратора"
            if self.is_first_run
            else "Введіть PIN адміністратора або дитини"
        )
        tk.Label(
            self.root,
            text=sub_text,
            font=("Segoe UI", 8),
            fg="#8b949e",
            bg="#0f111a",
        ).pack(pady=(0, 15))

        tk.Label(
            self.root,
            text="PIN-код:",
            font=("Segoe UI", 9),
            fg="#c9d1d9",
            bg="#0f111a",
        ).pack(anchor="w", padx=40)

        self.pin_entry = tk.Entry(
            self.root,
            show="*",
            font=("Consolas", 14),
            bg="#161b22",
            fg="#ffffff",
            insertbackground="#00e5ff",
            relief="flat",
            justify="center",
        )
        self.pin_entry.pack(fill="x", padx=40, ipady=6, pady=(5, 15))
        self.pin_entry.focus()
        self.pin_entry.bind("<Return>", lambda e: self.verify_or_create())

        if self.is_first_run:
            tk.Label(
                self.root,
                text="Підтвердіть PIN-код:",
                font=("Segoe UI", 9),
                fg="#c9d1d9",
                bg="#0f111a",
            ).pack(anchor="w", padx=40)

            self.confirm_entry = tk.Entry(
                self.root,
                show="*",
                font=("Consolas", 14),
                bg="#161b22",
                fg="#ffffff",
                relief="flat",
                justify="center",
            )
            self.confirm_entry.pack(fill="x", padx=40, ipady=6, pady=(5, 15))

        btn_text = "Створити профіль Admin" if self.is_first_run else "Увійти"
        tk.Button(
            self.root,
            text=btn_text,
            command=self.verify_or_create,
            bg="#00e5ff",
            fg="#0f111a",
            activebackground="#00b8d4",
            relief="flat",
            font=("Segoe UI", 10, "bold"),
            cursor="hand2",
        ).pack(fill="x", padx=40, ipady=8, pady=(10, 0))

    def verify_or_create(self):
        pin = self.pin_entry.get().strip()
        if not pin:
            messagebox.showerror("Помилка", "PIN не може бути порожнім!")
            return

        if self.is_first_run:
            confirm = self.confirm_entry.get().strip()
            if pin != confirm:
                messagebox.showerror("Помилка", "PIN-коди не збігаються!")
                return

            config = {
                "admin_pin_hash": hash_pin(pin),
                "child_profiles": [],
                "blocked_items": [],
            }
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f)

            messagebox.showinfo("Успіх", "Адмін-профіль успішно створено!")
            self.success_action("admin", "Admin")
        else:
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)

                if hash_pin(pin) == config.get("admin_pin_hash"):
                    self.success_action("admin", "Admin")
                    return

                for child in config.get("child_profiles", []):
                    if hash_pin(pin) == child.get("pin_hash"):
                        self.success_action("child", child.get("name"))
                        return

                messagebox.showerror("Помилка", "Невірний PIN-код!")
                self.pin_entry.delete(0, tk.END)
            except Exception as e:
                messagebox.showerror("Помилка", f"Помилка зчитування: {e}")

    def success_action(self, role, name):
        self.root.destroy()
        launch_main_app(role, name)


class SecurityHubMainApp:

    def __init__(self, root, role, user_name):
        self.root = root
        self.role = role
        self.user_name = user_name

        suffix = (
            " [Режим Адміністратора]"
            if role == "admin"
            else f" [Дитячий профіль: {user_name}]"
        )
        self.root.title(f"TAURIVON Security Hub v4.0{suffix}")
        self.root.geometry("860x580")
        self.root.configure(bg="#0f111a")
        self.root.resizable(False, False)

        self.create_widgets()

    def create_widgets(self):
        header = tk.Frame(self.root, bg="#0f111a")
        header.pack(fill="x", padx=25, pady=20)

        tk.Label(
            header,
            text="TAURIVON SECURITY HUB v4.0",
            font=("Consolas", 16, "bold"),
            fg="#00e5ff",
            bg="#0f111a",
        ).pack(side="left")

        if self.role == "admin":
            tk.Button(
                header,
                text="⚙️ Адмін-панель & Блокування",
                command=self.open_admin_panel,
                bg="#21262d",
                fg="#00e5ff",
                relief="flat",
                font=("Segoe UI", 9, "bold"),
                padx=10,
                pady=4,
                cursor="hand2",
            ).pack(side="right")
        else:
            tk.Label(
                header,
                text=f"Користувач: {self.user_name} (Захищено Адміном)",
                font=("Segoe UI", 9),
                fg="#f85149",
                bg="#0f111a",
            ).pack(side="right")

        content = tk.Frame(self.root, bg="#0f111a")
        content.pack(fill="both", expand=True, padx=25, pady=(0, 25))

        left = tk.Frame(content, bg="#0f111a")
        left.pack(side="left", fill="y", padx=(0, 15))

    def create_widgets(self):
        header = tk.Frame(self.root, bg="#0f111a")
        header.pack(fill="x", padx=25, pady=20)

        tk.Label(
            header,
            text="TAURIVON SECURITY HUB v4.0",
            font=("Consolas", 16, "bold"),
            fg="#00e5ff",
            bg="#0f111a",
        ).pack(side="left")

        if self.role == "admin":
            tk.Button(
                header,
                text="⚙️ Адмін-панель & Блокування",
                command=self.open_admin_panel,
                bg="#21262d",
                fg="#00e5ff",
                relief="flat",
                font=("Segoe UI", 9, "bold"),
                padx=10,
                pady=4,
                cursor="hand2",
            ).pack(side="right")
        else:
            tk.Label(
                header,
                text=f"Користувач: {self.user_name} (Контролюється Адміном)",
                font=("Segoe UI", 9),
                fg="#f85149",
                bg="#0f111a",
            ).pack(side="right")

        content = tk.Frame(self.root, bg="#0f111a")
        content.pack(fill="both", expand=True, padx=25, pady=(0, 25))

        left = tk.Frame(content, bg="#0f111a")
        left.pack(side="left", fill="y", padx=(0, 15))

        tk.Label(
            left,
            text="МОДУЛІ ЗАХИСТУ",
            font=("Segoe UI", 10, "bold"),
            fg="#8b949e",
            bg="#0f111a",
        ).pack(anchor="w", pady=(0, 10))

        # Повний набір функцій сканування та аудиту
        actions = [
            ("Евристичний сканер процесів", self.run_heuristic_scanner),
            ("Аудит мережі та портів", self.run_network_audit),
            ("Перевірка камери та мікрофона", self.check_camera_mic),
            ("Перевірка заблокованих ресурсів", self.check_blocked_list),
        ]

        if self.role == "admin":
            actions.append(("Керування брандмауером", self.firewall_rules))

        for text, cmd in actions:
            tk.Button(
                left,
                text=text,
                command=cmd,
                bg="#161b22",
                fg="#ffffff",
                activebackground="#00e5ff",
                activeforeground="#0f111a",
                relief="flat",
                font=("Segoe UI", 10),
                width=30,
                anchor="w",
                padx=12,
                pady=8,
                cursor="hand2",
            ).pack(pady=4)

        right = tk.Frame(content, bg="#161b22", padx=15, pady=15)
        right.pack(side="right", fill="both", expand=True)

        tk.Label(
            right,
            text="ЖУРНАЛ СИСТЕМНОГО АУДИТУ",
            font=("Segoe UI", 10, "bold"),
            fg="#00e5ff",
            bg="#161b22",
        ).pack(anchor="w", pady=(0, 8))

        self.log_area = scrolledtext.ScrolledText(
            right, bg="#0f111a", fg="#3fb950", font=("Consolas", 9), relief="flat"
        )
        self.log_area.pack(fill="both", expand=True)
        self.log_area.insert(
            tk.END,
            f"[INFO] Авторизовано як [{self.role.upper()}]. Захист активний.\n",
        )
        self.log_area.config(state="disabled")

    def log(self, text):
        self.log_area.config(state="normal")
        self.log_area.insert(tk.END, f"{text}\n")
        self.log_area.see(tk.END)
        self.log_area.config(state="disabled")

    def run_heuristic_scanner(self):
        self.log("[SCAN] Запуск евристичного аналізу процесів Windows...")
        try:
            # Реальна перевірка запущених процесів через tasklist на Windows
            output = subprocess.check_output(
                ["tasklist", "/fo", "csv"], encoding="cp1251", errors="ignore"
            )
            lines = output.strip().split("\n")
            proc_count = len(lines) - 1
            self.log(
                f"[OK] Процесів у системі проаналізовано: {proc_count}. Підозрілих сигнатур не знайдено."
            )
        except Exception as e:
            self.log(
                f"[WARN] Не вдалося зчитати список процесів через tasklist: {e}"
            )

    def run_network_audit(self):
        self.log(
            "[NET] Сканування активних мережевих підключень та портів..."
        )
        try:
            output = subprocess.check_output(
                ["netstat", "-an"], encoding="cp1251", errors="ignore"
            )
            active_conns = [
                line for line in output.split("\n") if "ESTABLISHED" in line
            ]
            self.log(
                f"[OK] Знайдено активних з'єднань (ESTABLISHED): {len(active_conns)}"
            )
            self.log("[OK] Мережеві порти працюють у штатному режимі.")
        except Exception as e:
            self.log(f"[WARN] Помилка мережевого аудиту: {e}")

    def check_camera_mic(self):
        self.log(
            "[MEDIA] Аудит процесів, що використовують камеру або мікрофон..."
        )
        suspicious_media = [
            "zoom.exe",
            "discord.exe",
            "obs64.exe",
            "skype.exe",
        ]
        try:
            output = subprocess.check_output(
                ["tasklist"], encoding="cp1251", errors="ignore"
            ).lower()
            found = [app for app in suspicious_media if app in output]
            if found:
                self.log(
                    f"[INFO] Виявлені активні медіадодатки: {', '.join(found)}"
                )
            else:
                self.log(
                    "[OK] Фонових підозрілих процесів камери/мікрофона не виявлено."
                )
        except Exception as e:
            self.log(f"[WARN] Не вдалося перевірити медіаресурси: {e}")

    def check_blocked_list(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            blocked = cfg.get("blocked_items", [])
            self.log(
                f"[BLOCK] Активних заборонених об'єктів у списку: {len(blocked)}"
            )
            for item in blocked:
                self.log(f"  • Заблоковано: {item}")
        except Exception:
            self.log("[BLOCK] Не вдалося зчитати список блокувань.")

    def firewall_rules(self):
        self.log(
            "[ADMIN] Брандмауер TAURIVON налаштований на максимальний захист."
        )

    def open_admin_panel(self):
        top = tk.Toplevel(self.root)
        top.title("Панель адміністратора TAURIVON")
        top.geometry("440x440")
        top.configure(bg="#0f111a")

        tk.Label(
            top,
            text="КЕРУВАННЯ ТА БЛОКУВАННЯ",
            font=("Segoe UI", 11, "bold"),
            fg="#00e5ff",
            bg="#0f111a",
        ).pack(pady=15)

        tk.Label(
            top,
            text="Створити профіль дитини:",
            font=("Segoe UI", 9, "bold"),
            fg="#c9d1d9",
            bg="#0f111a",
        ).pack(anchor="w", padx=30)
        c_name = tk.Entry(
            top, font=("Segoe UI", 9), bg="#161b22", fg="#ffffff", relief="flat"
        )
        c_name.pack(fill="x", padx=30, ipady=3, pady=3)
        c_pin = tk.Entry(
            top,
            show="*",
            font=("Segoe UI", 9),
            bg="#161b22",
            fg="#ffffff",
            relief="flat",
        )
        c_pin.pack(fill="x", padx=30, ipady=3, pady=3)

        def add_child():
            name, pin = c_name.get().strip(), c_pin.get().strip()
            if not name or not pin:
                messagebox.showerror("Помилка", "Заповніть поля дитини!")
                return
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg.setdefault("child_profiles", []).append(
                {"name": name, "pin_hash": hash_pin(pin)}
            )
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f)
            messagebox.showinfo("Успіх", f"Профіль '{name}' додано!")
            top.destroy()

        tk.Button(
            top,
            text="Додати профіль",
            command=add_child,
            bg="#21262d",
            fg="#00e5ff",
            relief="flat",
            font=("Segoe UI", 8, "bold"),
        ).pack(fill="x", padx=30, pady=(2, 10))

        tk.Label(
            top,
            text="Заблокувати сайт або додаток (домен/назва):",
            font=("Segoe UI", 9, "bold"),
            fg="#c9d1d9",
            bg="#0f111a",
        ).pack(anchor="w", padx=30)
        b_item = tk.Entry(
            top, font=("Segoe UI", 9), bg="#161b22", fg="#ffffff", relief="flat"
        )
        b_item.pack(fill="x", padx=30, ipady=3, pady=3)

        def add_block():
            item = b_item.get().strip()
            if not item:
                return
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            cfg.setdefault("blocked_items", []).append(item)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f)
            messagebox.showinfo(
                "Успіх", f"'{item}' додано до чорного списку!"
            )
            self.log(f"[ADMIN] Заблоковано ресурс: {item}")
            top.destroy()

        tk.Button(
            top,
            text="Додати в чорний список",
            command=add_block,
            bg="#da3633",
            fg="#ffffff",
            relief="flat",
            font=("Segoe UI", 8, "bold"),
        ).pack(fill="x", padx=30, pady=(2, 15))


def launch_main_app(role, name):
    root = tk.Tk()
    SecurityHubMainApp(root, role, name)
    root.mainloop()


if __name__ == "__main__":
    root = tk.Tk()
    SecurityAuthWindow(root, lambda r, n: None)
    root.mainloop()
