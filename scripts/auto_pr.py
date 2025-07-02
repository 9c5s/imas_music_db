#!/usr/bin/env python3
"""PR作成と監視を自動化するスクリプト

使用方法:
    python auto_pr.py [--title "PRタイトル"] [--body "PR説明"]

機能:
    1. 現在のブランチからPRを作成
    2. 作成されたPRを自動監視
    3. GitHub Actions完了まで待機
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import threading
import time


class AutoPR:
    """PR作成と監視を自動化するクラス"""

    def __init__(self) -> None:
        """初期化処理"""
        self.monitoring: bool = False
        self.monitor_thread: threading.Thread | None = None

    def run_command(self, cmd: list[str], *, capture_output: bool = True) -> tuple[bool, str]:
        """コマンドを実行して結果を返す"""
        try:
            if capture_output:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return True, result.stdout.strip()
            subprocess.run(cmd, check=True)
            return True, ""
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if hasattr(e, "stderr") and e.stderr else str(e)
            return False, error_msg

    def get_current_branch(self) -> str | None:
        """現在のブランチ名を取得"""
        success, output = self.run_command(["git", "branch", "--show-current"])
        if success:
            return output
        return None

    def check_git_status(self) -> bool:
        """Gitの状態をチェック(コミットされていない変更がないか)"""
        success, output = self.run_command(["git", "status", "--porcelain"])
        if not success:
            return False
        return len(output.strip()) == 0

    def push_current_branch(self) -> bool:
        """現在のブランチをリモートにプッシュ"""
        branch = self.get_current_branch()
        if not branch:
            print("❌ 現在のブランチ名を取得できませんでした")
            return False

        print(f"📤 ブランチ '{branch}' をリモートにプッシュ中...")
        success, output = self.run_command([
            "git",
            "push",
            "--set-upstream",
            "origin",
            branch,
        ])

        if success:
            print("✅ プッシュ完了")
            return True
        print(f"❌ プッシュに失敗しました: {output}")
        return False

    def create_pr(self, title: str, body: str) -> int | None:
        """PRを作成して番号を返す"""
        print("🚀 プルリクエストを作成中...")

        # PRの作成
        cmd = ["gh", "pr", "create", "--title", title, "--body", body]
        success, output = self.run_command(cmd)

        if not success:
            print(f"❌ PR作成に失敗しました: {output}")
            return None

        # PR番号を抽出
        try:
            # outputからPR URLを取得し、番号を抽出
            pr_url: str = output.strip()
            pr_number: int = int(pr_url.split("/")[-1])
        except (ValueError, IndexError):
            print(f"❌ PR番号の取得に失敗しました: {output}")
            return None
        else:
            print(f"✅ PR#{pr_number} を作成しました")
            print(f"🔗 URL: {pr_url}")
            return pr_number

    def start_monitoring(self, pr_number: int) -> None:
        """PRの監視を開始(別スレッドで実行)"""
        print(f"\n🔍 PR#{pr_number} の監視を開始します...")
        print("⏰ Ctrl+C で監視を停止できます")
        print("=" * 60)

        # monitor_pr.pyを実行
        self.monitoring = True
        self.monitor_thread = threading.Thread(
            target=self._run_monitor, args=(pr_number,), daemon=True
        )
        self.monitor_thread.start()

        # メインスレッドで待機
        try:
            while self.monitoring and self.monitor_thread.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n\n👋 PR#{pr_number} の監視を停止しました")
            self.monitoring = False

    def _run_monitor(self, pr_number: int) -> None:
        """監視スクリプトを実行"""
        try:
            # uvを使ってmonitor_pr.pyを実行
            subprocess.run(
                ["uv", "run", "python", "scripts/monitor_pr.py", str(pr_number)],
                check=True,
            )
        except subprocess.CalledProcessError:
            print("❌ 監視スクリプトの実行でエラーが発生しました")
        finally:
            self.monitoring = False

    def generate_default_pr_info(self) -> tuple[str, str]:
        """デフォルトのPR情報を生成"""
        branch = self.get_current_branch()
        if not branch:
            return "新機能追加", "新機能を追加しました"

        # ブランチ名からタイトルを生成
        if branch.startswith("feature/"):
            title = branch.replace("feature/", "").replace("-", " ").replace("_", " ")
            title = title.title()
        elif branch.startswith("fix/"):
            title = "バグ修正: " + branch.replace("fix/", "").replace("-", " ").replace(
                "_", " "
            )
        else:
            title = f"{branch} の変更"

        # 最近のコミットメッセージを取得してbodyに含める
        success, commits = self.run_command([
            "git",
            "log",
            "--oneline",
            "-5",
            "--format=%s",
        ])

        body_parts: list[str] = ["## Summary"]
        if success and commits:
            commit_list: list[str] = commits.split("\n")
            body_parts.extend([
                f"- {commit}" for commit in commit_list if commit.strip()
            ])
        else:
            body_parts.append("- 変更内容の詳細説明")

        body_parts.extend([
            "",
            "## Test plan",
            "- [ ] 機能が正常に動作することを確認",
            "- [ ] 既存機能に影響がないことを確認",
            "",
            "🤖 Generated with [Claude Code](https://claude.ai/code)",
        ])

        return title, "\n".join(body_parts)

    def run(self, title: str | None = None, body: str | None = None) -> bool:
        """メイン処理"""
        print("🤖 PR自動作成・監視ツール")
        print("=" * 50)

        # 前提条件チェック
        if not self.check_git_status():
            print("❌ コミットされていない変更があります")
            print("💡 先に 'git add .' と 'git commit' を実行してください")
            return False

        # ブランチをプッシュ
        if not self.push_current_branch():
            return False

        # PR情報を準備
        if not title or not body:
            default_title: str
            default_body: str
            default_title, default_body = self.generate_default_pr_info()
            title = title or default_title
            body = body or default_body

        print("\n📝 PR情報:")
        print(f"タイトル: {title}")
        print(f"説明: {body[:100]}...")

        # 確認
        response = input("\n? このPRを作成しますか? (y/N): ")
        if response.lower() not in ["y", "yes"]:
            print("❌ PR作成をキャンセルしました")
            return False

        # PRを作成
        pr_number = self.create_pr(title, body)
        if not pr_number:
            return False

        # 監視を開始
        self.start_monitoring(pr_number)
        return True


def main() -> None:
    """メイン関数"""
    parser = argparse.ArgumentParser(description="PR作成と監視を自動化するスクリプト")
    parser.add_argument(
        "--title", "-t", help="PRタイトル(指定しない場合はブランチ名から自動生成)"
    )
    parser.add_argument(
        "--body", "-b", help="PR説明(指定しない場合は最近のコミットから自動生成)"
    )
    parser.add_argument(
        "--no-monitor", "-n", action="store_true", help="監視を行わずPR作成のみ実行"
    )

    args = parser.parse_args()

    # GitHub CLIのチェック
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ GitHub CLI (gh) がインストールされていないか、認証されていません")
        print("💡 'gh auth login' を実行してください")
        sys.exit(1)

    # 自動PRツールを実行
    auto_pr = AutoPR()

    def signal_handler(_signum: int, _frame: object) -> None:
        print("\n\n👋 処理を中断しました")
        auto_pr.monitoring = False
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        success = auto_pr.run(args.title, args.body)
        if success:
            print("\n✅ PR作成・監視が完了しました")
        else:
            print("\n❌ 処理が失敗しました")
            sys.exit(1)
    except (KeyboardInterrupt, SystemExit):
        raise
    except (subprocess.CalledProcessError, FileNotFoundError, PermissionError) as e:
        print(f"\n❌ 予期しないエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
