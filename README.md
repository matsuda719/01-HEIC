# heic-to-jpg

HEIC/HEIF 画像を JPG に変換する Python プログラムです。EXIF メタデータの保持と画像の向き (Orientation) 補正に対応し、単一ファイル・ディレクトリ一括変換を CLI から実行できます。

## 動作要件

- Python 3.10 以上
- ランタイム依存: `pillow-heif`, `Pillow`
- 開発/テスト: `pytest`, `hypothesis`

## インストール

```bash
pip install -e ".[dev]"
```

## 使い方

基本形は次のとおりです。入力にはファイルまたはディレクトリを指定します。

```bash
python -m heic_to_jpg <入力パス> [オプション]
```

### コマンドラインオプション

| オプション | 説明 | デフォルト |
|---|---|---|
| `input_path` (必須) | 変換対象の HEIC/HEIF ファイル、またはそれらを含むディレクトリ | — |
| `--output <dir>` | 出力先ディレクトリ。省略時は入力ファイルと同じ場所に出力 | 入力と同じ場所 |
| `--quality <1-100>` | JPEG エンコード品質 (整数)。範囲外/非整数はエラー (終了コード 2) | `90` |
| `--recursive` | 入力がディレクトリのとき、サブディレクトリも再帰的に探索。出力先には相対パス構造を保持 | 無効 (直下のみ) |
| `--overwrite` | 出力先に同名 JPG が既存の場合に上書き。未指定なら既存ファイルはスキップ | 無効 (スキップ) |
| `--keep-metadata` | EXIF メタデータ (撮影日時・機種など) を出力 JPG に保持 | 無効 |

> 向き (Orientation) の補正は常に行われます。画像は視覚的に正立した状態で出力され、出力の Orientation タグは 1 に正規化されます (メタデータ保持の有無に関わらず)。

### 使用例

```bash
# 単一ファイルを同じ場所に変換 (IMG_0001.jpg を生成)
python -m heic_to_jpg IMG_0001.HEIC

# ディレクトリ内の HEIC を出力先にまとめて変換 (品質 90)
python -m heic_to_jpg ./photos --output ./out --quality 90

# サブディレクトリも含めて再帰変換 (ディレクトリ構造を保持)
python -m heic_to_jpg ./photos --output ./out --recursive

# EXIF メタデータを保持して変換
python -m heic_to_jpg ./photos --output ./out --keep-metadata

# 既存の JPG を上書き
python -m heic_to_jpg ./photos --output ./out --overwrite
```

## GUI で使う

コマンドラインの代わりに、ファイル選択ダイアログ付きの GUI からも変換できます (追加依存なし、Python 標準の tkinter を使用)。

```bash
python -m heic_to_jpg.gui
```

インストール済み (`pip install -e .`) の場合は、次のコマンドでも起動できます。

```bash
heic-to-jpg-gui
```

GUI では次の操作ができます。

- **ファイルを追加** — HEIC/HEIF ファイルを複数選択
- **フォルダを追加** — ディレクトリを丸ごと対象に指定
- **出力先** — 出力フォルダを選択 (空欄なら入力と同じ場所)
- **品質 (1-100)** — JPEG 品質を指定
- **チェックボックス** — 再帰変換 / 上書き / EXIF メタデータ保持
- **変換する** — バックグラウンドで変換を実行 (ウィンドウは固まりません)。結果 (成功・スキップ・失敗件数、失敗理由) が下部に表示されます

> 変換ロジックは CLI と同一です。GUI は選択したファイルごとに内部の変換処理を呼び出し、結果をまとめて表示します。

## 出力 (CLI)

処理が完了すると、件数のサマリが標準出力に表示されます。

```
succeeded: 2, skipped: 0, failed: 0
```

失敗したファイルがある場合は、その識別情報と理由も表示されます。

```
succeeded: 3, skipped: 0, failed: 1
failures:
  ./photos/broken.HEIC: <エラー理由>
```

## 終了コード (CLI)

| コード | 意味 |
|---|---|
| `0` | すべて成功 (変換対象が 0 件の場合も 0) |
| `1` | 一部のファイルが失敗 |
| `2` | 引数エラー (入力パスが存在しない、品質が範囲外/非整数など) |

## プログラムからの利用

CLI を介さず、Python から直接呼び出すこともできます。

```python
from pathlib import Path
from heic_to_jpg import ConversionConfig, run

config = ConversionConfig(
    input_path=Path("./photos"),
    output_dir=Path("./out"),
    quality=90,
    recursive=True,
    overwrite=False,
    keep_metadata=True,
)
summary = run(config)
print(f"成功: {summary.succeeded}, スキップ: {summary.skipped}, 失敗: {summary.failed}")
exit(summary.exit_code)
```

## 動作メモ

- 入力ファイルは変換によって変更されません (バイト内容は不変)。
- ディレクトリ入力時は、拡張子が `.heic` / `.heif` のファイル (大文字小文字を区別しない) のみが対象になります。
- 変換対象が 1 件も見つからない場合は警告を表示し、終了コード 0 で終了します。
- 一部のファイルが失敗しても処理は中断されず、残りのファイルの変換は継続されます。

## 開発

設計とタスク計画は `.kiro/specs/heic-to-jpg-converter/` を参照してください。
