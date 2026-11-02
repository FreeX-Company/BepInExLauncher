import os
import sys
import zipfile
import urllib.request
import json
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import io

try:
    from PIL import Image, ImageTk, ImageDraw
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

CONFIG_FILE = "BepInExLauncher.json"
BEPINEX_RELEASE_URL = "https://api.github.com/repos/BepInEx/BepInEx/releases/latest"
REPO_URL = "https://raw.githubusercontent.com/FreeX-Company/BepInExLauncher/main/"

class BepInExLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BepInEx Launcher")
        self.root.geometry("640x520")
        self.root.minsize(520, 400)

        # Установка иконки окна как у EXE программы
        self.set_window_icon()

        self.game_exe_path = ""
        self.mods_data = []
        self.game_folder_name = ""
        self.icon_image_ref = None
        self.available_repo_games = []
        self.last_mods_state = set()
        self.available_exes = []

        self.apply_light_theme()
        
        # Сканируем доступные .exe файлы в папке
        self.scan_available_exes()
        self.game_exe_path = self.auto_detect_game_exe()
        
        if self.game_exe_path:
            self.game_folder_name = Path(self.game_exe_path).stem

        self.create_widgets()

        if self.game_exe_path and os.path.exists(self.game_exe_path):
            self.check_and_init_bepinex()
        else:
            messagebox.showerror("Ошибка", "Не удалось автоматически найти .exe файл игры в текущей папке!")

        # Фоновая проверка папки модов каждые 2 секунды (2000 мс)
        self.root.after(2000, self.check_mods_loop)

    def set_window_icon(self):
        try:
            icon_path = Path("icon.ico")
            if not icon_path.exists():
                icon_path = Path("icon.png")

            if icon_path.exists() and PIL_AVAILABLE:
                img = Image.open(icon_path)
                self.window_icon_photo = ImageTk.PhotoImage(img)
                self.root.iconphoto(True, self.window_icon_photo)
            elif icon_path.exists():
                self.window_icon_photo = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(True, self.window_icon_photo)
        except Exception:
            pass

    def apply_light_theme(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        bg = "#f5f5f7"
        fg = "#1d1d1f"
        btn_bg = "#e8e8ed"
        btn_fg = "#1d1d1f"
        accent = "#0071e3"
        
        style.configure(".", background=bg, foreground=fg)
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=btn_bg, foreground=btn_fg, padding=[12, 6])
        style.map("TNotebook.Tab", background=[("selected", accent)], foreground=[("selected", "#ffffff")])
        
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.map("TCheckbutton", background=[("active", bg)])
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=fg)
        style.configure("TButton", background=btn_bg, foreground=btn_fg, borderwidth=1, relief="flat")
        style.map("TButton", background=[("active", accent)], foreground=[("active", "#ffffff")])
        
        self.root.configure(bg=bg)

    def scan_available_exes(self):
        cwd = Path(os.getcwd())
        exes = list(cwd.glob("*.exe"))
        self.available_exes = [str(e.name) for e in exes]

    def auto_detect_game_exe(self):
        if not self.available_exes:
            return ""
        
        cwd = Path(os.getcwd())
        ignored_keywords = ["unity", "crash", "install", "unins", "setup"]
        
        valid_exes = [
            e for e in self.available_exes 
            if not any(kw in e.lower() for kw in ignored_keywords)
        ]
        
        if valid_exes:
            return str(cwd / valid_exes[0])
        elif self.available_exes:
            return str(cwd / self.available_exes[0])
        return ""

    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.tab_mods = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_mods, text="Мои моды")

        self.tab_shop = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_shop, text="Каталог модов")

        self.create_local_mods_widgets()
        self.create_shop_widgets()

        bottom_frame = ttk.Frame(self.root, padding=10)
        bottom_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # Выбор EXE файла рядом с кнопкой запуска
        exe_select_frame = ttk.Frame(bottom_frame)
        exe_select_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))

        ttk.Label(exe_select_frame, text="EXE игры:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.exe_combo = ttk.Combobox(exe_select_frame, state="readonly", values=self.available_exes)
        self.exe_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        if self.game_exe_path:
            self.exe_combo.set(Path(self.game_exe_path).name)
        elif self.available_exes:
            self.exe_combo.set(self.available_exes[0])
            
        self.exe_combo.bind("<<ComboboxSelected>>", self.on_exe_selected)

        launch_btn = ttk.Button(bottom_frame, text="Запустить игру", command=self.launch_game)
        launch_btn.pack(side=tk.RIGHT)

        if self.game_folder_name:
            self.load_repo_games()

    def on_exe_selected(self, event):
        selected_filename = self.exe_combo.get()
        if selected_filename:
            cwd = Path(os.getcwd())
            new_path = cwd / selected_filename
            if new_path.exists():
                self.game_exe_path = str(new_path)
                self.game_folder_name = Path(self.game_exe_path).stem
                
                # Переинициализируем BepInEx и загружаем моды для выбранного экзешника
                self.check_and_init_bepinex()
                self.load_repo_games()

    def create_local_mods_widgets(self):
        canvas_frame = ttk.LabelFrame(self.tab_mods, text="Активные моды")
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.canvas = tk.Canvas(canvas_frame, highlightthickness=0, bg="#f5f5f7")
        self.scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_shop_widgets(self):
        shop_main_frame = ttk.Frame(self.tab_shop, padding=5)
        shop_main_frame.pack(fill=tk.BOTH, expand=True)

        select_game_frame = ttk.Frame(shop_main_frame)
        select_game_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(select_game_frame, text="Игра:").pack(side=tk.LEFT, padx=(0, 5))
        
        self.game_combo = ttk.Combobox(select_game_frame, state="readonly", width=30)
        self.game_combo.pack(side=tk.LEFT, padx=5)
        self.game_combo.bind("<<ComboboxSelected>>", self.on_shop_game_selected)

        refresh_shop_btn = ttk.Button(select_game_frame, text="Обновить", command=self.load_repo_games)
        refresh_shop_btn.pack(side=tk.LEFT, padx=(5, 0))

        header_frame = ttk.Frame(shop_main_frame)
        header_frame.pack(fill=tk.X, pady=(5, 10))

        self.icon_label = ttk.Label(header_frame)
        self.icon_label.pack(side=tk.LEFT, padx=(0, 10))

        self.shop_info_label = ttk.Label(header_frame, text="", font=("Segoe UI", 11, "bold"))
        self.shop_info_label.pack(side=tk.LEFT, anchor="w", fill=tk.X, expand=True)

        canvas_frame = ttk.LabelFrame(shop_main_frame, text="Доступные моды и паки из репозитория")
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.shop_canvas = tk.Canvas(canvas_frame, highlightthickness=0, bg="#f5f5f7")
        self.shop_scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.shop_canvas.yview)
        self.shop_scrollable_frame = ttk.Frame(self.shop_canvas)

        self.shop_scrollable_frame.bind(
            "<Configure>",
            lambda e: self.shop_canvas.configure(scrollregion=self.shop_canvas.bbox("all"))
        )

        self.shop_canvas.create_window((0, 0), window=self.shop_scrollable_frame, anchor="nw")
        self.shop_canvas.configure(yscrollcommand=self.shop_scrollbar.set)

        self.shop_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.shop_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def get_game_dir(self):
        if not self.game_exe_path:
            return None
        return Path(self.game_exe_path).parent

    def check_and_init_bepinex(self):
        game_dir = self.get_game_dir()
        if not game_dir or not game_dir.exists():
            return

        bepinex_detected = (
            (game_dir / "winhttp.dll").exists() or 
            (game_dir / "winmm.dll").exists() or 
            (game_dir / "BepInEx" / "core" / "BepInEx.Core.dll").exists()
        )

        if not bepinex_detected:
            if messagebox.askyesno("BepInEx не найден", "В папке с игрой не обнаружен BepInEx. Скачать и установить последнюю версию автоматически?"):
                arch = self.ask_architecture()
                self.download_and_install_bepinex(game_dir, arch)
        
        self.load_mods()

    def ask_architecture(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Выбор разрядности")
        dialog.geometry("340x180")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (340 // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (180 // 2)
        dialog.geometry(f"+{x}+{y}")

        arch_var = tk.StringVar(value="x64")

        ttk.Label(dialog, text="Выберите разрядность BepInEx для игры:", font=("Segoe UI", 10, "bold")).pack(padx=10, pady=15)

        frame = ttk.Frame(dialog)
        frame.pack(padx=20, anchor="w")

        ttk.Radiobutton(frame, text="64-bit", variable=arch_var, value="x64").pack(anchor="w", pady=3)
        ttk.Radiobutton(frame, text="32-bit", variable=arch_var, value="x86").pack(anchor="w", pady=3)

        result = {"arch": "x64"}

        def on_confirm():
            result["arch"] = arch_var.get()
            dialog.destroy()

        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=15)
        ttk.Button(btn_frame, text="Установить", command=on_confirm).pack()

        self.root.wait_window(dialog)
        return result["arch"]

    def download_and_install_bepinex(self, game_dir, arch="x64"):
        try:
            self.root.config(cursor="watch")
            self.root.update()

            req = urllib.request.Request(
                BEPINEX_RELEASE_URL, 
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
            
            download_url = None
            for asset in data.get("assets", []):
                name = asset.get("name", "")
                if arch in name and name.endswith(".zip"):
                    download_url = asset.get("browser_download_url")
                    break
            
            if not download_url:
                raise Exception(f"Архив BepInEx {arch} не найден в релизах GitHub.")

            zip_path = game_dir / "bepinex_temp.zip"
            urllib.request.urlretrieve(download_url, zip_path)

            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(game_dir)

            if zip_path.exists():
                os.remove(zip_path)

            messagebox.showinfo("Успех", f"BepInEx ({arch}) успешно скачан и установлен!")
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось скачать BepInEx:\n{e}")
        finally:
            self.root.config(cursor="")

    def check_mods_loop(self):
        game_dir = self.get_game_dir()
        if game_dir:
            plugins_dir = game_dir / "BepInEx" / "plugins"
            if plugins_dir.exists():
                current_files = set(str(p) for p in plugins_dir.rglob("*.dll")) | set(str(p) for p in plugins_dir.rglob("*.dll.disabled"))
                if current_files != self.last_mods_state:
                    self.last_mods_state = current_files
                    self.load_mods()
        
        self.root.after(2000, self.check_mods_loop)

    def load_mods(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.mods_data.clear()

        game_dir = self.get_game_dir()
        if not game_dir:
            return

        plugins_dir = game_dir / "BepInEx" / "plugins"
        if not plugins_dir.exists():
            ttk.Label(self.scrollable_frame, text="Папка BepInEx/plugins не найдена.").pack(padx=5, pady=5)
            return

        all_files = list(plugins_dir.rglob("*.dll")) + list(plugins_dir.rglob("*.dll.disabled"))

        if not all_files:
            ttk.Label(self.scrollable_frame, text="В папке plugins нет модов.").pack(padx=5, pady=5)
            return

        for file_path in sorted(all_files, key=lambda p: p.name.lower()):
            is_disabled = file_path.name.endswith(".disabled")
            initial_state = not is_disabled

            var = tk.BooleanVar(value=initial_state)
            
            try:
                rel_path_str = str(file_path.relative_to(plugins_dir))
            except ValueError:
                rel_path_str = file_path.name

            if rel_path_str.endswith(".dll.disabled"):
                display_name = rel_path_str[:-13]
            elif rel_path_str.endswith(".dll"):
                display_name = rel_path_str[:-4]
            else:
                display_name = rel_path_str

            row_frame = ttk.Frame(self.scrollable_frame)
            row_frame.pack(fill=tk.X, anchor="w", padx=5, pady=2)

            chk = ttk.Checkbutton(
                row_frame, 
                text=display_name, 
                variable=var,
                command=lambda fp=file_path, v=var: self.toggle_mod(fp, v)
            )
            chk.pack(side=tk.LEFT, anchor="w")

            del_btn = ttk.Button(
                row_frame, 
                text="🗑️", 
                width=3,
                command=lambda fp=file_path: self.delete_mod(fp)
            )
            del_btn.pack(side=tk.RIGHT, padx=5)
            
            self.mods_data.append({"path": file_path, "var": var})

    def toggle_mod(self, file_path, var):
        is_checked = var.get()

        try:
            if not file_path.exists():
                item = next((i for i in self.mods_data if i["var"] == var), None)
                if item:
                    file_path = item["path"]

            if not is_checked and not file_path.name.endswith(".disabled"):
                new_path = file_path.with_name(file_path.name + ".disabled")
                if file_path.exists():
                    file_path.rename(new_path)
                    for item in self.mods_data:
                        if item["var"] == var:
                            item["path"] = new_path
            elif is_checked and file_path.name.endswith(".disabled"):
                new_path = file_path.with_name(file_path.name[:-9])
                if file_path.exists():
                    file_path.rename(new_path)
                    for item in self.mods_data:
                        if item["var"] == var:
                            item["path"] = new_path
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось изменить состояние мода:\n{e}")
            var.set(not is_checked)

    def delete_mod(self, file_path):
        if not file_path.exists():
            item = next((i for i in self.mods_data if i["path"] == file_path), None)
            if item:
                file_path = item["path"]

        if not file_path.exists():
            messagebox.showerror("Ошибка", "Файл мода не найден!")
            return

        if messagebox.askyesno("Подтверждение удаления", f"Вы действительно хотите удалить '{file_path.name}'?"):
            try:
                os.remove(file_path)
                self.load_mods()
            except Exception as e:
                messagebox.showerror("Ошибка", f"Не удалось удалить мод:\n{e}")

    def load_repo_games(self):
        try:
            github_api = "https://api.github.com/repos/FreeX-Company/BepInExLauncher/contents/Games"
            req = urllib.request.Request(github_api, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                contents = json.loads(response.read().decode())

            self.available_repo_games = [item.get("name") for item in contents if item.get("type") == "dir"]
            
            if self.available_repo_games:
                self.game_combo['values'] = self.available_repo_games
                
                matched_game = None
                if self.game_folder_name:
                    for g in self.available_repo_games:
                        if g.lower() == self.game_folder_name.lower():
                            matched_game = g
                            break

                if matched_game:
                    self.game_combo.set(matched_game)
                else:
                    self.game_combo.set(self.available_repo_games[0])
                
                self.load_repo_mods_for_game(self.game_combo.get())
            else:
                self.game_combo['values'] = []
                self.shop_info_label.config(text="")
        except Exception:
            pass

    def on_shop_game_selected(self, event):
        selected_game = self.game_combo.get()
        if selected_game:
            self.load_repo_mods_for_game(selected_game)

    def load_repo_mods_for_game(self, game_name):
        for widget in self.shop_scrollable_frame.winfo_children():
            widget.destroy()

        self.icon_label.config(image="")
        self.icon_image_ref = None
        self.shop_info_label.config(text=game_name)

        try:
            github_api = f"https://api.github.com/repos/FreeX-Company/BepInExLauncher/contents/Games/{game_name}"
            req = urllib.request.Request(github_api, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response:
                contents = json.loads(response.read().decode())

            has_items = False

            for item in contents:
                name = item.get("name", "")
                download_url = item.get("download_url", "")

                if name.lower() == "icon.png":
                    try:
                        with urllib.request.urlopen(urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})) as img_res:
                            img_data = img_res.read()
                            if PIL_AVAILABLE:
                                pil_img = Image.open(io.BytesIO(img_data)).convert("RGBA")
                                pil_img = pil_img.resize((48, 48), Image.Resampling.LANCZOS)
                                
                                mask = Image.new("L", (48, 48), 0)
                                draw = ImageDraw.Draw(mask)
                                draw.rounded_rectangle((0, 0, 48, 48), radius=12, fill=255)
                                
                                rounded_img = Image.new("RGBA", (48, 48))
                                rounded_img.paste(pil_img, (0, 0), mask=mask)
                                
                                self.icon_image_ref = ImageTk.PhotoImage(rounded_img)
                            else:
                                original_image = tk.PhotoImage(data=img_data)
                                self.icon_image_ref = original_image.subsample(6, 6)

                            self.icon_label.config(image=self.icon_image_ref)
                    except Exception:
                        pass
                    continue

                if name.endswith(".dll") or name.endswith(".zip"):
                    has_items = True
                    row_frame = ttk.Frame(self.shop_scrollable_frame, padding=5)
                    row_frame.pack(fill=tk.X, anchor="w")

                    display_name = name[:-4] if name.endswith(".dll") else (name[:-4] if name.endswith(".zip") else name)
                    file_type_label = "ZIP" if name.endswith(".zip") else "DLL"
                    ttk.Label(row_frame, text=f"{display_name} ({file_type_label})", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
                    
                    dl_btn = ttk.Button(row_frame, text="Скачать", command=lambda url=download_url, fname=name: self.download_repo_file(url, fname))
                    dl_btn.pack(side=tk.RIGHT)

            if not has_items:
                ttk.Label(self.shop_scrollable_frame, text="Для этой игры пока нет модов.").pack(padx=5, pady=5)

        except Exception:
            pass

    def download_repo_file(self, download_url, filename):
        game_dir = self.get_game_dir()
        if not game_dir:
            messagebox.showerror("Ошибка", "Путь к игре не определен!")
            return

        plugins_dir = game_dir / "BepInEx" / "plugins"
        plugins_dir.mkdir(parents=True, exist_ok=True)

        target_path = plugins_dir / filename

        try:
            self.root.config(cursor="watch")
            self.root.update()

            urllib.request.urlretrieve(download_url, target_path)

            if filename.endswith(".zip"):
                with zipfile.ZipFile(target_path, 'r') as zip_ref:
                    zip_ref.extractall(plugins_dir)
                os.remove(target_path)
                messagebox.showinfo("Успех", f"Архив {filename} успешно скачан и распакован!")
            else:
                messagebox.showinfo("Успех", f"Мод {filename} успешно скачан!")

            self.load_mods()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось скачать файл:\n{e}")
        finally:
            self.root.config(cursor="")

    def launch_game(self):
        if not self.game_exe_path or not os.path.exists(self.game_exe_path):
            messagebox.showerror("Ошибка", "Игровой EXE файл не найден!")
            return
        
        try:
            os.startfile(self.game_exe_path)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось запустить игру:\n{e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = BepInExLauncherApp(root)
    root.mainloop()
