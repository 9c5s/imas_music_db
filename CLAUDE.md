# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

このプロジェクトは、Googleスプレッドシートからアイマス楽曲データベースをJSONファイルとして自動生成・配信するシステムです。

## 開発コマンド

### セットアップ
```bash
# 依存関係のインストール（本番用）
uv sync --no-dev

# 開発依存関係を含むインストール
uv sync
```

### メインスクリプトの実行
```bash
# スプレッドシートからJSONを生成
python sheet_to_json.py

# または uvで実行
uv run sheet_to_json.py
```

### コード品質チェック

#### Pythonコード
```bash
# Ruffによるリンティング
uv run ruff check

# Ruffによる自動修正
uv run ruff check --fix

# フォーマッティング
uv run ruff format

# Pyrightによる型チェック
uv run pyright
```

#### YAMLファイル（厳格ルール）
```bash
# yamllintによるリンティング（厳格設定）
uv run yamllint .

# yamlfixによる自動フォーマット（厳格設定）
uv run yamlfix .
```

**厳格ルール詳細:**
- 行長制限: 80文字
- インデント: 一貫したスペース数
- ドキュメント開始: `---` 必須
- 真偽値: `true`/`false`のみ（GitHub Actions `on` は例外）
- スペーシング・フォーマット: 厳格に統一

#### シェルスクリプト（厳格ルール）
```bash
# ShellCheckによるリンティング（全ルール有効）
uv run shellcheck ./*.sh

# shfmtによるフォーマット（POSIX準拠）
uv run shfmt -i 2 -p -s -ci -sr -fn -w ./*.sh

# フォーマットチェック（差分表示）
uv run shfmt -i 2 -p -s -ci -sr -fn -d ./*.sh
```

**厳格ルール詳細:**
- **ShellCheck**: 全オプションチェック有効（`enable=all`）
- **構文解析**: POSIX準拠による最高の互換性
- **インデント**: 2スペース統一
- **フォーマット**: 一貫した波括弧・演算子配置
- **行長制限**: 80文字による横スクロール回避
- **セキュリティ**: 変数クォート・終了コード検証

### 開発タスク（uvベース）

#### コード品質チェック
```bash
# 全てのコード品質チェック
./scripts.sh test

# Pythonリンティング
./scripts.sh lint

# Python自動修正
./scripts.sh lint-fix

# Pythonフォーマット
./scripts.sh format

# YAMLリンティング
./scripts.sh yaml-lint

# YAML自動修正
./scripts.sh yaml-fix

# シェルスクリプトリンティング
./scripts.sh shell-lint

# シェルスクリプトフォーマット
./scripts.sh shell-format

# シェルスクリプト統合チェック
./scripts.sh shell-check

# Python型チェック
./scripts.sh type-check
```

#### その他の開発コマンド
```bash
# ヘルプ表示
./scripts.sh help

# 開発環境セットアップ
./scripts.sh setup

# メインスクリプト実行
./scripts.sh run

# 一時ファイル削除
./scripts.sh clean
```

### 認証設定
```bash
# Google Cloud認証（初回のみ）
gcloud auth application-default login

# Gitフック自動化セットアップ（推奨）
uv run lefthook install
```

## プロジェクト構造

```
imas_music_db/
├── .github/workflows/     # GitHub Actions
│   ├── update_json_data.yml # データ更新自動化
│   └── claude.yml         # Claude Code連携
├── .editorconfig          # shfmtフォーマッター設定
├── .shellcheckrc          # ShellCheckリンター設定（自動検出）
├── .yamllint.yml          # YAMLリンター設定（自動検出）
├── sheet_to_json.py       # メインスクリプト
├── sheet_config.yml       # スプレッドシート設定
├── scripts.sh             # 開発タスクランナー
├── lefthook.yml           # Gitフック自動化設定
├── pyproject.toml         # プロジェクト設定・品質チェック設定
└── README.md
```

### 設定ファイルの管理

