"""app.gui モジュールの詳細なユニットテスト"""

import tkinter as tk
from pathlib import Path

import pytest

from app.gui import AutoMapGeneratorGUI, load_config, save_config


def test_config_load_and_save(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr("app.gui.CONFIG_FILE", cfg_file)

    # 1. 存在しない場合
    c1 = load_config()
    assert c1["width"] == 800

    # 2. 保存テスト
    c1["width"] = 1200
    save_config(c1)
    assert cfg_file.exists()

    # 3. 読み込みテスト
    c2 = load_config()
    assert c2["width"] == 1200

    # 4. 破損ファイル読み込みテスト
    cfg_file.write_text("invalid json")
    c3 = load_config()
    assert c3["width"] == 800


def test_gui_full_coverage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg_file = tmp_path / "config.json"
    monkeypatch.setattr("app.gui.CONFIG_FILE", cfg_file)

    try:
        root = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"Tkinter display not available: {e}")
    root.withdraw()
    gui = AutoMapGeneratorGUI(root)

    # ダイアログ参照メソッドのモックテスト
    monkeypatch.setattr(
        "app.gui.filedialog.askdirectory", lambda **kwargs: str(tmp_path)
    )
    monkeypatch.setattr(
        "app.gui.filedialog.askopenfilename",
        lambda **kwargs: str(tmp_path / "test.png"),
    )

    gui._browse_input_dir()
    assert gui.input_dir_var.get() == str(tmp_path)

    gui._browse_output_dir()
    assert gui.output_dir_var.get() == str(tmp_path)

    gui._browse_pin_image()
    assert gui.pin_image_var.get() == str(tmp_path / "test.png")

    # バリデーション失敗（空入力）のテスト
    gui.input_dir_var.set("")
    monkeypatch.setattr("app.gui.messagebox.showwarning", lambda *args, **kwargs: None)
    gui._start_process()

    # 存在しない入力フォルダ時のテスト
    gui.input_dir_var.set("C:/non_existent_folder_123")
    monkeypatch.setattr("app.gui.messagebox.showerror", lambda *args, **kwargs: None)
    gui._start_process()

    # 正常な開始 & ワーカースレッド・キュー処理テスト
    gui.input_dir_var.set(str(tmp_path))
    gui.output_dir_var.set("")

    monkeypatch.setattr("app.gui.messagebox.showinfo", lambda *args, **kwargs: None)

    # 実際にプロセスを直接ワーカースレッドなしで動作確認
    gui._start_process()

    # キューメッセージの送信＆処理を直接シミュレート
    gui.msg_queue.put(("PROGRESS", (1, 2, "img1.jpg", "SUCCESS", "ok")))
    gui.msg_queue.put(("PROGRESS", (2, 2, "img2.jpg", "SKIP", "no gps")))
    gui.msg_queue.put(("PROGRESS", (2, 2, "img3.jpg", "ERROR", "err")))
    gui.msg_queue.put(("PROGRESS", (2, 2, "img4.jpg", "CANCELLED", "cancel")))
    gui.msg_queue.put(("FINISHED", (1, 1, 2)))

    gui._process_queue()

    # 0枚時の通知テスト
    gui.msg_queue.put(("FINISHED", (0, 0, 0)))
    gui._process_queue()

    # キャンセル時の通知テスト
    gui.cancel_requested = True
    gui.msg_queue.put(("FINISHED", (1, 1, 2)))
    gui._process_queue()

    gui._on_close()
