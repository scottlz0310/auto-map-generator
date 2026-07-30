# CHANGELOG

## [0.1.0] - 2026-07-30

### Added
- **Tkinter GUI**: 写真選択・設定調整・進捗表示・手動中断が可能な非開発者向けGUIアプリケーション (`app/gui.py`) の実装
- **設定の永続化**: GUI設定値 (入力/出力フォルダ、画像サイズ、ズームレベル、ピン画像、タイルURL) の `config.json` への自動保存・復元機能
- **自動環境構築＆サイレント起動**: `uv` 自動導入と依存関係の全自動同期を行う `setup_and_run.bat`, `run.bat` およびコンソール非表示起動スクリプト `run.vbs`
- **コアモジュールのモジュール化**: `app/core.py` へのEXIF解析・地図画像合成・キャッシュ制御処理の分離
- **CLI機能の改善**: `main.py` のモジュール化・リファクタリング
- **品質・テスト基盤**: `pytest` + `pytest-cov` による包括的な単体テスト (カバレッジ94%), `ruff` フォーマット/リンター, `basedpyright` 型チェック全適用
- **CI / Release ワークフロー**: GitHub Actions (`.github/workflows/ci.yml`, `release.yml`) および `.pre-commit-config.yaml` の追加

### Fixed
- **CIビルド修正**: `pyproject.toml` の `dev` 依存関係に `ruff` および `basedpyright` を追加し、CIでのツール未検出エラーを解消
- **CI GUIテスト修正**: Ubuntu CI 上での Tkinter ディスプレイ不在による `TclError` を防ぐため `xvfb-run` を導入し、テストにフォールバック処理を追加
- **pre-commitフック修正**: `.pre-commit-config.yaml` の basedpyright リポジトリ URL を `basedpyright-pre-commit-mirror` に修正
- **Git管理対象の整理**: `usage.txt` を git 追跡対象外にし、`.gitignore` に追加



