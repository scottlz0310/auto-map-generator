"""アプリケーション・サービス層モジュール。

GUI や CLI などの UI 層とコアロジック (app.core) の間を媒介し、
ユースケースに応じたビジネスロジックやドメインモデル変換・バリデーションを提供する。
"""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from app.core import DEFAULT_PIN_PATH, extract_gps_location, list_gps_images, render_map


@dataclass(frozen=True)
class PreviewResult:
    """プレビュー生成処理の実行結果オブジェクト。"""

    image: Image.Image | None
    location: tuple[float, float] | None
    message: str
    success: bool


class PreviewService:
    """マッププレビュー機能を提供するサービスクラス。"""

    @staticmethod
    def fetch_gps_images(input_dir: Path) -> list[tuple[Path, float, float]]:
        """指定されたフォルダからGPS位置情報を含む画像一覧を取得。"""
        return list_gps_images(input_dir)

    @staticmethod
    def generate_preview(
        image_path: Path | None,
        width: int = 800,
        height: int = 600,
        zoom: int = 15,
        pin_path: Path | None = None,
        tile_url: str = "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    ) -> PreviewResult:
        """単一の画像から指定のパラメータで地図プレビュー画像を合成する。

        パラメータバリデーションとエラーハンドリングを含み、結果オブジェクトを返す。
        """
        if width <= 0 or height <= 0:
            return PreviewResult(
                image=None,
                location=None,
                message="画像サイズ(幅・高さ)は正の整数を指定してください。",
                success=False,
            )

        if not (1 <= zoom <= 19):
            return PreviewResult(
                image=None,
                location=None,
                message="ズームレベルは 1 〜 19 の範囲で指定してください。",
                success=False,
            )

        if not image_path:
            return PreviewResult(
                image=None,
                location=None,
                message="プレビュー対象の画像が選択されていません。",
                success=False,
            )

        if not image_path.exists() or not image_path.is_file():
            return PreviewResult(
                image=None,
                location=None,
                message="指定された画像ファイルが存在しません。",
                success=False,
            )

        loc = extract_gps_location(image_path)
        if not loc:
            return PreviewResult(
                image=None,
                location=None,
                message="選択された写真にGPS情報が含まれていません。",
                success=False,
            )

        lat, lon = loc
        effective_pin_path = pin_path if pin_path else DEFAULT_PIN_PATH

        try:
            map_image = render_map(
                lat=lat,
                lon=lon,
                width=width,
                height=height,
                zoom=zoom,
                pin_path=effective_pin_path,
                tile_url_template=tile_url,
            )
            return PreviewResult(
                image=map_image,
                location=loc,
                message=f"緯度: {lat:.5f}, 経度: {lon:.5f}",
                success=True,
            )
        except Exception as e:  # noqa: BLE001
            return PreviewResult(
                image=None,
                location=loc,
                message=f"プレビュー生成エラー: {e}",
                success=False,
            )
