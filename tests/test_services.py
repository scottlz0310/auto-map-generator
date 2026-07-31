"""app.services モジュールのユニットテスト"""

from pathlib import Path

from PIL import Image

from app.services import PreviewService


def test_preview_service_fetch_gps_images(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    in_dir.mkdir()

    # GPS付き画像生成
    gps_path = in_dir / "photo1.jpg"
    img = Image.new("RGB", (50, 50), "yellow")
    exif = img.getexif()
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1], gps_ifd[2], gps_ifd[3], gps_ifd[4] = (
        "N",
        (35, 40, 52),
        "E",
        (139, 46, 1),
    )
    img.save(gps_path, exif=exif)

    results = PreviewService.fetch_gps_images(in_dir)
    assert len(results) == 1
    assert results[0][0] == gps_path


def test_preview_service_generate_preview_valid(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    in_dir.mkdir()

    gps_path = in_dir / "photo1.jpg"
    img = Image.new("RGB", (50, 50), "yellow")
    exif = img.getexif()
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1], gps_ifd[2], gps_ifd[3], gps_ifd[4] = (
        "N",
        (35, 40, 52),
        "E",
        (139, 46, 1),
    )
    img.save(gps_path, exif=exif)

    # 正常系
    res = PreviewService.generate_preview(
        image_path=gps_path,
        width=400,
        height=300,
        zoom=14,
    )
    assert res.success is True
    assert res.image is not None
    assert res.image.size == (400, 300)
    assert res.location is not None


def test_preview_service_generate_preview_invalid_cases(tmp_path: Path) -> None:
    # 1. 画像未指定
    r1 = PreviewService.generate_preview(image_path=None)
    assert r1.success is False
    assert "選択されていません" in r1.message

    # 2. 存在しないファイル
    r2 = PreviewService.generate_preview(image_path=tmp_path / "not_found.jpg")
    assert r2.success is False
    assert "存在しません" in r2.message

    # 3. 不正サイズ
    r3 = PreviewService.generate_preview(
        image_path=tmp_path / "dummy.jpg", width=0, height=-10
    )
    assert r3.success is False
    assert "正の整数" in r3.message

    # 4. 不正ズーム
    r4 = PreviewService.generate_preview(
        image_path=tmp_path / "dummy.jpg", width=800, height=600, zoom=25
    )
    assert r4.success is False
    assert "1 〜 19" in r4.message

    # 5. GPSなし画像
    nogps_path = tmp_path / "nogps.jpg"
    Image.new("RGB", (50, 50), "black").save(nogps_path)
    r5 = PreviewService.generate_preview(image_path=nogps_path)
    assert r5.success is False
    assert "GPS情報が含まれていません" in r5.message
