# Implementation Plan: HEIC to JPG コンバーター

## Overview

本実装計画は、承認済みの `design.md` と `requirements.md` に基づき、HEIC/HEIF 画像を JPG に変換する Python プログラムを段階的に構築する。実装言語は設計ドキュメントで明示されている **Python 3.10 以上** を使用する。

各タスクは前のタスクの成果物の上に構築され、最終的に CLI として統合される。依存関係の少ない下位レイヤー（データモデル → コンバーター → オーケストレーター → CLI）から順に実装し、各コンポーネントの完了時にプロパティテスト・ユニットテストで検証する。プロパティテストには `hypothesis` を使用する。

## Tasks

- [x] 1. プロジェクト構造と依存関係のセットアップ
  - [x] 1.1 パッケージ構造と依存関係を構築する
    - `heic_to_jpg/` パッケージディレクトリと `tests/` ディレクトリを作成する
    - `pyproject.toml`（または `requirements.txt`）に `pillow-heif`, `Pillow`, 開発用に `pytest`, `hypothesis` を宣言する
    - `heic_to_jpg/__init__.py` を作成し、公開 API（`ConversionConfig`, `run` など）のエクスポート用プレースホルダを用意する
    - `register_heif_opener()` を呼び出す初期化フック（`heic_to_jpg/_heif.py` など）を用意する
    - _Requirements: 全体基盤_

- [x] 2. データモデルと検証の実装
  - [x] 2.1 `ConversionConfig` / `ConversionOptions` を実装する
    - `models.py` に frozen dataclass として `ConversionConfig`（input_path, output_dir, quality, recursive, overwrite, keep_metadata）と `ConversionOptions`（quality, keep_metadata, overwrite）を定義する
    - `quality` が 1〜100 の整数であることを検証し、範囲外なら例外を送出する検証ロジックを実装する
    - _Requirements: 4.1, 4.3_

  - [ ]* 2.2 品質範囲のプロパティテストを作成する
    - **Property 4: 品質範囲 (Quality Range)**
    - **Validates: Requirements 4.2, 4.3**
    - ランダム整数に対し、1〜100 の範囲内なら構築成功、範囲外なら構築失敗となることを hypothesis で検証する

  - [x] 2.3 `ConversionResult` と `ResultStatus` を実装する
    - `ResultStatus` Enum（SUCCESS / SKIPPED / FAILED）と frozen dataclass `ConversionResult`（src, dst, status, error_message）を定義する
    - _Requirements: 1.2, 7.1, 7.4_

  - [x] 2.4 `ConversionSummary` と集計プロパティを実装する
    - `results` から `succeeded` / `skipped` / `failed` の件数を算出するプロパティを実装する
    - `exit_code` プロパティ（failed > 0 なら 1、それ以外は 0）を実装する
    - _Requirements: 8.1, 8.2, 8.3_

  - [ ]* 2.5 終了コード整合のプロパティテストを作成する
    - **Property 8: 終了コード整合 (Exit Code Consistency)**
    - **Validates: Requirements 8.2, 8.3**
    - ランダムな `ConversionResult` 集合に対し `exit_code == (1 if failed > 0 else 0)` が成立することを hypothesis で検証する

  - [ ]* 2.6 `ConversionSummary` の件数集計ユニットテストを作成する
    - succeeded / skipped / failed のカウントを各種混在ケースで検証する
    - _Requirements: 8.1_

- [x] 3. チェックポイント - データモデルのテストが通ることを確認
  - すべてのテストが通ることを確認し、疑問があればユーザーに確認する。