- **pyproject.toml**: Ruff・Pyright・yamlfixの設定を統合（自動検出）
- **ルートの設定ファイル**: yamllint・ShellCheck・shfmt用（各ツールが自動検出）
- **統一された実行方法**: `scripts.sh`経由で実行（設定ファイルパス指定不要）
- **GitHub Actions連携**: CI/CDパイプラインでも同じ設定を使用
- **4言語統合**: Python・YAML・シェルスクリプト・型チェックの統一的品質管理
- **Gitフック自動化**: lefthook.ymlによるコミット前品質チェック

## システムアーキテクチャ

### メインコンポーネント

1. **GoogleApiService** (`sheet_to_json.py`)
   - Google Sheets APIの認証とサービス初期化を管理
   - スコープ: `spreadsheets.readonly`

2. **SheetProcessor** (`sheet_to_json.py`)
   - スプレッドシートの生データを設定に基づいて処理・整形
   - IDの降順ソート、配列フィールドの統合処理

### データフロー

1. YAML設定ファイル（`sheet_config.yml`）から設定を読み込み
2. 指定されたスプレッドシートから直接データを読み取り
3. 列マッピング設定に従ってJSONオブジェクトに変換
4. IDフィールドの降順でソート
5. JSONファイルとして出力

### 設定

メインの設定は `sheet_config.yml` で管理される外部設定ファイル：
- **spreadsheet**: スプレッドシート基本設定
  - `source_id`: コピー元スプレッドシートID
  - `target_sheet`: 読み取り対象シート名
- **output**: 出力設定
  - `filename`: 出力JSONファイル名
- **data_structure**: データ構造設定
  - `data_start_row`: データ開始行番号
  - `end_check_columns`: データ終端判定列範囲
- **column_mapping**: 列文字とJSONキーのマッピング（配列処理含む）
- **ignore_values**: 空文字として扱う値のセット

## GitHub Actions

### 自動データ更新ワークフロー

`.github/workflows/update_json_data.yml`で定義された自動化処理：

1. **スケジュール実行**: 毎日日本時間9:00（UTC 0:00）
2. **手動実行**: GitHub UIから実行可能
3. **ワークフロー**:
   - mainブランチからスクリプトを取得
   - Workload Identity連携でGoogle Cloud認証
   - Python環境セットアップ・依存関係インストール
   - `sheet_to_json.py` 実行
   - PrettierでJSONフォーマット
   - dataブランチに変更をコミット・プッシュ
   - 新しいリリースを作成・JSONファイルを添付

### Claude Code連携ワークフロー

**`claude.yml`**: Claude Code連携ワークフロー
- PRコメント・イシュー・レビューでの@claudeメンション対応
- Claude Code OAuth連携による自動応答
- コードレビュー・課題解決の自動化

### Gitフック自動化

**lefthook.yml**による自動品質チェック：

**pre-commit**: コミット前の並列品質チェック
- **Python**: Ruffリンティング・フォーマット（自動修正）
- **YAML**: yamllintチェック・yamlfix自動修正
- **Shell**: ShellCheckリンティング・shfmtフォーマット（自動修正）
- 修正されたファイルの自動ステージング

**pre-push**: プッシュ前の包括的品質チェック
- 全ファイル対象の品質チェック
- Ruff・yamllint・ShellCheckによる最終検証

**セットアップ**:
```bash
# lefthookのインストールと有効化
uv run lefthook install
```

### ブランチ構成・開発フロー

このリポジトリは**GitHub Flow**を採用しています：

- `main`: メインブランチ（スクリプト格納・本番環境）
- `data`: データ配信用ブランチ（JSONファイル格納）
- フィーチャーブランチ: `feature/機能名` または `fix/修正内容`

**開発フロー**：
1. `main`ブランチから新しいフィーチャーブランチを作成
2. フィーチャーブランチで開発・コミット
3. プルリクエストを作成して`main`にマージ
4. マージ後、フィーチャーブランチを削除

## Google Cloud連携

- Workload Identity連携による認証
- 必要なシークレット: `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`
- APIスコープ: Google Sheets API（読み取り専用）

## データ配信

生成されたJSONファイルは以下のURLで配信：
```
https://raw.githubusercontent.com/9c5s/imas_music_db/data/imas_music_db.json
```
