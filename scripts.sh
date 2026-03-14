#!/bin/bash
# uvを使った開発タスクスクリプト

set -e

# ヘルプ表示
show_help()
{
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
  echo "  shell-lint     - シェルスクリプトのリンティング"
  echo "  shell-format   - シェルスクリプトのフォーマット"
  echo "  shell-check    - シェルスクリプトの品質チェック（リント+フォーマット）"
  echo "  type-check     - Pyrightによる型チェック"
  echo "  test           - 全てのコード品質チェック（型チェック含む）"
  echo "  run            - メインスクリプトの実行"
  echo "  clean          - 一時ファイルの削除"
  echo "  help           - このヘルプを表示"
  echo ""
  echo "例:"
  echo "  ./scripts.sh test      # コード品質チェック"
  echo "  ./scripts.sh shell-check  # シェルスクリプト品質チェック"
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
    uv run ruff check
    ;;
  "lint-fix")
    echo "🔧 Pythonコードをリンティング（自動修正）中..."
    uv run ruff check --fix
    ;;
  "format")
    echo "💅 Pythonコードをフォーマット中..."
    uv run ruff format
    ;;
  "yaml-lint")
    echo "📄 YAMLファイルをリンティング中..."
    uv run yamllint .
    ;;
  "yaml-fix")
    echo "🔧 YAMLファイルを自動修正中..."
    uv run yamlfix .
    ;;
  "shell-lint")
    echo "🔍 シェルスクリプトをリンティング中..."
    uv run shellcheck ./*.sh
    ;;
  "shell-format")
    echo "💅 シェルスクリプトをフォーマット中..."
    uv run shfmt -i 2 -p -s -ci -sr -fn -w ./*.sh
    ;;
  "shell-check")
    echo "🧪 シェルスクリプト品質チェックを実行中..."
    echo "--- シェルスクリプトリンティング ---"
    uv run shellcheck ./*.sh
    echo "--- シェルスクリプトフォーマットチェック ---"
    uv run shfmt -i 2 -p -s -ci -sr -fn -d ./*.sh
    echo "✅ シェルスクリプト品質チェックが完了しました"
    ;;
  "type-check")
    echo "🔍 Pyrightによる型チェックを実行中..."
    uv run pyright
    echo "✅ 型チェックが完了しました"
    ;;
  "test")
    echo "🧪 全てのコード品質チェックを実行中..."
    echo "--- Pythonリンティング ---"
    uv run ruff check
    echo "--- Python型チェック ---"
    uv run pyright
    echo "--- YAMLリンティング ---"
    uv run yamllint .
    echo "--- シェルスクリプトリンティング ---"
    uv run shellcheck ./*.sh
    echo "--- シェルスクリプトフォーマットチェック ---"
    uv run shfmt -i 2 -p -s -ci -sr -fn -d ./*.sh
    echo "✅ 全てのコード品質チェックが完了しました"
    ;;
  "run")
    echo "🚀 メインスクリプトを実行中..."
    uv run python sheet_to_json.py
    ;;
  "clean")
    echo "🧹 一時ファイルを削除中..."
    find . -type f -name "*.pyc" -delete 2> /dev/null || true
    find . -type d -name "__pycache__" -exec rm -rf {} + 2> /dev/null || true
    find . -type d -name "*.egg-info" -exec rm -rf {} + 2> /dev/null || true
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