- [x] 4. コンバーターエンジンの実装
  - [x] 4.1 `load_heic()` を実装する
    - `pillow-heif` を利用して HEIC/HEIF を Pillow `Image` として読み込む
    - デコード失敗時は例外を送出する（呼び出し側で FAILED として扱う）
    - _Requirements: 1.1, 1.4_

  - [x] 4.2 `apply_orientation()` を実装する
    - EXIF Orientation タグ（値 1〜8）に従い画像を回転・反転して視覚的に正立させる
    - Orientation 情報がない、または値が 1 の場合は無変換で返す
    - _Requirements: 5.3, 5.4_

  - [ ]* 4.3 Orientation 正立のプロパティテストを作成する
    - **Property 7: Orientation 正立 (Orientation Correctness)**
    - **Validates: Requirements 5.3, 5.4**
    - Orientation 1〜8 を持つ生成画像に対し、正立化後のピクセル配置が基準画像と一致し、出力の Orientation タグが 1 に正規化されることを hypothesis で検証する

  - [x] 4.4 `extract_exif()` を実装する
    - 保持すべき EXIF メタデータをバイト列として抽出し、存在しなければ `None` を返す
    - 正立化後のため Orientation タグを値 1 に正規化する
    - _Requirements: 5.1, 5.2_

  - [x] 4.5 `convert_file()` を実装する
    - デコード → Orientation 補正 → カラーモード正規化（RGB/L 以外は RGB へ変換）→ EXIF 抽出（keep_metadata 時）→ 親ディレクトリ確保 → JPG エンコード（quality 指定）の一連を実装する
    - keep_metadata 有効時は EXIF を埋め込み、無効時は EXIF を含めない
    - EXIF 抽出・埋め込み失敗時も変換を継続し SUCCESS を返す
    - 成功時に SUCCESS の `ConversionResult` を返す
    - _Requirements: 1.1, 1.2, 3.4, 4.1, 5.1, 5.2, 5.5_

  - [ ]* 4.6 入力不変性のプロパティテストを作成する
    - **Property 3: 入力不変性 (Input Immutability)**
    - **Validates: Requirements 1.3**
    - 生成した HEIC 入力に対し、変換前後で入力ファイルのバイト内容が変化しないことを hypothesis で検証する

  - [ ]* 4.7 `convert_file()` の異常系ユニットテストを作成する
    - 破損ファイル・非 HEIC ファイルで例外が送出されること、権限エラーが伝播することを検証する
    - _Requirements: 1.4, 7.1, 7.2_

- [x] 5. チェックポイント - コンバーターのテストが通ることを確認
  - すべてのテストが通ることを確認し、疑問があればユーザーに確認する。

- [x] 6. オーケストレーターの実装
  - [x] 6.1 `resolve_output_path()` を実装する
    - 入力ファイル名の拡張子を小文字 `.jpg` に置換して出力名を決定する
    - output_dir なし → 入力と同じディレクトリ、output_dir あり → 指定先、再帰かつディレクトリ入力 → 相対パス構造を保持
    - _Requirements: 3.1, 3.2, 3.3, 2.4_

  - [ ]* 6.2 拡張子正当性のプロパティテストを作成する
    - **Property 2: 拡張子正当性 (Output Extension Validity)**
    - **Validates: Requirements 3.1**
    - ランダムな入力ファイル名に対し、解決された出力パス（および成功結果の dst）が常に小文字 `.jpg` で終わることを hypothesis で検証する

  - [ ]* 6.3 `resolve_output_path()` のユニットテストを作成する
    - output_dir あり/なし、recursive あり/なしの各組み合わせでのパス生成を検証する
    - _Requirements: 3.1, 3.2, 3.3, 2.4_

  - [x] 6.4 `discover_heic_files()` を実装する
    - 拡張子が HEIC/HEIF に一致（大文字小文字区別なし）するファイルのみ列挙する
    - 再帰有効時はサブディレクトリも対象、無効時は直下のみを対象とする
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 6.5 `discover_heic_files()` のユニットテストを作成する
    - 混在ディレクトリ（HEIC/HEIF/その他拡張子、大文字小文字混在、サブディレクトリ）での列挙結果を検証する
    - _Requirements: 2.1, 2.2, 2.3_

  - [x] 6.6 `run()`（メイン変換ワークフロー）を実装する
    - 単一ファイル/ディレクトリを判別し変換対象を決定する
    - 出力先が既存かつ overwrite 無効なら SKIPPED を記録し既存ファイルを保持する
    - 各ファイルの変換を try/except で囲み、失敗は FAILED として記録し処理を継続する（障害分離）
    - 全結果を `ConversionSummary` に集約し、件数が対象ファイル数と一致することを保証する
    - _Requirements: 2.5, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 9.3_

  - [ ]* 6.7 件数保存のプロパティテストを作成する
    - **Property 1: 件数保存 (Count Preservation)**
    - **Validates: Requirements 2.4, 9.2**
    - ランダムな N 件の HEIC ファイル集合に対し、`run(config).results` の件数が常に N であることを hypothesis で検証する

  - [ ]* 6.8 上書き制御のプロパティテストを作成する
    - **Property 5: 上書き制御 (Overwrite Control)**
    - **Validates: Requirements 6.1**
    - `overwrite=False` かつ出力先既存のとき、結果が常に SKIPPED であり既存ファイルのバイト内容が不変であることを hypothesis で検証する

  - [ ]* 6.9 障害分離のプロパティテストを作成する
    - **Property 6: 障害分離 (Failure Isolation)**
    - **Validates: Requirements 7.3, 7.4**
    - 成功/失敗が混在するファイル集合に対し、失敗が他ファイルの結果に影響せず各結果が独立に生成されることを hypothesis で検証する

