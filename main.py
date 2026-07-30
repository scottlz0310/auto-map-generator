"""写真のEXIF(GPS情報)を抽出し、写真ごとに個別マップ画像を自動生成・一括保存するCLIツール。"""

import argparse
import sys
from pathlib import Path
from typing import Any

from app.core import DEFAULT_PIN_PATH, process_images


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="写真のGPS位置情報から、写真ごとの個別の地図画像をまとめて自動生成します。",
        add_help=False,
    )
    _ = parser.add_argument(
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="このヘルプメッセージを表示して終了します",
    )
    _ = parser.add_argument(
        "-i",
        "--input-dir",
        type=Path,
        required=True,
        help="対象写真が保存されているフォルダのパス",
    )
    _ = parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="生成した地図画像の保存先フォルダ (省略時は入力フォルダ配下の 'map_outputs')",
    )
    _ = parser.add_argument(
        "-w",
        "-W",
        "--width",
        type=int,
        default=800,
        help="生成する地図画像の幅 (px, 既定値: 800)",
    )
    _ = parser.add_argument(
        "-h",
        "-H",
        "--height",
        type=int,
        default=600,
        help="生成する地図画像の高さ (px, 既定値: 600)",
    )
    _ = parser.add_argument(
        "-z",
        "--zoom",
        type=int,
        default=15,
        help="地図のズームレベル (1-19, 既定値: 15)",
    )
    _ = parser.add_argument(
        "--pin-image",
        type=Path,
        default=DEFAULT_PIN_PATH,
        help="使用するピン画像ファイルのパス",
    )
    _ = parser.add_argument(
        "--tile-url",
        type=str,
        default="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        help="タイルサーバーのURLテンプレート (既定値: OpenStreetMap)",
    )
    return parser.parse_args()


def cli_progress_callback(
    current: int, total: int, filename: str, status: str, message: str
) -> None:
    if status == "SUCCESS":
        print(f"[{current}/{total}] {filename}: -> {message}")
    elif status == "SKIP":
        print(f"[{current}/{total}] {filename}: -> {message} (スキップ)")
    elif status == "ERROR":
        print(f"[{current}/{total}] {filename}: -> {message}")


def main() -> None:
    args: Any = parse_args()

    raw_input_dir: Path = args.input_dir
    input_dir: Path = raw_input_dir.resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"エラー: 入力フォルダが存在しません: {input_dir}")
        sys.exit(1)

    raw_output_dir: Path | None = args.output_dir
    output_dir: Path = (
        raw_output_dir.resolve() if raw_output_dir else input_dir / "map_outputs"
    )

    raw_pin_image: Path = args.pin_image
    pin_path: Path = raw_pin_image.resolve()

    width: int = int(args.width)
    height: int = int(args.height)
    zoom: int = int(args.zoom)
    tile_url: str = str(args.tile_url)

    print("=== 写真個別マップ一括生成ツール (CLI) ===")
    print(f"入力フォルダ: {input_dir}")
    print(f"出力フォルダ: {output_dir}")
    print(f"画像サイズ  : {width}x{height} px")
    print(f"ズームレベル: {zoom}")
    print(f"ピン画像    : {pin_path}")
    print("-----------------------------------")

    success_count, skip_count, total = process_images(
        input_dir=input_dir,
        output_dir=output_dir,
        width=width,
        height=height,
        zoom=zoom,
        pin_path=pin_path,
        tile_url=tile_url,
        on_progress=cli_progress_callback,
    )

    if total == 0:
        print(f"指定されたフォルダに対象写真が見つかりません: {input_dir}")
        sys.exit(0)

    print("-----------------------------------")
    print(
        f"完了: 成功={success_count}枚, GPSなしスキップ={skip_count}枚, 合計={total}枚"
    )


if __name__ == "__main__":
    main()
