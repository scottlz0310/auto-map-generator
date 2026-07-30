"""写真個別マップ自動生成ツールの Tkinter GUI 実装。"""

import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import Any

from app.core import BASE_DIR, DEFAULT_PIN_PATH, process_images

CONFIG_FILE = BASE_DIR / "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "input_dir": "",
    "output_dir": "",
    "width": 800,
    "height": 600,
    "zoom": 15,
    "pin_image": str(DEFAULT_PIN_PATH),
    "tile_url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
}


def load_config() -> dict[str, Any]:
    """永続化された設定ファイルを読み込む。存在しない場合はデフォルト値を返す。"""
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data: Any = json.load(f)
                if isinstance(data, dict):
                    config.update(data)
        except (OSError, json.JSONDecodeError) as e:
            print(f"設定ファイル読み込み失敗: {e}")
    return config


def save_config(config: dict[str, Any]) -> None:
    """設定を json ファイルに保存する。"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except OSError as e:
        print(f"設定ファイル保存失敗: {e}")


class AutoMapGeneratorGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Auto Map Generator - 写真個別マップ自動生成")
        self.root.geometry("680x720")
        self.root.minsize(580, 600)

        self.config: dict[str, Any] = load_config()
        self.msg_queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.is_running = False
        self.cancel_requested = False

        self._create_widgets()
        self._load_values_from_config()

        # スレッド安全なGUI更新ループ
        _ = self.root.after(100, self._process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _create_widgets(self) -> None:
        # スタイル設定
        style = ttk.Style()
        style.theme_use("clam")

        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # ----------------------------------------------------
        # 1. フォルダ設定セクション
        # ----------------------------------------------------
        folder_frame = ttk.LabelFrame(main_frame, text=" フォルダ設定 ", padding="10")
        folder_frame.pack(fill=tk.X, pady=(0, 10))

        # 入力フォルダ
        ttk.Label(folder_frame, text="入力写真フォルダ:").grid(
            row=0, column=0, sticky=tk.W, pady=4
        )
        self.input_dir_var = tk.StringVar()
        ttk.Entry(folder_frame, textvariable=self.input_dir_var).grid(
            row=0, column=1, sticky=tk.EW, padx=5, pady=4
        )
        ttk.Button(folder_frame, text="参照...", command=self._browse_input_dir).grid(
            row=0, column=2, pady=4
        )

        # 出力フォルダ
        ttk.Label(folder_frame, text="出力先フォルダ:").grid(
            row=1, column=0, sticky=tk.W, pady=4
        )
        self.output_dir_var = tk.StringVar()
        ttk.Entry(folder_frame, textvariable=self.output_dir_var).grid(
            row=1, column=1, sticky=tk.EW, padx=5, pady=4
        )
        ttk.Button(folder_frame, text="参照...", command=self._browse_output_dir).grid(
            row=1, column=2, pady=4
        )

        ttk.Label(
            folder_frame,
            text="※出力先を空欄にすると、入力フォルダ配下に 'map_outputs' が自動作成されます。",
            font=("", 8),
            foreground="gray",
        ).grid(row=2, column=1, sticky=tk.W, padx=5)

        _ = folder_frame.columnconfigure(1, weight=1)

        # ----------------------------------------------------
        # 2. マップ・生成設定セクション
        # ----------------------------------------------------
        map_frame = ttk.LabelFrame(
            main_frame, text=" マップ生成オプション ", padding="10"
        )
        map_frame.pack(fill=tk.X, pady=(0, 10))

        # 画像サイズ
        size_frame = ttk.Frame(map_frame)
        size_frame.grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=4)

        ttk.Label(size_frame, text="横幅 (px):").pack(side=tk.LEFT, padx=(0, 5))
        self.width_var = tk.IntVar(value=800)
        ttk.Spinbox(
            size_frame,
            from_=200,
            to=4000,
            increment=50,
            textvariable=self.width_var,
            width=8,
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(size_frame, text="縦幅 (px):").pack(side=tk.LEFT, padx=(0, 5))
        self.height_var = tk.IntVar(value=600)
        ttk.Spinbox(
            size_frame,
            from_=200,
            to=4000,
            increment=50,
            textvariable=self.height_var,
            width=8,
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Label(size_frame, text="ズームレベル (1-19):").pack(
            side=tk.LEFT, padx=(0, 5)
        )
        self.zoom_var = tk.IntVar(value=15)
        ttk.Spinbox(
            size_frame, from_=1, to=19, increment=1, textvariable=self.zoom_var, width=5
        ).pack(side=tk.LEFT)

        # ピン画像
        ttk.Label(map_frame, text="ピン画像:").grid(
            row=1, column=0, sticky=tk.W, pady=4
        )
        self.pin_image_var = tk.StringVar()
        ttk.Entry(map_frame, textvariable=self.pin_image_var).grid(
            row=1, column=1, sticky=tk.EW, padx=5, pady=4
        )
        ttk.Button(map_frame, text="参照...", command=self._browse_pin_image).grid(
            row=1, column=2, pady=4
        )

        # タイルURL
        ttk.Label(map_frame, text="タイルURL:").grid(
            row=2, column=0, sticky=tk.W, pady=4
        )
        self.tile_url_var = tk.StringVar()
        ttk.Entry(map_frame, textvariable=self.tile_url_var).grid(
            row=2, column=1, columnspan=2, sticky=tk.EW, padx=5, pady=4
        )

        _ = map_frame.columnconfigure(1, weight=1)

        # ----------------------------------------------------
        # 3. 実行制御セクション
        # ----------------------------------------------------
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.start_btn = ttk.Button(
            btn_frame, text="▶ マップ一括生成を開始", command=self._start_process
        )
        self.start_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        self.cancel_btn = ttk.Button(
            btn_frame, text="■ 中断", command=self._cancel_process, state=tk.DISABLED
        )
        self.cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # ----------------------------------------------------
        # 4. 進捗＆ログエリア
        # ----------------------------------------------------
        progress_frame = ttk.LabelFrame(main_frame, text=" 処理進捗 ", padding="10")
        progress_frame.pack(fill=tk.BOTH, expand=True)

        self.status_label = ttk.Label(progress_frame, text="待機中...")
        self.status_label.pack(fill=tk.X, pady=(0, 4))

        self.progressbar = ttk.Progressbar(progress_frame, mode="determinate")
        self.progressbar.pack(fill=tk.X, pady=(0, 8))

        self.log_text = scrolledtext.ScrolledText(
            progress_frame, height=12, state=tk.DISABLED, font=("Consolas", 9)
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _load_values_from_config(self) -> None:
        self.input_dir_var.set(str(self.config.get("input_dir", "")))
        self.output_dir_var.set(str(self.config.get("output_dir", "")))
        self.width_var.set(int(self.config.get("width", 800)))
        self.height_var.set(int(self.config.get("height", 600)))
        self.zoom_var.set(int(self.config.get("zoom", 15)))
        self.pin_image_var.set(str(self.config.get("pin_image", str(DEFAULT_PIN_PATH))))
        self.tile_url_var.set(
            str(
                self.config.get(
                    "tile_url", "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
                )
            )
        )

    def _save_current_config(self) -> None:
        self.config["input_dir"] = self.input_dir_var.get()
        self.config["output_dir"] = self.output_dir_var.get()
        self.config["width"] = self.width_var.get()
        self.config["height"] = self.height_var.get()
        self.config["zoom"] = self.zoom_var.get()
        self.config["pin_image"] = self.pin_image_var.get()
        self.config["tile_url"] = self.tile_url_var.get()
        save_config(self.config)

    def _browse_input_dir(self) -> None:
        dir_path = filedialog.askdirectory(title="写真が保存されているフォルダを選択")
        if dir_path:
            self.input_dir_var.set(dir_path)
            self._save_current_config()

    def _browse_output_dir(self) -> None:
        dir_path = filedialog.askdirectory(title="地図画像の保存先フォルダを選択")
        if dir_path:
            self.output_dir_var.set(dir_path)
            self._save_current_config()

    def _browse_pin_image(self) -> None:
        file_path = filedialog.askopenfilename(
            title="ピン画像ファイルを選択",
            filetypes=[("PNG画像", "*.png"), ("すべてのファイル", "*.*")],
        )
        if file_path:
            self.pin_image_var.set(file_path)
            self._save_current_config()

    def _log(self, text: str) -> None:
        self.log_text.config(state=tk.NORMAL)
        _ = self.log_text.insert(tk.END, text + "\n")
        _ = self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _clear_log(self) -> None:
        self.log_text.config(state=tk.NORMAL)
        _ = self.log_text.delete("1.0", tk.END)
        self.log_text.config(state=tk.DISABLED)

    def _start_process(self) -> None:
        input_dir_str = self.input_dir_var.get().strip()
        if not input_dir_str:
            _ = messagebox.showwarning(
                "入力エラー", "対象の写真フォルダを指定してください。"
            )
            return

        input_dir = Path(input_dir_str)
        if not input_dir.exists() or not input_dir.is_dir():
            _ = messagebox.showerror(
                "エラー", f"指定された入力フォルダが存在しません:\n{input_dir}"
            )
            return

        output_dir_str = self.output_dir_var.get().strip()
        output_dir = (
            Path(output_dir_str) if output_dir_str else input_dir / "map_outputs"
        )

        pin_path_str = self.pin_image_var.get().strip()
        pin_path = Path(pin_path_str) if pin_path_str else DEFAULT_PIN_PATH

        self._save_current_config()

        self.is_running = True
        self.cancel_requested = False
        self.start_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        self._clear_log()
        self.progressbar["value"] = 0
        self.status_label.config(text="処理を開始します...")

        # 別スレッドでバックグラウンド実行
        thread = threading.Thread(
            target=self._worker,
            args=(
                input_dir,
                output_dir,
                self.width_var.get(),
                self.height_var.get(),
                self.zoom_var.get(),
                pin_path,
                self.tile_url_var.get(),
            ),
            daemon=True,
        )
        thread.start()

    def _cancel_process(self) -> None:
        if self.is_running:
            self.cancel_requested = True
            self.status_label.config(text="手動キャンセルのリクエスト中...")
            self._log(
                ">>> 中断リクエストを送信しました。現在の写真の処理が終わり次第停止します..."
            )

    def _worker(
        self,
        input_dir: Path,
        output_dir: Path,
        width: int,
        height: int,
        zoom: int,
        pin_path: Path,
        tile_url: str,
    ) -> None:
        def on_progress(
            current: int, total: int, filename: str, status: str, message: str
        ) -> None:
            self.msg_queue.put(
                ("PROGRESS", (current, total, filename, status, message))
            )

        def cancel_check() -> bool:
            return self.cancel_requested

        success_count, skip_count, total = process_images(
            input_dir=input_dir,
            output_dir=output_dir,
            width=width,
            height=height,
            zoom=zoom,
            pin_path=pin_path,
            tile_url=tile_url,
            on_progress=on_progress,
            cancel_check=cancel_check,
        )

        self.msg_queue.put(("FINISHED", (success_count, skip_count, total)))

    def _process_queue(self) -> None:
        """キューから通知を取り出し、GUIを更新するメインスレッド上のルーチン"""
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == "PROGRESS":
                    current: int = data[0]
                    total: int = data[1]
                    filename: str = data[2]
                    status: str = data[3]
                    message: str = data[4]
                    pct = (current / total) * 100 if total > 0 else 0
                    self.progressbar["value"] = pct
                    self.status_label.config(
                        text=f"[{current}/{total}] {filename} 処理中 ({pct:.0f}%)"
                    )

                    if status == "SUCCESS":
                        self._log(f"[{current}/{total}] {filename}: {message}")
                    elif status == "SKIP":
                        self._log(
                            f"[{current}/{total}] {filename}: [スキップ] {message}"
                        )
                    elif status == "ERROR":
                        self._log(f"[{current}/{total}] {filename}: [エラー] {message}")
                    elif status == "CANCELLED":
                        self._log(f"[{current}/{total}] {filename}: [中断] {message}")

                elif msg_type == "FINISHED":
                    success_count: int = data[0]
                    skip_count: int = data[1]
                    fin_total: int = data[2]
                    self.is_running = False
                    self.start_btn.config(state=tk.NORMAL)
                    self.cancel_btn.config(state=tk.DISABLED)

                    if fin_total == 0:
                        self.status_label.config(
                            text="対象写真が見つかりませんでした。"
                        )
                        self._log(
                            "指定されたフォルダに対象の写真（.jpg / .jpeg / .tif / .heic）が見つかりませんでした。"
                        )
                    elif self.cancel_requested:
                        self.status_label.config(text="処理を中断しました。")
                        self._log(
                            f"\n--- 処理中断: 成功 {success_count}枚, スキップ {skip_count}枚 ---"
                        )
                        _ = messagebox.showinfo(
                            "中断", "地図の自動生成を中断しました。"
                        )
                    else:
                        self.progressbar["value"] = 100
                        self.status_label.config(
                            text=f"処理完了: 成功 {success_count}/{fin_total}枚"
                        )
                        self._log("\n=== 処理完了 ===")
                        self._log(
                            f"成功: {success_count}枚 / GPSなしスキップ: {skip_count}枚 / 全体: {fin_total}枚"
                        )
                        _ = messagebox.showinfo(
                            "完了",
                            f"地図生成が完了しました！\n成功: {success_count}枚 / 合計: {fin_total}枚",
                        )

        except queue.Empty:
            pass

        _ = self.root.after(100, self._process_queue)

    def _on_close(self) -> None:
        self._save_current_config()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    AutoMapGeneratorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
