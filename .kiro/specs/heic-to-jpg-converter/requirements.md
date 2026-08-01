# Requirements Document

## Introduction

本機能は、iOS デバイスで撮影された HEIC/HEIF 形式の画像を JPG 形式に変換する Python プログラムである。単一ファイルおよびディレクトリ単位での一括変換をサポートし、コマンドラインインターフェース (CLI) から操作する。EXIF メタデータおよび画像の向き (Orientation) を保持し、大量ファイルを堅牢に処理することを目的とする。

本要件ドキュメントは承認済みの設計ドキュメント (`design.md`) から導出され、設計上の技術的判断（コンポーネント構成、データモデル、アルゴリズム、正当性プロパティ）と整合するように記述されている。

## Glossary

- **Converter_System**: HEIC を JPG に変換するプログラム全体。
- **CLI**: コマンドライン引数を解析し、変換処理を起動し、結果を標準出力へ表示するコンポーネント。
- **Orchestrator**: 入力パスを解決し、変換対象ファイルを列挙し、各変換ジョブを実行して結果を集約するコンポーネント。
- **Converter_Engine**: 単一の HEIC ファイルを JPG に変換するコアロジックを担うコンポーネント。
- **HEIC_File**: HEIC/HEIF 形式の入力画像ファイル。
- **JPG_File**: 変換後に出力される JPEG 形式の画像ファイル。
- **EXIF_Metadata**: 撮影日時、GPS、Orientation などの画像メタデータ。
- **Orientation**: EXIF に含まれる画像の向きを示すタグ (値 1〜8)。
- **ConversionConfig**: 入力パス、出力先、品質、再帰、上書き、メタデータ保持を保持する設定オブジェクト。
- **ConversionResult**: 単一ファイルの変換結果 (SUCCESS / SKIPPED / FAILED)。
- **ConversionSummary**: 全変換結果の集約とサマリ (成功・スキップ・失敗件数、終了コード)。
- **Exit_Code**: プロセス終了コード (0=全成功, 1=一部失敗, 2=引数エラー)。
- **Quality**: JPG エンコード品質を表す 1〜100 の整数。

## Requirements

### Requirement 1: 単一ファイルの変換

**User Story:** iOS ユーザーとして、1つの HEIC ファイルを JPG に変換したい。それにより、HEIC 非対応の環境でも画像を閲覧・共有できる。

#### Acceptance Criteria

1. WHEN 入力パスとして単一の HEIC_File が指定される, THE Converter_System SHALL 当該 HEIC_File をデコードし、拡張子 `.jpg` を持つ有効な JPG_File を1件生成する
2. WHEN 単一ファイルの変換が成功する, THE Converter_Engine SHALL ステータス SUCCESS を持ち、生成された JPG_File の出力先パスを含む ConversionResult を返す
3. THE Converter_Engine SHALL 変換処理の前後で入力 HEIC_File のバイト内容を変更しない状態で保持する
4. IF 指定された単一の HEIC_File のデコードに失敗する, THEN THE Converter_System SHALL 当該ファイルをステータス FAILED として記録し、失敗理由を示すエラーメッセージを保持し、JPG_File を生成しない

### Requirement 2: ディレクトリ一括変換

**User Story:** iOS ユーザーとして、ディレクトリ内の複数の HEIC ファイルを一括で JPG に変換したい。それにより、大量の写真をまとめて処理できる。

#### Acceptance Criteria

1. WHEN 入力パスとしてディレクトリが指定される, THE Orchestrator SHALL 当該ディレクトリ配下のファイルのうち拡張子が HEIC または HEIF に一致する（大文字小文字を区別しない）ファイルのみを HEIC_File として列挙する
2. WHERE 再帰オプションが有効である, THE Orchestrator SHALL 入力ディレクトリのすべてのサブディレクトリ配下の HEIC_File も列挙対象に含める
3. WHERE 再帰オプションが無効である, THE Orchestrator SHALL 入力ディレクトリ直下の HEIC_File のみを列挙対象とし、サブディレクトリ配下の HEIC_File を列挙対象から除外する
4. WHERE 再帰オプションが有効かつ入力がディレクトリである, THE Orchestrator SHALL 入力ディレクトリからの相対パス構造を出力先ディレクトリに反映する
5. WHEN 変換対象ファイル集合のすべてのファイルの処理が完了する, THE Orchestrator SHALL ConversionSummary に含まれる ConversionResult の件数を変換対象ファイル数と等しくする

### Requirement 3: 出力パスの決定

**User Story:** ユーザーとして、変換後の JPG がどこに出力されるかを制御したい。それにより、元ファイルと出力を整理して管理できる。

#### Acceptance Criteria

1. THE Orchestrator SHALL 出力 JPG_File のファイル名を、対応する入力 HEIC_File のファイル名の拡張子を小文字の `.jpg` に置換した名前にする
2. WHERE 出力先ディレクトリが指定されない, THE Orchestrator SHALL 入力 HEIC_File と同じディレクトリに JPG_File を出力する
3. WHERE 出力先ディレクトリが指定される, THE Orchestrator SHALL 指定された出力先ディレクトリに JPG_File を出力する
4. WHEN JPG_File を書き込む際に出力先の親ディレクトリが存在しない, THE Orchestrator SHALL 当該親ディレクトリを作成してから JPG_File を書き込む

### Requirement 4: 品質指定

**User Story:** ユーザーとして、JPG の圧縮品質を指定したい。それにより、ファイルサイズと画質のバランスを調整できる。

#### Acceptance Criteria

