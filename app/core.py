"""写真のEXIF解析および地図合成処理を提供するコアモジュール。"""

import io
import math
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from PIL import Image, ImageDraw

USER_AGENT = "AutoMapGenerator/1.0 (https://github.com/scottlz0310/PhotoGeoExplorer)"
TILE_CACHE_DIR = Path(os.environ.get("TEMP", ".")) / "auto_map_generator_tiles"
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PIN_PATH = BASE_DIR / "assets" / "green_pin.png"

# サポートする画像拡張子
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".tif", ".tiff", ".heic"}


def convert_dms_to_dd(dms: Any, ref: str) -> float:
    """度分秒(DMS)または数値・分数タプル表現を十進表記(Decimal Degrees)に変換"""
    if not dms or len(dms) < 3:
        return 0.0

    def _val(x: Any) -> float:
        if isinstance(x, (tuple, list)) and len(x) > 0:
            val0 = cast(Any, x[0])
            val1 = cast(Any, x[1]) if len(x) > 1 else 1
            num = float(val0)
            den = float(val1)
            return num / den if den != 0 else num
        return float(cast(Any, x))

    deg = _val(dms[0])
    minute = _val(dms[1])
    sec = _val(dms[2])
    dd = deg + (minute / 60.0) + (sec / 3600.0)
    if ref in ["S", "W"]:
        dd = -dd
    return dd


def extract_gps_location(image_path: Path) -> tuple[float, float] | None:
    """画像からEXIF GPS情報 (lat, lon) を抽出"""
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            if not exif:
                return None

            # GPS IFD
            gps_info = exif.get_ifd(0x8825)
            if not gps_info:
                return None

            lat_dms = gps_info.get(2)  # GPSLatitude
            lat_ref = gps_info.get(1)  # GPSLatitudeRef
            lon_dms = gps_info.get(4)  # GPSLongitude
            lon_ref = gps_info.get(3)  # GPSLongitudeRef

            if not (lat_dms and lat_ref and lon_dms and lon_ref):
                return None

            lat = convert_dms_to_dd(tuple(lat_dms), str(lat_ref))
            lon = convert_dms_to_dd(tuple(lon_dms), str(lon_ref))
            return lat, lon
    except (KeyError, ValueError, TypeError, AttributeError, OSError):
        return None


def latlon_to_tile_xy(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    """緯度経度から Mercator タイル座標(浮動小数点)を計算"""
    n = 2.0**zoom
    x = (lon + 180.0) / 360.0 * n
    lat_rad = math.radians(lat)
    y = (
        (1.0 - math.log(math.tan(lat_rad) + (1.0 / math.cos(lat_rad))) / math.pi)
        / 2.0
        * n
    )
    return x, y


def fetch_tile(x: int, y: int, z: int, tile_url_template: str) -> Image.Image:
    """指定タイルの画像を取得（ローカルキャッシュ対応）"""
    TILE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = TILE_CACHE_DIR / f"{z}_{x}_{y}.png"

    if cache_file.exists():
        try:
            return Image.open(cache_file).convert("RGBA")
        except (OSError, ValueError):
            pass

    url = tile_url_template.format(z=z, x=x, y=y)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req) as resp:
            data: bytes = resp.read()
            _ = cache_file.write_bytes(data)
            return Image.open(io.BytesIO(data)).convert("RGBA")
    except (urllib.error.URLError, OSError, ValueError):
        return Image.new("RGBA", (256, 256), (220, 220, 220, 255))


def _draw_fallback_pin(cropped_map: Image.Image, cx: float, cy: float) -> None:
    """ピン画像が存在しない場合のフォールバック描画"""
    draw = ImageDraw.Draw(cropped_map)
    pin_radius = 10
    draw.ellipse(
        [
            (cx - pin_radius - 2, cy - pin_radius - 2),
            (cx + pin_radius + 2, cy + pin_radius + 2),
        ],
        fill=(255, 255, 255, 255),
        outline=(100, 100, 100, 255),
        width=1,
    )
    draw.ellipse(
        [
            (cx - pin_radius, cy - pin_radius),
            (cx + pin_radius, cy + pin_radius),
        ],
        fill=(235, 59, 36, 255),
        outline=(180, 20, 20, 255),
        width=1,
    )
    draw.ellipse(
        [(cx - 3, cy - 3), (cx + 3, cy + 3)],
        fill=(255, 255, 255, 255),
    )


