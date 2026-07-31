"""app.core モジュールのユニットテスト"""

from pathlib import Path

import pytest
from PIL import Image

from app.core import (
    _draw_fallback_pin,
    convert_dms_to_dd,
    extract_gps_location,
    fetch_tile,
    latlon_to_tile_xy,
    list_gps_images,
    process_images,
    render_map,
)


@pytest.mark.parametrize(
    ("dms", "ref", "expected"),
    [
        (((35, 1), (40, 1), (52, 1)), "N", 35.68111111111111),
        (((35, 1), (40, 1), (52, 1)), "S", -35.68111111111111),
        (((139, 1), (46, 1), (1, 1)), "E", 139.76694444444444),
        (((139, 1), (46, 1), (1, 1)), "W", -139.76694444444444),
        ((0, 0, 0), "N", 0.0),
    ],
)
def test_convert_dms_to_dd(dms: tuple[object, ...], ref: str, expected: float) -> None:
    result = convert_dms_to_dd(dms, ref)
    assert pytest.approx(result, rel=1e-5) == expected


@pytest.mark.parametrize(
    ("lat", "lon", "zoom"),
    [
        (35.6812, 139.7671, 15),
        (0.0, 0.0, 1),
        (-33.8688, 151.2093, 10),
    ],
)
def test_latlon_to_tile_xy(lat: float, lon: float, zoom: int) -> None:
    x, y = latlon_to_tile_xy(lat, lon, zoom)
    assert x > 0
    assert y > 0


def test_extract_gps_location(tmp_path: Path) -> None:
    # 1. EXIF GPS付き画像
    gps_img_path = tmp_path / "gps.jpg"
    img = Image.new("RGB", (50, 50), color="blue")
    exif = img.getexif()
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1] = "N"
    gps_ifd[2] = (35, 40, 52)
    gps_ifd[3] = "E"
    gps_ifd[4] = (139, 46, 1)
    img.save(gps_img_path, exif=exif)

    loc = extract_gps_location(gps_img_path)
    assert loc is not None
    assert pytest.approx(loc[0], rel=1e-3) == 35.6811
    assert pytest.approx(loc[1], rel=1e-3) == 139.7669

    # 2. EXIFなし画像
    no_gps_path = tmp_path / "nogps.jpg"
    img_nogps = Image.new("RGB", (50, 50), color="red")
    img_nogps.save(no_gps_path)
    assert extract_gps_location(no_gps_path) is None

    # 3. 不正ファイル
    bad_file = tmp_path / "bad.jpg"
    bad_file.write_text("invalid image content")
    assert extract_gps_location(bad_file) is None


def test_fetch_tile_cache_and_network(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    cache_dir = tmp_path / "tiles"
    monkeypatch.setattr("app.core.TILE_CACHE_DIR", cache_dir)

    # 失敗テスト (ダミーURL)
    tile_fail = fetch_tile(
        99999, 99999, 1, "https://invalid-domain-xyz-123.com/{z}/{x}/{y}.png"
    )
    assert tile_fail.size == (256, 256)

    # モックによる成功テスト
    def mock_urlopen(req: object) -> object:
        class MockResp:
            def read(self) -> bytes:
                buf = io.BytesIO()
                Image.new("RGBA", (256, 256), "green").save(buf, format="PNG")
                return buf.getvalue()

            def __enter__(self):
                return self

            def __exit__(self, *args: object) -> None:
                pass

        return MockResp()

    import hashlib
    import io
    import urllib.request

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

    url_template = "https://example.com/{z}/{x}/{y}.png"
    tile_success = fetch_tile(10, 20, 5, url_template)
    assert tile_success.size == (256, 256)

    url_hash = hashlib.md5(url_template.encode("utf-8")).hexdigest()[:8]
    assert (cache_dir / f"{url_hash}_5_10_20.png").exists()

    # 既存キャッシュからの読み込みテスト
    tile_from_cache = fetch_tile(10, 20, 5, url_template)
    assert tile_from_cache.size == (256, 256)


def test_render_map_and_fallback_pin(tmp_path: Path) -> None:
    # フォールバックピン描画の直接テスト
    canvas = Image.new("RGBA", (200, 200), "white")
    _draw_fallback_pin(canvas, 100.0, 100.0)
    assert canvas.size == (200, 200)

    # モックタイル取得で render_map テスト
    img = render_map(
        lat=35.6812,
        lon=139.7671,
        width=300,
        height=200,
        zoom=15,
        pin_path=None,
        tile_url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    )
    assert img.size == (300, 200)

    # カスタムピン画像指定でのテスト
    pin_path = tmp_path / "pin.png"
    Image.new("RGBA", (20, 40), "red").save(pin_path)
    img_custom_pin = render_map(
        lat=35.6812,
        lon=139.7671,
        width=300,
        height=200,
        zoom=15,
        pin_path=pin_path,
        tile_url_template="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    )
    assert img_custom_pin.size == (300, 200)


def test_process_images_workflow(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    in_dir.mkdir()
    out_dir = tmp_path / "out"

    # 空フォルダの場合
    success, skip, total = process_images(in_dir, out_dir)
    assert (success, skip, total) == (0, 0, 0)

    # 写真生成
    gps_path = in_dir / "photo1.jpg"
    img1 = Image.new("RGB", (50, 50), "yellow")
    exif = img1.getexif()
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1], gps_ifd[2], gps_ifd[3], gps_ifd[4] = (
        "N",
        (35, 40, 52),
        "E",
        (139, 46, 1),
    )
    img1.save(gps_path, exif=exif)

    nogps_path = in_dir / "photo2.jpg"
    Image.new("RGB", (50, 50), "black").save(nogps_path)

    events: list[tuple[int, int, str, str, str]] = []

    def on_progress(cur: int, tot: int, name: str, status: str, msg: str) -> None:
        events.append((cur, tot, name, status, msg))

    success, skip, total = process_images(
        input_dir=in_dir,
        output_dir=out_dir,
        on_progress=on_progress,
    )

    assert total == 2
    assert success == 1
    assert skip == 1
    assert (out_dir / "photo1_map.png").exists()

    # キャンセル動作のテスト
    def cancel_check() -> bool:
        return True

    success_c, _, _ = process_images(
        input_dir=in_dir,
        output_dir=out_dir,
        cancel_check=cancel_check,
    )
    assert success_c == 0


def test_list_gps_images(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    in_dir.mkdir()

    # 1. 存在しないディレクトリ
    assert list_gps_images(tmp_path / "non_existent") == []

    # 2. GPS付き画像とGPSなし画像の用意
    gps_path = in_dir / "photo1.jpg"
    img1 = Image.new("RGB", (50, 50), "yellow")
    exif = img1.getexif()
    gps_ifd = exif.get_ifd(0x8825)
    gps_ifd[1], gps_ifd[2], gps_ifd[3], gps_ifd[4] = (
        "N",
        (35, 40, 52),
        "E",
        (139, 46, 1),
    )
    img1.save(gps_path, exif=exif)

    nogps_path = in_dir / "photo2.jpg"
    Image.new("RGB", (50, 50), "black").save(nogps_path)

    gps_list = list_gps_images(in_dir)
    assert len(gps_list) == 1
    assert gps_list[0][0] == gps_path
