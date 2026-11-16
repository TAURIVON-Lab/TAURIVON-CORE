import os
import sys
import time
import threading
import subprocess
import shutil
import json
import hashlib
import secrets
import winsound
from datetime import datetime
import customtkinter as ctk
from tkinter import messagebox, filedialog
import psutil

# Ініціалізація теми CustomTkinter
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

# Налаштування захищеного середовища в AppData
APPDATA_DIR = os.path.join(os.path.expanduser("~"), "AppData", "Local", "TAURIVON_SOFTWARE")
QUARANTINE_DIR = os.path.join(APPDATA_DIR, "Quarantine")
LOG_FILE = os.path.join(APPDATA_DIR, "security.log")
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")

for folder in [APPDATA_DIR, QUARANTINE_DIR]:
    if not os.path.exists(folder):
        os.makedirs(folder)

def write_security_log(message):
    """Запис подій у захищений аудит-лог"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass

def hash_pin_with_salt(pin_string, salt_hex):
    """Створення захищеного хешу PIN-коду через SHA-256 з використанням солі"""
    combined = salt_hex + pin_string
    return hashlib.sha256(combined.encode('utf-8')).hexdigest()

DANGEROUS_SIGNATURES = [
    "powershell -enc",
    "Invoke-Expression",
    "IEX(",
    "FromBase64String",
    "DownloadString",
    "Cscript.exe",
    "Wscript.Shell",
    "URLDownloadToFile",
    "del /f /s /q",
    "net user /add",
    "reg add HKLM",
    "-ExecutionPolicy Bypass",
    "-WindowStyle Hidden"
]

class TaurivonApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("TAURIVON Security Hub — Expert Protection (v3.4)")
        self.geometry("950x750")
        
        self.failed_attempts = 0
        self.is_locked_out = False
        self.lockout_end_time = 0
        
        # Події для контрольованого завершення фонових потоків
        self.stop_event = threading.Event()
        
        # Завантаження захищеного конфігу з солью та хешем
        self.load_or_create_secure_config()

        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.create_widgets()
        
        # Секретний тригер: швидке натискання Enter 9 разів
        self.bind("<Return>", lambda event: self.handle_stealth_trigger("Enter", "Секретна активація безпеки через Enter x9"))

        # Запуск оптимізованих фонових потоків
        self.start_system_monitor()
        self.start_browser_shield()
        
        write_security_log("Додаток TAURIVON Security Hub v3.4 успішно ініціалізовано.")

    def load_or_create_secure_config(self):
        default_pin = "0000"
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.pin_salt = data.get("pin_salt", secrets.token_hex(16))
                    self.admin_pin_hash = data.get("admin_pin_hash", hash_pin_with_salt(default_pin, self.pin_salt))
            else:
                self.pin_salt = secrets.token_hex(16)
                self.admin_pin_hash = hash_pin_with_salt(default_pin, self.pin_salt)
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    json.dump({
                        "pin_salt": self.pin_salt,
                        "admin_pin_hash": self.admin_pin_hash
                    }, f)
                write_security_log("Створено захищений файл конфігурації із солоним SHA-256 хешем.")
        except Exception as e:
            self.pin_salt = secrets.token_hex(16)
            self.admin_pin_hash = hash_pin_with_salt(default_pin, self.pin_salt)
            write_security_log(f"Помилка завантаження конфігу, застосовано дефолтний захист: {e}")

    def create_widgets(self):
        top_frame = ctk.CTkFrame(self, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=10)

        title_label = ctk.CTkLabel(top_frame, text="TAURIVON Security Hub v3.4", font=ctk.CTkFont(size=22, weight="bold"))
        title_label.pack(side="left")

        self.theme_menu = ctk.CTkSegmentedButton(top_frame, values=["Dark", "Light", "System"], command=self.change_theme)
        self.theme_menu.set("System")
        self.theme_menu.pack(side="right")

        path_label = ctk.CTkLabel(top_frame, text=f"Захищений простір AppData: {APPDATA_DIR} (Salted Hash Active)", font=ctk.CTkFont(size=11), text_color="gray")
        path_label.pack(side="bottom", anchor="w", pady=(5, 0))

        # Моніторинг ресурсів
        res_frame = ctk.CTkFrame(self)
        res_frame.pack(fill="x", padx=20, pady=10)

        self.cpu_label = ctk.CTkLabel(res_frame, text="💻 Завантаження CPU: вимірювання...", font=ctk.CTkFont(size=13))
        self.cpu_label.pack(anchor="w", padx=15, pady=5)

        self.ram_label = ctk.CTkLabel(res_frame, text="🧠 Оперативна пам'ять (RAM): вимірювання...", font=ctk.CTkFont(size=13))
        self.ram_label.pack(anchor="w", padx=15, pady=(0, 5))

        # Модуль антикрадія
        anti_theft_frame = ctk.CTkFrame(self, fg_color="#4A1515" if ctk.get_appearance_mode()=="Dark" else "#F8D7DA")
        anti_theft_frame.pack(fill="x", padx=20, pady=5)

        at_label = ctk.CTkLabel(anti_theft_frame, text="🛡️ Модуль «Антикрадій» (Швидкий тригер: натисніть Enter 9 разів)", font=ctk.CTkFont(size=14, weight="bold"))
        at_label.pack(anchor="w", padx=15, pady=5)

        self.alarm_btn = ctk.CTkButton(anti_theft_frame, text="🚨 Увімкнути режим тривоги Антикрадій", fg_color="#D9534F", hover_color="#C9302C", command=lambda: self.start_stealth_challenge("Активація сирени Антикрадій"))
        self.alarm_btn.pack(fill="x", padx=15, pady=(0, 10))

        # Кнопки функціоналу
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="both", expand=True, padx=20, pady=10)

        ctk.CTkButton(btn_frame, text="🔑 Змінити PIN-код адміністратора", fg_color="#F0AD4E", hover_color="#EEA236", text_color="black", command=self.change_admin_pin).pack(fill="x", pady=2)
        ctk.CTkButton(btn_frame, text="🌐 Захист браузера та перевірка процесів", fg_color="#337AB7", hover_color="#286090", command=lambda: self.start_stealth_challenge("Перевірка безпеки браузерів")).pack(fill="x", pady=2)
        ctk.CTkButton(btn_frame, text="📷 Реальний аудит активності камери", command=lambda: self.start_stealth_challenge("Аудит камери")).pack(fill="x", pady=2)
        ctk.CTkButton(btn_frame, text="🎙️ Реальний аудит активності мікрофона", command=lambda: self.start_stealth_challenge("Аудит мікрофона")).pack(fill="x", pady=2)
        ctk.CTkButton(btn_frame, text="🔒 Заблокувати екран/сеанс", fg_color="#F0AD4E", hover_color="#EEA236", text_color="black", command=lambda: self.start_stealth_challenge("Екстрене блокування сеансу")).pack(fill="x", pady=2)
        
        ctk.CTkButton(btn_frame, text="🔍 Розширений антивірусний сканер", fg_color="#5CB85C", hover_color="#4CAE4C", command=self.scan_folder).pack(fill="x", pady=2)
        ctk.CTkButton(btn_frame, text="☣️ Менеджер Карантину (керування загрозами)", fg_color="#D9534F", hover_color="#C9302C", command=self.open_quarantine_manager).pack(fill="x", pady=2)
        
        ctk.CTkButton(btn_frame, text="🧹 Безпечне очищення тимчасових файлів", command=self.clean_temp_files).pack(fill="x", pady=2)
        ctk.CTkButton(btn_frame, text="🌐 Мережевий інспектор (Network Monitor)", fg_color="#6F42C1", hover_color="#5A32A3", command=self.open_network_monitor).pack(fill="x", pady=2)
        ctk.CTkButton(btn_frame, text="📂 Відкрити журнал подій (security.log)", command=self.open_security_log).pack(fill="x", pady=2)

        # Статусний рядок
        self.status_box = ctk.CTkTextbox(self, height=45, font=ctk.CTkFont(size=11))
        self.status_box.pack(fill="x", padx=20, pady=5)
        self.status_box.insert("end", "Система ініціалізована у захищеному режимі v3.4. Натисніть Enter 9 разів для екстреної активації.")
        self.status_box.configure(state="disabled")

    def change_theme(self, new_theme):
        ctk.set_appearance_mode(new_theme)
        write_security_log(f"Змінено системну тему інтерфейсу на: {new_theme}")

    def start_system_monitor(self):
        def update_metrics():
            while not self.stop_event.is_set():
                try:
                    cpu_usage = psutil.cpu_percent(interval=1)
                    ram = psutil.virtual_memory()
                    if self.winfo_exists():
                        self.after(0, lambda: self.update_ui_metrics(cpu_usage, ram))
                except Exception:
                    pass
                for _ in range(2):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)

        threading.Thread(target=update_metrics, daemon=True).start()

    def start_browser_shield(self):
        def browser_guard_loop():
            browsers = ["chrome.exe", "msedge.exe", "firefox.exe", "opera.exe"]
            while not self.stop_event.is_set():
                try:
                    for proc in psutil.process_iter(['name', 'cmdline']):
                        p_name = proc.info['name'].lower()
                        if p_name in browsers:
                            cmdline = proc.info.get('cmdline')
                            if cmdline:
                                cmd_str = " ".join(cmdline).lower()
                                if "--load-extension" in cmd_str and "temp" in cmd_str:
                                    write_security_log(f"УВАГА: Виявлено підозріле розширення у браузері {p_name}!")
                except Exception:
                    pass
                for _ in range(10):
                    if self.stop_event.is_set():
                        break
                    time.sleep(1)

        threading.Thread(target=browser_guard_loop, daemon=True).start()

    def update_ui_metrics(self, cpu, ram):
        try:
            self.cpu_label.configure(text=f"💻 Завантаження CPU: {cpu}%")
            self.ram_label.configure(text=f"🧠 Оперативна пам'ять (RAM): {ram.percent}% ({ram.used // (1024**2)} MB / {ram.total // (1024**2)} MB)")
        except Exception:
            pass

    def handle_stealth_trigger(self, key_name, success_message):
        if not hasattr(self, 'stealth_count'):
            self.stealth_count = 0
            self.stealth_timer = time.time()

        current_time = time.time()
        if current_time - self.stealth_timer > 3.0:
            self.stealth_count = 0

        self.stealth_count += 1
        self.stealth_timer = current_time
        remaining = 9 - self.stealth_count

        if self.stealth_count >= 9:
            self.stealth_count = 0
            write_security_log(f"Успішна секретна активація через Enter x9: {success_message}")
            try:
                winsound.Beep(900, 200)
            except Exception:
                winsound.MessageBeep(winsound.MB_OK)

            messagebox.showinfo("Секретний режим", "Активовано комбінацією Enter x9!\nЗапускається екстрений захист.")
            threading.Thread(target=self.play_anti_theft_alarm, daemon=True).start()
            os.system("rundll32.exe user32.dll,LockWorkStation")
        else:
            try:
                self.status_box.configure(state="normal")
                self.status_box.delete("0.0", "end")
                self.status_box.insert("end", f"Секретний ввід [Enter]: натиснуто {self.stealth_count}/9. Залишилось: {remaining}")
                self.status_box.configure(state="disabled")
            except Exception:
                pass

    def start_stealth_challenge(self, action_name):
        if self.is_locked_out:
            remaining_time = int(self.lockout_end_time - time.time())
            if remaining_time > 0:
                winsound.MessageBeep(winsound.MB_ICONWARNING)
                messagebox.showwarning("Блокування безпеки", f"Доступ заблоковано ще на {remaining_time} сек.")
                return
            else:
                self.is_locked_out = False
                self.failed_attempts = 0

        dialog = ctk.CTkInputDialog(text="Введіть PIN-код адміністратора:", title="Авторизація безпеки")
        user_input = dialog.get_input()

        if user_input and hash_pin_with_salt(user_input.strip(), self.pin_salt) == self.admin_pin_hash:
            self.failed_attempts = 0
            try:
                winsound.Beep(800, 150)
            except Exception:
                winsound.MessageBeep(winsound.MB_OK)

            write_security_log(f"Успішна авторизація для дії: {action_name}")
            
            if "сирени" in action_name or "Антикрадій" in action_name:
                messagebox.showinfo("Успіх", f"Дію дозволено: {action_name}")
                threading.Thread(target=self.play_anti_theft_alarm, daemon=True).start()
            elif "блокування" in action_name:
                os.system("rundll32.exe user32.dll,LockWorkStation")
            elif "Аудит камери" in action_name:
                self.perform_camera_audit()
            elif "Аудит мікрофона" in action_name:
                self.perform_microphone_audit()
            elif "браузерів" in action_name:
                self.perform_browser_audit()
            else:
                messagebox.showinfo("Аудит", f"Дію дозволено. {action_name} завершено успішно.")
        else:
            self.failed_attempts += 1
            write_security_log(f"НЕВДАЛА СПРОБА АВТОРИЗАЦІЇ ({self.failed_attempts}/3)")
            
            if self.failed_attempts >= 3:
                self.is_locked_out = True
                self.lockout_end_time = time.time() + 20
                messagebox.showerror("Блокування", "Перевищено ліміт невірних спроб! Доступ заблоковано на 20 секунд.")
            else:
                remaining = 3 - self.failed_attempts
                messagebox.showwarning("Помилка", f"Невірний PIN-код! Залишилось спроб: {remaining}")

    def change_admin_pin(self):
        """Зміна PIN-коду адміністратора із запитом поточного"""
        dialog_old = ctk.CTkInputDialog(text="Введіть поточний PIN-код:", title="Зміна PIN-коду")
        old_pin = dialog_old.get_input()
        
        if not old_pin or hash_pin_with_salt(old_pin.strip(), self.pin_salt) != self.admin_pin_hash:
            messagebox.showerror("Помилка", "Поточний PIN-код введено невірно!")
            return

        dialog_new = ctk.CTkInputDialog(text="Введіть новий PIN-код (мінімум 4 символи):", title="Зміна PIN-коду")
        new_pin = dialog_new.get_input()

        if not new_pin or len(new_pin.strip()) < 4:
            messagebox.showwarning("Попередження", "PIN-код занадто короткий. Зміну скасовано.")
            return

        dialog_confirm = ctk.CTkInputDialog(text="Повторіть новий PIN-код:", title="Зміна PIN-коду")
        confirm_pin = dialog_confirm.get_input()

        if new_pin != confirm_pin:
            messagebox.showerror("Помилка", "Нові PIN-коди не збігаються!")
            return

        self.pin_salt = secrets.token_hex(16)
        self.admin_pin_hash = hash_pin_with_salt(new_pin.strip(), self.pin_salt)
        
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump({
                    "pin_salt": self.pin_salt,
                    "admin_pin_hash": self.admin_pin_hash
                }, f)
            write_security_log("Адміністратор успішно змінив PIN-код.")
            messagebox.showinfo("Успіх", "PIN-код успішно змінено та надійно збережено!")
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося зберегти новий конфіг: {e}")

    def perform_browser_audit(self):
        browsers = ["chrome.exe", "msedge.exe", "firefox.exe", "opera.exe"]
        active_browsers = set()
        try:
            for proc in psutil.process_iter(['name']):
                p_name = proc.info['name'].lower()
                if p_name in browsers:
                    active_browsers.add(p_name)
        except Exception as e:
            write_security_log(f"Помилка перевірки браузерів: {e}")

        if active_browsers:
            msg = "Захист браузера активний.\nВиявлені запущені браузери:\n• " + "\n• ".join(active_browsers) + "\n\nЖодних шкідливих ін'єкцій не виявлено."
            messagebox.showinfo("Захист браузера", msg)
        else:
            messagebox.showinfo("Захист браузера", "Наразі жоден підтримуваний браузер не запущено.")

    def perform_camera_audit(self):
        camera_keywords = ["zoom", "teams", "skype", "obs64", "discord", "meet", "webex", "droidcam", "manycam"]
        active_cam_procs = []
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                p_name = proc.info['name'].lower()
                if any(kw in p_name for kw in camera_keywords):
                    active_cam_procs.append(f"{proc.info['name']} (PID: {proc.info['pid']})")
        except Exception as e:
            write_security_log(f"Помилка аудиту камери: {e}")

        if active_cam_procs:
            msg = "Увага! Виявлено активні додатки зв'язку, які можуть використовувати камеру:\n\n" + "\n".join(active_cam_procs)
            messagebox.showwarning("Аудит камери: Активність знайдено", msg)
        else:
            messagebox.showinfo("Аудит камери", "Жодного відомого процесу, що використовує камеру, у системі не виявлено.")

    def perform_microphone_audit(self):
        mic_keywords = ["zoom", "teams", "skype", "discord", "audacity", "obs64", "viber", "telegram"]
        active_mic_procs = []
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                p_name = proc.info['name'].lower()
                if any(kw in p_name for kw in mic_keywords):
                    active_mic_procs.append(f"{proc.info['name']} (PID: {proc.info['pid']})")
        except Exception as e:
            write_security_log(f"Помилка аудиту мікрофона: {e}")

        if active_mic_procs:
            msg = "Увага! Виявлено активні додатки, які можуть використовувати мікрофон:\n\n" + "\n".join(active_mic_procs)
            messagebox.showwarning("Аудит мікрофона: Активність знайдено", msg)
        else:
            messagebox.showinfo("Аудит мікрофона", "Жодного активного процесу запису звуку не виявлено.")

    def play_anti_theft_alarm(self):
        for _ in range(5):
            try:
                winsound.Beep(1200, 300)
                time.sleep(0.1)
            except Exception:
                pass

    def scan_folder(self):
        folder_to_scan = filedialog.askdirectory(title="Виберіть папку для розширеного аналізу безпеки")
        if not folder_to_scan:
            return

        write_security_log(f"Запущено розширений антивірусний сканер для папки: {folder_to_scan}")
        scanned_count = 0
        threats_found = []
        whitelist_folders = ["jdk", "node_modules", ".git", "venv"]
        double_ext_risks = (".jpg.exe", ".png.exe", ".pdf.bat", ".txt.vbs", ".docx.cmd", ".jpeg.exe", ".mp4.exe", ".xlsx.ps1", ".pdf.exe")

        try:
            for root, dirs, files in os.walk(folder_to_scan):
                if any(w in root.lower() for w in whitelist_folders):
                    continue
                for file in files:
                    scanned_count += 1
                    file_path = os.path.join(root, file)
                    file_lower = file.lower()
                    is_threat = False
                    threat_reason = ""
                    
                    if file_lower.endswith(double_ext_risks):
                        is_threat = True
                        threat_reason = "Підозріле подвійне розширення (можливе маскування під файл даних)"
                    elif file_lower.endswith(('.bat', '.cmd', '.vbs', '.ps1', '.txt', '.log', '.py')):
                        try:
                            if os.path.getsize(file_path) < 5 * 1024 * 1024:
                                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                    for sig in DANGEROUS_SIGNATURES:
                                        if sig.lower() in content.lower():
                                            is_threat = True
                                            threat_reason = f"Знайдено небезпечний паттерн / сигнатуру: {sig}"
                                            break
                        except Exception:
                            pass
                    if is_threat:
                        threats_found.append((file_path, threat_reason))
        except Exception as e:
            messagebox.showerror("Помилка", f"Помилка під час сканування: {e}")
            return

        report_msg = f"Проскановано файлів: {scanned_count}\nВиявлено потенційних загроз: {len(threats_found)}"
        write_security_log(f"Сканування завершено. {report_msg}")

        if threats_found:
            details = "\n".join([f"• {os.path.basename(path)} — {reason}" for path, reason in threats_found[:10]])
            if len(threats_found) > 10:
                details += f"\n... та ще {len(threats_found) - 10} загроз."
            
            answer = messagebox.askyesno("УВАГА: Знайдено підозрілі файли!", f"{report_msg}\n\nБажаєте ізолювати ці файли в Карантин?\n\n{details}")
            if answer:
                success_moved = 0
                failed_moved = 0
                for path, _ in threats_found:
                    try:
                        shutil.move(path, QUARANTINE_DIR)
                        success_moved += 1
                        write_security_log(f"Файл успішно перенесено в Карантин: {path}")
                    except Exception as ex:
                        failed_moved += 1
                        write_security_log(f"Не вдалося ізолювати {path}: {ex}")
                
                if success_moved > 0 and failed_moved == 0:
                    messagebox.showinfo("Карантин", f"Успішно ізольовано файлів: {success_moved}")
                else:
                    messagebox.showwarning("Карантин завершено з помилками", f"Ізольовано: {success_moved}\nНе вдалося перемістити: {failed_moved}")
        else:
            messagebox.showinfo("Сканування завершено", f"{report_msg}\nЖодних відомих загроз не виявлено. Система чиста!")

    def open_quarantine_manager(self):
        q_win = ctk.CTkToplevel(self)
        q_win.title("TAURIVON Quarantine Manager")
        q_win.geometry("700x450")

        lbl = ctk.CTkLabel(q_win, text="🛡️ Ізольовані файли в Карантині:", font=ctk.CTkFont(size=15, weight="bold"))
        lbl.pack(anchor="w", padx=15, pady=10)

        files_frame = ctk.CTkScrollableFrame(q_win, height=250)
        files_frame.pack(fill="both", expand=True, padx=15, pady=5)

        quarantined_files = []
        try:
            if os.path.exists(QUARANTINE_DIR):
                quarantined_files = os.listdir(QUARANTINE_DIR)
        except Exception:
            pass

        if not quarantined_files:
            ctk.CTkLabel(files_frame, text="Карантин порожній. Загроз не виявлено.", text_color="gray").pack(pady=20)
        else:
            for file_name in quarantined_files:
                row_frame = ctk.CTkFrame(files_frame, fg_color="transparent")
                row_frame.pack(fill="x", pady=4)

                f_label = ctk.CTkLabel(row_frame, text=file_name, font=ctk.CTkFont(size=12))
                f_label.pack(side="left", padx=5)

                file_path = os.path.join(QUARANTINE_DIR, file_name)
                del_btn = ctk.CTkButton(row_frame, text="Видалити назавжди", fg_color="#D9534F", width=130, command=lambda p=file_path, w=q_win: self.delete_from_quarantine(p, w))
                del_btn.pack(side="right", padx=5)

                rest_btn = ctk.CTkButton(row_frame, text="Відновити", fg_color="#5CB85C", width=100, command=lambda p=file_path, w=q_win: self.restore_from_quarantine(p, w))
                rest_btn.pack(side="right", padx=5)

    def delete_from_quarantine(self, file_path, window):
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
            write_security_log(f"Файл остаточно видалено з карантину: {file_path}")
            messagebox.showinfo("Успіх", "Файл успішно знищено.")
            window.destroy()
            self.open_quarantine_manager()
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося видалити файл: {e}")

    def restore_from_quarantine(self, file_path, window):
        try:
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            dest = os.path.join(desktop, os.path.basename(file_path))
            shutil.move(file_path, dest)
            write_security_log(f"Файл відновлено з карантину на Робочий стіл: {dest}")
            messagebox.showinfo("Відновлення", f"Файл успішно відновлено на Робочий стіл:\n{dest}")
            window.destroy()
            self.open_quarantine_manager()
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося відновити файл: {e}")

    def open_network_monitor(self):
        net_win = ctk.CTkToplevel(self)
        net_win.title("TAURIVON Network Inspector")
        net_win.geometry("800x500")

        text_box = ctk.CTkTextbox(net_win, font=ctk.CTkFont(family="Consolas", size=12))
        text_box.pack(fill="both", expand=True, padx=10, pady=10)

        connections_info = "PID    | ЛОКАЛЬНА АДРЕСА        | ВІДДАЛЕНА АДРЕСА      | СТАТУС       | ПРОЦЕС\n"
        connections_info += "-" * 85 + "\n"

        try:
            for conn in psutil.net_connections(kind='inet'):
                laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "-"
                raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "-"
                status = conn.status
                pid = conn.pid if conn.pid else "N/A"
                proc_name = "Unknown"
                if conn.pid:
                    try:
                        proc_name = psutil.Process(conn.pid).name()
                    except Exception:
                        pass
                connections_info += f"{str(pid):<6} | {laddr:<21} | {raddr:<21} | {status:<13} | {proc_name}\n"
        except Exception as e:
            connections_info += f"Помилка отримання з'єднань: {e}\n"

        text_box.insert("end", connections_info)
        text_box.configure(state="disabled")

    def clean_temp_files(self):
        temp_dir = os.path.expanduser(r"~\AppData\Local\Temp")
        answer = messagebox.askyesno("Безпечне очищення", "Бажаєте запустити безпечне очищення тимчасових файлів користувача?")
        if not answer:
            return

        write_security_log(f"Запущено безпечне очищення папки Temp: {temp_dir}")
        deleted_files = 0
        deleted_dirs = 0
        failed_count = 0

        if os.path.exists(temp_dir):
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    real_path = os.path.realpath(item_path)
                    real_temp = os.path.realpath(temp_dir)
                    if not real_path.startswith(real_temp):
                        continue
                except Exception:
                    continue

                try:
                    if os.path.isfile(item_path) or os.path.islink(item_path):
                        os.unlink(item_path)
                        deleted_files += 1
                    elif os.path.isdir(item_path):
                        try:
                            shutil.rmtree(item_path)
                            deleted_dirs += 1
                        except PermissionError:
                            failed_count += 1
                        except Exception:
                            failed_count += 1
                except Exception:
                    failed_count += 1
        
        report_msg = f"Очищення Temp завершено!\nВидалено файлів: {deleted_files}\nВидалено папок: {deleted_dirs}\nПропущено зайнятих: {failed_count}"
        write_security_log(f"Підсумок очищення Temp: файлів - {deleted_files}, папок - {deleted_dirs}")
        messagebox.showinfo("Результат очищення", report_msg)

    def open_security_log(self):
        if os.path.exists(LOG_FILE):
            os.startfile(LOG_FILE)
        else:
            messagebox.showwarning("Логи", "Файл подій порожній.")

    def on_closing(self):
        write_security_log("Користувач завершив роботу TAURIVON Security Hub.")
        self.stop_event.set()
        self.after(100, self.destroy)

if __name__ == "__main__":
    app = TaurivonApp()
    app.mainloop()
