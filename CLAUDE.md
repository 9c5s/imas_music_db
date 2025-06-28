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

### 開発タスク（uvベース）

#### ワンコマンドでPR作成・監視
```bash
# PR自動作成と監視（推奨）
./scripts.sh pr

# または直接実行
uv run python auto_pr.py
```

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
```

#### その他の開発コマンド
```bash
# ヘルプ表示
./scripts.sh help

# 開発環境セットアップ
./scripts.sh setup

# メインスクリプト実行
./scripts.sh run

# 最新PRの監視
./scripts.sh monitor

# 一時ファイル削除
./scripts.sh clean
```

### 認証設定
```bash
# Google Cloud認証（初回のみ）
gcloud auth application-default login

# GitHub CLI認証（初回のみ）
gh auth login
```

## システムアーキテクチャ

### メインコンポーネント

1. **GoogleApiService** (`sheet_to_json.py:113-140`)
   - Google Drive API・Sheets APIの認証とサービス初期化を管理
   - スコープ: `drive`, `spreadsheets`

2. **SheetCopier** (`sheet_to_json.py`)
   - スプレッドシートの一時コピー作成・削除を管理
   - コンテキストマネージャーとして実装（自動クリーンアップ）

3. **SheetProcessor** (`sheet_to_json.py:142-`)
   - スプレッドシートの生データを設定に基づいて処理・整形
   - IDの降順ソート、配列フィールドの統合処理

### データフロー

1. 指定されたスプレッドシート（`CONFIG["source_spreadsheet_id"]`）を一時的にドライブにコピー
2. 対象シート（`CONFIG["target_sheet_name"]`）からデータを読み取り
3. 列マッピング設定（`CONFIG["column_mapping"]`）に従ってJSONオブジェクトに変換
4. IDフィールドの降順でソート
5. JSONファイル（`CONFIG["output_filename"]`）として出力
6. 一時コピーファイルを削除

### 設定

メインの設定は `CONFIG` 辞書（`sheet_to_json.py:55-89`）で管理：
- `source_spreadsheet_id`: コピー元スプレッドシートID
- `target_sheet_name`: 読み取り対象シート名
- `column_mapping`: 列文字とJSONキーのマッピング
- `ignore_values`: 空文字として扱う値のセット

## GitHub Actions

### 自動データ更新ワークフロー

`.github/workflows/update_json_data.yml`で定義された自動化処理：

1. **スケジュール実行**: 毎日日本時間9:00（UTC 0:00）
2. **手動実行**: GitHub UIから実行可能
3. **ワークフロー**:
   - masterブランチからスクリプトを取得
   - Workload Identity連携でGoogle Cloud認証
   - Python環境セットアップ・依存関係インストール
   - `sheet_to_json.py` 実行
   - PrettierでJSONフォーマット
   - dataブランチに変更をコミット・プッシュ
   - 新しいリリースを作成・JSONファイルを添付

### コード品質チェックワークフロー

プルリクエスト作成時に以下のワークフローが自動実行されます：

**`code_quality.yml`**: 統合コード品質チェック（PRコメント付き）
- PythonファイルのRuffリンティング・フォーマットチェック
- YAMLファイルのyamllintチェック
- チェック結果をPRにコメントとして投稿
- 統計情報と修正方法の表示
- GitHub Actions UI上でのエラー表示

### ブランチ構成・開発フロー

このリポジトリは**GitHub Flow**を採用しています：

- `master`: メインブランチ（スクリプト格納・本番環境）
- `data`: データ配信用ブランチ（JSONファイル格納）
- フィーチャーブランチ: `feature/機能名` または `fix/修正内容`

**開発フロー**：
1. `master`ブランチから新しいフィーチャーブランチを作成
2. フィーチャーブランチで開発・コミット
3. プルリクエストを作成して`master`にマージ
4. マージ後、フィーチャーブランチを削除

## Google Cloud連携

- Workload Identity連携による認証
- 必要なシークレット: `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_SERVICE_ACCOUNT`
- APIスコープ: Google Drive API, Google Sheets API

## データ配信

生成されたJSONファイルは以下のURLで配信：
```
https://raw.githubusercontent.com/9c5s/imas_music_db/data/imas_music_db.json
```

## コーディング規約

- コメントは日本語で記述する
- コメントは「だ・である調」で記述する
- コメントに全角記号を使用しない
- エラーハンドリングを適切に行う
- セキュリティを考慮したコーディングを行う
- コードの可読性を重視する
- 関数やメソッドは単一責任の原則に従う
- 命名規則は一貫性を持たせる
- コードの再利用性を考慮する
- ドキュメントを適切に記述する
- パフォーマンスを意識する