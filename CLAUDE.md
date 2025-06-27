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
```bash
# Ruffによるリンティング
uv run ruff check

# Ruffによる自動修正
uv run ruff check --fix

# フォーマッティング
uv run ruff format
```

### 認証設定
```bash
# Google Cloud認証（初回のみ）
gcloud auth application-default login
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