- [x] 7. チェックポイント - オーケストレーターのテストが通ることを確認
  - すべてのテストが通ることを確認し、疑問があればユーザーに確認する。

- [x] 8. CLI レイヤーの実装
  - [x] 8.1 `parse_args()` を実装する
    - `argparse` で入力パス、--output、--quality、--recursive、--overwrite、--keep-metadata を解析し `ConversionConfig` を構築する
    - 入力パスが存在しない場合、quality が範囲外/非整数の場合は引数エラーとして扱う
    - overwrite が未指定の場合は無効として扱う
    - _Requirements: 4.2, 4.4, 6.4, 9.1_

  - [x] 8.2 `main()` を実装する
    - `parse_args()` → `run()` を呼び出し、サマリ（成功・スキップ・失敗件数）を標準出力に表示する
    - 失敗ファイルがある場合は各失敗ファイルの識別情報と理由を表示する
    - 対象が 0 件の場合は警告を表示し Exit_Code 0 を返す
    - 引数エラー時は Exit_Code 2、一部失敗時は 1、全成功時は 0 を返す
    - _Requirements: 4.2, 4.4, 8.1, 8.2, 8.3, 8.4, 9.1, 9.2, 9.3_

  - [ ]* 8.3 CLI 引数検証のユニットテストを作成する
    - 存在しない入力パス、範囲外/非整数 quality で Exit_Code 2 となることを検証する
    - _Requirements: 4.2, 4.4, 9.1_

  - [x] 8.4 `__main__.py` を作成しモジュール実行を有効化する
    - `python -m heic_to_jpg ...` で `main()` が起動するよう配線する
    - _Requirements: 8.1_

- [x] 9. 統合とワイヤリング
  - [x] 9.1 公開 API を `__init__.py` に集約する
    - `ConversionConfig`, `ConversionOptions`, `ConversionResult`, `ConversionSummary`, `run` を公開エクスポートとして配線する
    - _Requirements: 全体統合_

  - [ ]* 9.2 統合テストを作成する
    - サンプル HEIC を用いた単一ファイル/ディレクトリ再帰変換の end-to-end 検証、出力ディレクトリ構造の保持検証、subprocess 経由の CLI 実行（引数解析→変換→終了コード）を検証する
    - _Requirements: 1.1, 2.2, 2.4, 8.1, 8.2, 8.3_

- [x] 10. 最終チェックポイント - 全テストが通ることを確認
  - すべてのテストが通ることを確認し、疑問があればユーザーに確認する。

## Notes

- `*` が付いたサブタスクは任意（テスト系）であり、高速な MVP のためにスキップ可能。コア実装タスクはスキップ不可。
- 各タスクはトレーサビリティのため具体的な requirements 番号を参照している。
- プロパティテストは設計の Correctness Properties（P1〜P8）を検証し、各テストはプロパティ番号と対応する要件番号を明記している。
- ユニットテストは具体例・エッジケースを検証し、プロパティテストと相補的に機能する。
- チェックポイントで段階的に検証を行う。

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["2.1", "2.3", "2.4"] },
    { "id": 2, "tasks": ["2.2", "2.5", "2.6", "4.1", "4.2", "4.4"] },
    { "id": 3, "tasks": ["4.3", "4.5", "6.1", "6.4"] },
    { "id": 4, "tasks": ["4.6", "4.7", "6.2", "6.3", "6.5", "6.6"] },
    { "id": 5, "tasks": ["6.7", "6.8", "6.9", "8.1"] },
    { "id": 6, "tasks": ["8.2", "8.4"] },
    { "id": 7, "tasks": ["8.3", "9.1"] },
    { "id": 8, "tasks": ["9.2"] }
  ]
}
```