1. WHEN JPG_File のエンコードを実行する, THE Converter_Engine SHALL 1 以上 100 以下の整数である Quality を JPEG エンコード品質として適用する
2. IF Quality が 1 未満または 100 を超える整数である, THEN THE CLI SHALL 引数エラーを示すエラーメッセージを表示し、変換処理を実行せず Exit_Code 2 で終了する
3. WHERE Quality が 1 以上 100 以下の整数である, THE Converter_System SHALL ConversionConfig の構築を成功させる
4. IF Quality が整数として解釈できない値である, THEN THE CLI SHALL 引数エラーを示すエラーメッセージを表示し、変換処理を実行せず Exit_Code 2 で終了する

### Requirement 5: EXIF メタデータと Orientation の保持

**User Story:** iOS ユーザーとして、撮影日時などのメタデータと正しい画像の向きを保持したい。それにより、変換後も情報と見た目を維持できる。

#### Acceptance Criteria

1. WHERE メタデータ保持オプションが有効である, THE Converter_Engine SHALL 入力 HEIC_File から抽出できた EXIF_Metadata を出力 JPG_File に埋め込む
2. WHERE メタデータ保持オプションが無効である, THE Converter_Engine SHALL 出力 JPG_File に EXIF_Metadata を一切含めない
3. THE Converter_Engine SHALL メタデータ保持オプションの有無にかかわらず、EXIF Orientation に従って画像を視覚的に正立させ、出力 JPG_File の Orientation タグを値 1 に設定した状態で出力する
4. IF 入力画像に Orientation 情報が存在しない、または Orientation の値が 1 である, THEN THE Converter_Engine SHALL 回転・反転を適用せずに画像を出力する
5. IF EXIF_Metadata の抽出または埋め込みに失敗する, THEN THE Converter_Engine SHALL 変換を継続し、JPG_File を出力し、結果をステータス SUCCESS として記録する

### Requirement 6: 上書き制御

**User Story:** ユーザーとして、既存の JPG を上書きするかどうかを制御したい。それにより、意図しないファイル消失を防げる。

#### Acceptance Criteria

1. IF 出力先に JPG_File が既存し、かつ上書きオプションが無効である, THEN THE Orchestrator SHALL 当該ファイルの ConversionResult をステータス SKIPPED として記録する
2. IF 出力先に JPG_File が既存し、かつ上書きオプションが無効である, THEN THE Orchestrator SHALL 既存 JPG_File のバイト内容を変更せず保持する
3. WHERE 上書きオプションが有効である, THE Orchestrator SHALL 既存の同名 JPG_File のバイト内容を変換結果で置き換える
4. WHERE 上書きオプションが指定されない, THE Converter_System SHALL 上書きオプションを無効として扱う

### Requirement 7: エラー処理と障害分離

**User Story:** ユーザーとして、一部のファイルが変換に失敗しても残りの処理を継続してほしい。それにより、大量処理中の中断を避けられる。

#### Acceptance Criteria

1. IF ある HEIC_File のデコードに失敗する, THEN THE Converter_System SHALL 当該ファイルの ConversionResult をステータス FAILED として記録し、失敗理由を示すエラーメッセージを保持し、不完全な JPG_File を残さない
2. IF JPG_File の書き込み時に書き込み不可または権限エラーが発生する, THEN THE Converter_System SHALL 当該ファイルの ConversionResult をステータス FAILED として記録し、失敗理由を示すエラーメッセージを保持する
3. WHEN あるファイルの変換が失敗する, THE Orchestrator SHALL 失敗を変換対象集合全体へ伝播させず、残りのすべての HEIC_File の処理を継続する
4. THE Orchestrator SHALL 各 HEIC_File に対し、他ファイルの成功・失敗いずれにも依存しない独立した ConversionResult を1件生成する
5. WHEN 変換対象集合内に失敗が含まれる状態で全処理が完了する, THE Orchestrator SHALL ConversionSummary に含まれる ConversionResult の総数を変換対象ファイル数と等しくする
6. IF 変換に失敗した HEIC_File が存在する, THEN THE Converter_System SHALL 各失敗ファイルの識別情報と失敗理由を示すエラーメッセージをサマリに含める

### Requirement 8: サマリレポートと終了コード

**User Story:** ユーザーとして、変換結果の概要と終了ステータスを知りたい。それにより、成否をスクリプトやパイプラインで判定できる。

#### Acceptance Criteria

1. WHEN 全変換ジョブが完了する, THE CLI SHALL 成功件数・スキップ件数・失敗件数の3つの件数を含むサマリを標準出力に表示する
2. IF ConversionSummary の失敗件数が 0 を超える, THEN THE Converter_System SHALL Exit_Code 1 を返す
3. WHERE ConversionSummary の失敗件数が 0 である, THE Converter_System SHALL Exit_Code 0 を返す
4. IF ConversionSummary の失敗件数が 0 を超える, THEN THE CLI SHALL 各失敗ファイルの識別情報と失敗理由を示すエラーメッセージを標準出力に表示する

### Requirement 9: 入力検証

**User Story:** ユーザーとして、不正な入力に対して明確なエラーを受け取りたい。それにより、問題を素早く修正できる。

#### Acceptance Criteria

1. IF 入力パスが存在しない, THEN THE CLI SHALL 指定された入力パスが存在しない旨を示すエラーメッセージを表示し、変換処理を一切実行せずに Exit_Code 2 で終了する
2. WHEN 変換対象の HEIC_File の探索が完了し対象が1件も見つからない, THE Converter_System SHALL 変換対象が見つからない旨を示す警告メッセージを表示する
3. WHEN 変換対象の HEIC_File が1件も見つからない状態で処理が完了する, THE Converter_System SHALL 成功・スキップ・失敗の件数がいずれも 0 である ConversionSummary を返し Exit_Code 0 を返す
