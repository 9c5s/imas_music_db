# Makefile for imas_music_db project

.PHONY: help setup install lint format yaml-lint yaml-fix test pr monitor clean

# デフォルトターゲット（help表示）
help:
	@echo "利用可能なコマンド:"
	@echo "  setup          - 開発環境のセットアップ（依存関係インストール）"
	@echo "  install        - 本番用依存関係のインストール"
	@echo "  lint           - Pythonコードのリンティング"
	@echo "  format         - Pythonコードのフォーマット"
	@echo "  yaml-lint      - YAMLファイルのリンティング"
	@echo "  yaml-fix       - YAMLファイルの自動修正"
	@echo "  test           - 全てのコード品質チェックを実行"
	@echo "  pr             - PR作成と自動監視"
	@echo "  monitor        - 最新PRの監視"
	@echo "  run            - メインスクリプトの実行"
	@echo "  clean          - 一時ファイルの削除"

# 開発環境セットアップ
setup:
	@echo "🔧 開発環境をセットアップ中..."
	uv sync
	@echo "✅ セットアップ完了"

# 本番用インストール
install:
	@echo "📦 本番用依存関係をインストール中..."
	uv sync --no-dev
	@echo "✅ インストール完了"

# Pythonコードリンティング
lint:
	@echo "🔍 Pythonコードをリンティング中..."
	uv run ruff check

# Pythonコードフォーマット
format:
	@echo "💅 Pythonコードをフォーマット中..."
	uv run ruff format

# Pythonコードリンティング（自動修正付き）
lint-fix:
	@echo "🔧 Pythonコードをリンティング（自動修正）中..."
	uv run ruff check --fix

# YAMLリンティング
yaml-lint:
	@echo "📄 YAMLファイルをリンティング中..."
	uv run yamllint .

# YAML自動修正
yaml-fix:
	@echo "🔧 YAMLファイルを自動修正中..."
	uv run yamlfix .

# 全てのコード品質チェック
test: lint yaml-lint
	@echo "✅ 全てのコード品質チェックが完了しました"

# メインスクリプト実行
run:
	@echo "🚀 メインスクリプトを実行中..."
	uv run python sheet_to_json.py

# PR作成と監視
pr:
	@echo "🚀 PR作成と監視を開始..."
	uv run python auto_pr.py

# 最新PRの監視のみ
monitor:
	@echo "🔍 最新PRを監視中..."
	uv run python monitor_pr.py

# 特定PR番号の監視
monitor-pr:
	@read -p "監視するPR番号を入力してください: " pr_number; \
	echo "🔍 PR#$$pr_number を監視中..."; \
	uv run python monitor_pr.py $$pr_number

# 一時ファイルの削除
clean:
	@echo "🧹 一時ファイルを削除中..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ クリーンアップ完了"

# GitHub認証確認
auth-check:
	@echo "🔐 GitHub認証を確認中..."
	@gh auth status || (echo "❌ GitHub認証が必要です。'gh auth login' を実行してください" && exit 1)
	@echo "✅ GitHub認証OK"

# 完全セットアップ（初回用）
init: setup auth-check
	@echo "🎉 初期セットアップが完了しました！"
	@echo ""
	@echo "利用可能なコマンド:"
	@echo "  make pr        - PR作成と監視"
	@echo "  make test      - コード品質チェック"
	@echo "  make run       - メインスクリプト実行"