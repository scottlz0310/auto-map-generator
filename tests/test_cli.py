"""main.py CLI モジュールのユニットテスト"""

import sys
from pathlib import Path

import pytest
from PIL import Image

from main import cli_progress_callback, main


def test_cli_progress_callback(capsys: pytest.CaptureFixture[str]) -> None:
    cli_progress_callback(1, 10, "test.jpg", "SUCCESS", "成功メッセージ")
    captured = capsys.readouterr()
    assert "SUCCESS" not in captured.out
    assert "test.jpg" in captured.out

    cli_progress_callback(2, 10, "test2.jpg", "SKIP", "GPSなし")
    captured = capsys.readouterr()
    assert "スキップ" in captured.out

    cli_progress_callback(3, 10, "test3.jpg", "ERROR", "エラー発生")
    captured = capsys.readouterr()
    assert "エラー発生" in captured.out


def test_cli_main_invalid_input_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sys, "argv", ["main.py", "-i", "C:/non_existent_folder_xyz_123"]
    )
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 1


def test_cli_main_no_images(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setattr(sys, "argv", ["main.py", "-i", str(empty_dir)])
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 0


def test_cli_main_successful_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    photos_dir = tmp_path / "photos"
    photos_dir.mkdir()
    img_path = photos_dir / "sample.jpg"

    img = Image.new("RGB", (50, 50), "blue")
    exif = img.getexif()
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1], gps_ifd[2], gps_ifd[3], gps_ifd[4] = (
        "N",
        (35, 40, 52),
        "E",
        (139, 46, 1),
    )
    img.save(img_path, exif=exif)

    monkeypatch.setattr(sys, "argv", ["main.py", "-i", str(photos_dir), "-z", "14"])
    main()

    assert (photos_dir / "map_outputs" / "sample_map.png").exists()