def render_map(
    lat: float,
    lon: float,
    width: int,
    height: int,
    zoom: int,
    pin_path: Path | None,
    tile_url_template: str,
) -> Image.Image:
    """中心座標(lat, lon)をもとに指定サイズの地図画像を合成・ピン描画"""
    tile_x, tile_y = latlon_to_tile_xy(lat, lon, zoom)
    center_px_x = tile_x * 256.0
    center_px_y = tile_y * 256.0

    left_px = center_px_x - (width / 2.0)
    top_px = center_px_y - (height / 2.0)
    right_px = center_px_x + (width / 2.0)
    bottom_px = center_px_y + (height / 2.0)

    min_tile_x = math.floor(left_px / 256.0)
    max_tile_x = math.floor(right_px / 256.0)
    min_tile_y = math.floor(top_px / 256.0)
    max_tile_y = math.floor(bottom_px / 256.0)

    canvas_w = (max_tile_x - min_tile_x + 1) * 256
    canvas_h = (max_tile_y - min_tile_y + 1) * 256
    canvas = Image.new("RGBA", (canvas_w, canvas_h))

    for ty in range(min_tile_y, max_tile_y + 1):
        for tx in range(min_tile_x, max_tile_x + 1):
            tile_img = fetch_tile(tx, ty, zoom, tile_url_template)
            pos_x = (tx - min_tile_x) * 256
            pos_y = (ty - min_tile_y) * 256
            canvas.paste(tile_img, (pos_x, pos_y))

    # 切り抜き
    crop_left = left_px - (min_tile_x * 256.0)
    crop_top = top_px - (min_tile_y * 256.0)
    crop_right = crop_left + width
    crop_bottom = crop_top + height

    cropped_map = canvas.crop((crop_left, crop_top, crop_right, crop_bottom))

    # ピン描画
    cx, cy = width / 2.0, height / 2.0

    if pin_path and pin_path.exists():
        try:
            with Image.open(pin_path) as pin_img:
                pin_rgba = pin_img.convert("RGBA")
                pw, ph = pin_rgba.size
                pin_left = round(cx - (pw / 2.0))
                pin_top = round(cy - ph)

                cropped_map.paste(pin_rgba, (pin_left, pin_top), mask=pin_rgba)
        except (OSError, ValueError):
            _draw_fallback_pin(cropped_map, cx, cy)
    else:
        _draw_fallback_pin(cropped_map, cx, cy)

    return cropped_map


def process_images(
    input_dir: Path,
    output_dir: Path,
    width: int = 800,
    height: int = 600,
    zoom: int = 15,
    pin_path: Path | None = None,
    tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    on_progress: Callable[[int, int, str, str, str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> tuple[int, int, int]:
    """対象フォルダ内の写真を一括処理する共通関数。

    on_progress: (current_index, total_count, filename, status, message) のコールバック
    cancel_check: Trueを返した場合に処理を中断する関数
    戻り値: (success_count, skip_count, total_count)
    """
    if not pin_path:
        pin_path = DEFAULT_PIN_PATH

    image_files = [
        p
        for p in input_dir.iterdir()
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    total = len(image_files)
    if total == 0:
        return 0, 0, 0

    output_dir.mkdir(parents=True, exist_ok=True)

    success_count = 0
    skip_count = 0

    for idx, img_path in enumerate(image_files, start=1):
        if cancel_check and cancel_check():
            if on_progress:
                on_progress(
                    idx,
                    total,
                    img_path.name,
                    "CANCELLED",
                    "処理が手動でキャンセルされました。",
                )
            break

        location = extract_gps_location(img_path)
        if not location:
            skip_count += 1
            if on_progress:
                on_progress(
                    idx, total, img_path.name, "SKIP", "GPS情報が見つかりません。"
                )
            continue

        lat, lon = location
        try:
            map_image = render_map(
                lat=lat,
                lon=lon,
                width=width,
                height=height,
                zoom=zoom,
                pin_path=pin_path,
                tile_url_template=tile_url,
            )
            out_name = f"{img_path.stem}_map.png"
            out_path = output_dir / out_name
            map_image.save(out_path, format="PNG")
            success_count += 1
            if on_progress:
                on_progress(
                    idx,
                    total,
                    img_path.name,
                    "SUCCESS",
                    f"位置情報 ({lat:.5f}, {lon:.5f}) -> {out_name} を作成しました。",
                )
        except Exception as e:  # noqa: BLE001
            if on_progress:
                on_progress(idx, total, img_path.name, "ERROR", f"生成エラー: {e}")

    return success_count, skip_count, total


def list_gps_images(input_dir: Path) -> list[tuple[Path, float, float]]:
    """入力フォルダ配下の写真ファイルから、GPS情報(lat, lon)を取得できたファイルのリストを返す。"""
    if not input_dir.exists() or not input_dir.is_dir():
        return []

    results: list[tuple[Path, float, float]] = []
    image_files = sorted(
        [
            p
            for p in input_dir.iterdir()
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
    )
    for p in image_files:
        loc = extract_gps_location(p)
        if loc:
            results.append((p, loc[0], loc[1]))
    return results
