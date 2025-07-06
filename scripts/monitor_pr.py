#!/usr/bin/env python3
"""PRのGitHub Actions実行状況とコメントを自動監視するスクリプト

使用方法:
    python monitor_pr.py [PR番号]

    PR番号を指定しない場合は最新のPRを監視
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from typing import Any


def run_gh_command(cmd: list[str]) -> str:
    """GitHub CLIコマンドを実行して結果を取得する"""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"GitHub CLIコマンドエラー: {e}", flush=True)
        print(f"エラー出力: {e.stderr}", flush=True)
        return ""


def get_latest_pr_number() -> int | None:
    """最新のPR番号を取得する"""
    output = run_gh_command(["gh", "pr", "list", "--json", "number", "--limit", "1"])
    if not output:
        return None

    try:
        prs: list[dict[str, Any]] = json.loads(output)
        if prs and len(prs) > 0:
            return prs[0]["number"]
    except json.JSONDecodeError:
        print("PR一覧の取得に失敗しました", flush=True)
    return None


def get_pr_status(pr_number: int) -> dict[str, Any]:
    """PRの詳細情報を取得する"""
    output = run_gh_command([
        "gh",
        "pr",
        "view",
        str(pr_number),
        "--json",
        "number,title,state,mergeable,statusCheckRollup",
    ])
    if not output:
        return {}

    try:
        pr_data: dict[str, Any] = json.loads(output)
        return pr_data
    except json.JSONDecodeError:
        print(f"PR#{pr_number}の詳細取得に失敗しました", flush=True)
        return {}


def get_pr_comments(pr_number: int) -> list[dict[str, Any]]:
    """PRのコメントを取得する"""
    output = run_gh_command(["gh", "pr", "view", str(pr_number), "--json", "comments"])
    if not output:
        return []

    try:
        data: dict[str, Any] = json.loads(output)
        comments: list[dict[str, Any]] = data.get("comments", [])
        return comments
    except json.JSONDecodeError:
        print(f"PR#{pr_number}のコメント取得に失敗しました", flush=True)
        return []


def format_check_status(checks: list[dict[str, Any]]) -> str:
    """チェック状況をフォーマットして表示用の文字列を生成する"""
    if not checks:
        return "⏳ チェック待機中..."

    conclusion_icons = {
        "SUCCESS": "✅",
        "FAILURE": "❌",
        "NEUTRAL": "⚪",
        "SKIPPED": "⏭️",
    }

    status_icons = {
        "PENDING": "⏳",
        "IN_PROGRESS": "🔄",
        "COMPLETED": "",  # conclusionアイコンを使用
    }

    results: list[str] = []
    for check in checks:
        check_status: str = check.get("status", "UNKNOWN")
        check_conclusion: str = check.get("conclusion", "UNKNOWN")
        name: str = check.get("name", "Unknown")

        # ステータスがCOMPLETEDの場合はconclusionアイコンを使用
        if check_status == "COMPLETED":
            icon: str = conclusion_icons.get(check_conclusion, "❓")
        else:
            icon = status_icons.get(check_status, "❓")

        results.append(f"{icon} {name}")

    return "\n".join(results)


def find_code_quality_comment(comments: list[dict[str, Any]]) -> str | None:
    """コード品質チェックのコメントを探す"""
    for comment in comments:
        author: dict[str, Any] | None = comment.get("author")
        if author and author.get("login") == "github-actions[bot]":
            body: str | None = comment.get("body")
            if body and ("コード品質チェック結果" in body or "YAMLコード品質" in body):
                return body
    return None


def monitor_pr(pr_number: int, check_interval: int = 10) -> None:
    """PRを監視してリアルタイムで状況を表示する"""
    print(f"🔍 PR#{pr_number} の監視を開始します...", flush=True)
    print(f"⏰ {check_interval}秒間隔でチェックします", flush=True)
    print("=" * 60, flush=True)

    last_status = None
    last_comment_count = 0
    check_count = 0

    while True:
        check_count += 1
        timestamp = time.strftime("%H:%M:%S")

        print(
            f"[{timestamp}] 📡 チェック #{check_count} - PR情報を取得中...", flush=True
        )

        # PR情報を取得
        pr_info = get_pr_status(pr_number)
        if not pr_info:
            print(f"[{timestamp}] ❌ PR情報の取得に失敗しました", flush=True)
            time.sleep(check_interval)
            continue

        print(f"[{timestamp}] ✅ PR情報取得完了", flush=True)

        # PR基本情報をログ出力
        pr_title = pr_info.get("title", "Unknown")
        pr_state = pr_info.get("state", "Unknown")
        mergeable = pr_info.get("mergeable", "Unknown")

        print(
            f"[{timestamp}] 📋 PR情報: '{pr_title}' (状態: {pr_state}, "
            f"マージ可能: {mergeable})",
            flush=True,
        )

        # チェック状況を表示
        checks = pr_info.get("statusCheckRollup", [])
        current_status = format_check_status(checks)

        print(f"[{timestamp}] 🔄 チェック数: {len(checks)}個", flush=True)

        if current_status != last_status:
            print(f"\n[{timestamp}] 🔄 チェック状況更新", flush=True)
            print("-" * 40, flush=True)
            print(current_status, flush=True)
            print("-" * 40, flush=True)
            last_status = current_status
        else:
            print(f"[{timestamp}] ⏸️  チェック状況: 変更なし", flush=True)

        # コメントをチェック
        print(f"[{timestamp}] 💬 コメント確認中...", flush=True)
        comments = get_pr_comments(pr_number)
        print(f"[{timestamp}] 📝 現在のコメント数: {len(comments)}個", flush=True)

        if len(comments) > last_comment_count:
            print(f"\n[{timestamp}] 💬 新しいコメントが追加されました!", flush=True)
            print(
                f"[{timestamp}] 📈 コメント数: {last_comment_count} → {len(comments)}",
                flush=True,
            )

            # コード品質チェックのコメントを探す
            quality_comment = find_code_quality_comment(comments)
            if quality_comment:
                print(f"[{timestamp}] 📊 コード品質チェック結果を発見:", flush=True)
                print("-" * 40, flush=True)
                # コメントから結果部分のみを抽出して表示
                lines = quality_comment.split("\n")
                in_result_section = False
                for line in lines:
                    if line.startswith(("##", "###")):
                        in_result_section = True
                        print(line, flush=True)
                    elif in_result_section and (line.startswith(("✅", "❌"))):
                        print(line, flush=True)
                print("-" * 40, flush=True)
            else:
                print(f"[{timestamp}] 📝 一般的なコメントが追加されました", flush=True)

            last_comment_count = len(comments)
        else:
            print(f"[{timestamp}] 📭 新しいコメントなし", flush=True)

        # 全てのチェックが完了しているかを確認
        print(f"[{timestamp}] 🔍 完了状況を確認中...", flush=True)
        if checks:
            completed_checks = [
                check for check in checks if check.get("status") == "COMPLETED"
            ]
            pending_checks = [
                check
                for check in checks
                if check.get("status") in ["PENDING", "IN_PROGRESS"]
            ]

            # 失敗したチェックを特定
            failed_checks = [
                check
                for check in completed_checks
                if check.get("conclusion") == "FAILURE"
            ]

            print(f"[{timestamp}] ✅ 完了済み: {len(completed_checks)}個", flush=True)
            print(f"[{timestamp}] ⏳ 実行中: {len(pending_checks)}個", flush=True)

            if failed_checks:
                print(f"[{timestamp}] ❌ 失敗: {len(failed_checks)}個", flush=True)
                for failed_check in failed_checks:
                    check_name = failed_check.get("name", "Unknown")
                    details_url = failed_check.get("detailsUrl", "")
                    print(f"[{timestamp}] ❌ {check_name}: {details_url}", flush=True)

            all_complete = len(pending_checks) == 0
            if all_complete:
                if failed_checks:
                    print(
                        f"\n[{timestamp}] ⚠️ 全てのチェックが完了しましたが、"
                        f"{len(failed_checks)}個のチェックが失敗しました",
                        flush=True,
                    )
                else:
                    print(
                        f"\n[{timestamp}] 🎉 全てのチェックが完了しました!", flush=True
                    )
                break
        else:
            print(f"[{timestamp}] ❓ チェック情報が見つかりません", flush=True)

        # 少し待機
        print(f"[{timestamp}] ⏳ {check_interval}秒後に次回チェック...", flush=True)
        print("-" * 60, flush=True)
        time.sleep(check_interval)


def main() -> None:
    """メイン処理"""
    # PR番号を取得
    if len(sys.argv) > 1:
        try:
            pr_number = int(sys.argv[1])
        except ValueError:
            print("❌ エラー: PR番号は数値で指定してください", flush=True)
            sys.exit(1)
    else:
        print("🔍 最新のPRを検索中...", flush=True)
        pr_number = get_latest_pr_number()
        if pr_number is None:
            print("❌ 開いているPRが見つかりませんでした", flush=True)
            sys.exit(1)
        print(f"📋 最新のPR: #{pr_number}", flush=True)

    # GitHub CLIが利用可能かチェック
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "❌ エラー: GitHub CLI (gh) がインストールされていないか、"
            "認証されていません",
            flush=True,
        )
        print("💡 'gh auth login' を実行してください", flush=True)
        sys.exit(1)

    # 監視開始
    try:
        monitor_pr(pr_number)
    except KeyboardInterrupt:
        print(f"\n\n👋 PR#{pr_number} の監視を終了しました", flush=True)


if __name__ == "__main__":
    main()
