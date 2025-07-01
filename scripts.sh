#!/bin/bash
# uvを使った開発タスクスクリプト

set -e

# ヘルプ表示
show_help() {
    echo "🤖 imas_music_db 開発スクリプト (uvベース)"
    echo ""
    echo "使用方法: ./scripts.sh <command>"
    echo ""
    echo "利用可能なコマンド:"
    echo "  setup          - 開発環境のセットアップ"
    echo "  install        - 本番用依存関係のインストール"
    echo "  lint           - Pythonコードのリンティング"
    echo "  lint-fix       - Pythonコードのリンティング（自動修正）"
    echo "  format         - Pythonコードのフォーマット"
    echo "  yaml-lint      - YAMLファイルのリンティング"
    echo "  yaml-fix       - YAMLファイルの自動修正"
    echo "  test           - 全てのコード品質チェック"
    echo "  run            - メインスクリプトの実行"
    echo "  pr             - PR作成と自動監視"
    echo "  monitor        - 最新PRの監視"
    echo "  clean          - 一時ファイルの削除"
    echo "  help           - このヘルプを表示"
    echo ""
    echo "例:"
    echo "  ./scripts.sh pr        # PR作成と監視"
    echo "  ./scripts.sh test      # コード品質チェック"
    echo "  ./scripts.sh run       # メインスクリプト実行"
}

# 各コマンドの実装
case "${1:-help}" in
    "setup")
        echo "🔧 開発環境をセットアップ中..."
        uv sync
        echo "✅ セットアップ完了"
        ;;
    "install")
        echo "📦 本番用依存関係をインストール中..."
        uv sync --no-dev
        echo "✅ インストール完了"
        ;;
    "lint")
        echo "🔍 Pythonコードをリンティング中..."
        uv run ruff check --config config/ruff.toml
        ;;
    "lint-fix")
        echo "🔧 Pythonコードをリンティング（自動修正）中..."
        uv run ruff check --fix --config config/ruff.toml
        ;;
    "format")
        echo "💅 Pythonコードをフォーマット中..."
        uv run ruff format --config config/ruff.toml
        ;;
    "yaml-lint")
        echo "📄 YAMLファイルをリンティング中..."
        uv run yamllint -c config/yamllint.yml .
        ;;
    "yaml-fix")
        echo "🔧 YAMLファイルを自動修正中..."
        uv run yamlfix -c config/yamlfix.toml .
        ;;
    "test")
        echo "🧪 全てのコード品質チェックを実行中..."
        echo "--- Pythonリンティング ---"
        uv run ruff check --config config/ruff.toml
        echo "--- YAMLリンティング ---"
        uv run yamllint -c config/yamllint.yml .
        echo "✅ 全てのコード品質チェックが完了しました"
        ;;
    "run")
        echo "🚀 メインスクリプトを実行中..."
        uv run python sheet_to_json.py
        ;;
    "pr")
        echo "🚀 PR作成と監視を開始..."
        uv run python scripts/auto_pr.py
        ;;
    "monitor")
        echo "🔍 最新PRを監視中..."
        uv run python scripts/monitor_pr.py
        ;;
    "clean")
        echo "🧹 一時ファイルを削除中..."
        find . -type f -name "*.pyc" -delete 2>/dev/null || true
        find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
        find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
        echo "✅ クリーンアップ完了"
        ;;
    "help" | "--help" | "-h")
        show_help
        ;;
    *)
        echo "❌ 不明なコマンド: $1"
        echo ""
        show_help
        exit 1
        ;;
esac