#!/usr/bin/env python3
"""ワークフローエラーを自動修正するスクリプト

GitHub Actionsのコード品質チェックで発生したエラーを
自動的に検出・修正するツール
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path


class WorkflowErrorFixer:
    """ワークフローエラーの自動修正を行うクラス"""

    def __init__(self) -> None:
        """初期化処理"""
        self.pr_number: int | None = None
        self.errors_fixed: list[str] = []
        self.project_root = Path.cwd()

    def run_command(
        self, cmd: list[str], *, capture_output: bool = True
    ) -> tuple[bool, str]:
        """コマンドを実行して結果を返す

        Args:
            cmd: 実行するコマンドのリスト
            capture_output: 出力をキャプチャするかどうか

        Returns:
            成功フラグと出力のタプル
        """
        try:
            if capture_output:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return True, result.stdout.strip()
            subprocess.run(cmd, check=True)
            return True, ""
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if hasattr(e, "stderr") and e.stderr else str(e)
            return False, error_msg

    def get_latest_workflow_run(self) -> dict | None:
        """最新のワークフロー実行結果を取得

        Returns:
            ワークフロー実行情報の辞書、または None
        """
        success, output = self.run_command([
            "gh",
            "run",
            "list",
            "--workflow=code_quality.yml",
            "--limit",
            "1",
            "--json",
            "databaseId,status,conclusion,headSha",
        ])
        if not success or not output:
            return None

        try:
            runs = json.loads(output)
            return runs[0] if runs else None
        except json.JSONDecodeError:
            return None

    def get_pr_comments(self) -> list[dict]:
        """PRのコメントを取得

        Returns:
            コメントのリスト
        """
        if not self.pr_number:
            return []

        success, output = self.run_command([
            "gh",
            "api",
            f"/repos/9c5s/imas_music_db/issues/{self.pr_number}/comments",
        ])
        if not success or not output:
            return []

        try:
            return json.loads(output)
        except json.JSONDecodeError:
            return []

    def parse_error_from_comments(self) -> dict[str, list[str]]:
        """PRコメントからエラーを解析

        Returns:
            エラータイプごとのエラーメッセージ辞書
        """
        comments = self.get_pr_comments()
        errors = {"ruff_lint": [], "ruff_format": [], "yaml_lint": []}

        for comment in comments:
            if comment.get("user", {}).get("login") != "github-actions[bot]":
                continue

            body = comment.get("body", "")

            # Ruffリンティングエラー
            if "❌ リンティング: エラーあり" in body:
                # エラー内容を抽出
                lint_match = re.search(r"```\n(.*?)```", body, re.DOTALL)
                if lint_match:
                    errors["ruff_lint"].append(lint_match.group(1))

            # Ruffフォーマットエラー
            if "❌ フォーマット: 修正が必要" in body:
                errors["ruff_format"].append("フォーマット修正が必要")

            # YAMLエラー
            if "❌ yamllint: エラーあり" in body:
                yaml_match = re.search(r"```\n(.*?)```", body, re.DOTALL)
                if yaml_match:
                    errors["yaml_lint"].append(yaml_match.group(1))

        return errors

    def fix_ruff_format_errors(self) -> bool:
        """Ruffフォーマットエラーを自動修正

        Returns:
            修正に成功したかどうか
        """
        print("🔧 Ruffフォーマットエラーを修正中...")
        success, output = self.run_command(["uv", "run", "ruff", "format"])
        if success:
            self.errors_fixed.append("Ruffフォーマット修正完了")
            print("✅ フォーマット修正完了")
            return True
        print(f"❌ フォーマット修正失敗: {output}")
        return False

    def fix_ruff_lint_errors(self) -> bool:
        """Ruffリンティングエラーを自動修正

        Returns:
            修正に成功したかどうか
        """
        print("🔧 Ruffリンティングエラーを修正中...")

        # 自動修正可能なエラーを修正
        success, output = self.run_command(["uv", "run", "ruff", "check", "--fix"])
        if success:
            self.errors_fixed.append("Ruffリンティング修正(自動修正可能分)")
            print("✅ 自動修正可能なエラーを修正しました")

        # 残りのエラーを確認
        success, output = self.run_command(["uv", "run", "ruff", "check"])
        if success:
            print("✅ 全てのリンティングエラーが解決しました")
            return True
        print("⚠️  自動修正できないエラーが残っています")
        return False

    def fix_yaml_errors(self) -> bool:
        """YAMLエラーを自動修正

        Returns:
            修正に成功したかどうか
        """
        print("🔧 YAMLエラーを修正中...")
        success, output = self.run_command(["uv", "run", "yamlfix", "."])
        if success:
            self.errors_fixed.append("YAML修正完了")
            print("✅ YAML修正完了")
            return True
        print(f"❌ YAML修正失敗: {output}")
        return False

    def fix_workflow_config_errors(self, errors: dict[str, list[str]]) -> bool:
        """ワークフロー設定エラーを修正

        Args:
            errors: エラー情報の辞書

        Returns:
            修正に成功したかどうか
        """
        # --output-format エラーの修正
        for error_msg in errors.get("ruff_lint", []):
            if "invalid value" in error_msg and "--output-format" in error_msg:
                print("🔧 ワークフロー設定の --output-format エラーを修正中...")
                workflow_file = self.project_root / ".github/workflows/code_quality.yml"
                if workflow_file.exists():
                    content = workflow_file.read_text()
                    new_content = content.replace("--output-format=text", "")
                    workflow_file.write_text(new_content)
                    self.errors_fixed.append(
                        "ワークフロー設定修正: --output-format削除"
                    )
                    print("✅ --output-format を削除しました")
                    return True
        return False

    def commit_and_push_fixes(self) -> bool:
        """修正をコミット・プッシュ

        Returns:
            成功したかどうか
        """
        if not self.errors_fixed:
            print("⚠️  修正する内容がありません")
            return False

        # 変更があるか確認
        success, output = self.run_command(["git", "status", "--porcelain"])
        if not success or not output:
            print("⚠️  変更されたファイルがありません")
            return False

        print("📝 修正をコミット中...")

        # 全ての変更をステージング
        self.run_command(["git", "add", "-A"])

        # コミットメッセージ作成
        commit_message = f"""ワークフローエラーを自動修正

修正内容:
{chr(10).join(f"- {fix}" for fix in self.errors_fixed)}

🤖 Generated with fix_workflow_errors.py

Co-Authored-By: Workflow Error Fixer <noreply@github.com>"""

        # コミット
        success, output = self.run_command(["git", "commit", "-m", commit_message])
        if not success:
            print(f"❌ コミット失敗: {output}")
            return False

        print("✅ コミット完了")

        # プッシュ
        print("📤 プッシュ中...")
        success, output = self.run_command(["git", "push"])
        if success:
            print("✅ プッシュ完了")
            return True
        print(f"❌ プッシュ失敗: {output}")
        return False

    def verify_fixes(self, wait_seconds: int = 30) -> bool:
        """修正後のワークフロー実行を確認

        Args:
            wait_seconds: ワークフロー開始を待つ秒数

        Returns:
            ワークフローが成功したかどうか
        """
        print(f"⏳ {wait_seconds}秒待機してワークフローの実行を確認します...")
        time.sleep(wait_seconds)

        # 新しいワークフロー実行を確認
        latest_run = self.get_latest_workflow_run()
        if not latest_run:
            print("❌ ワークフロー実行情報を取得できませんでした")
            return False

        run_id = latest_run.get("databaseId")
        print(f"🔍 ワークフロー実行 #{run_id} を監視中...")

        # ワークフローが完了するまで待機(最大5分)
        max_wait = 300  # 5分
        check_interval = 10
        elapsed = 0

        while elapsed < max_wait:
            success, output = self.run_command([
                "gh",
                "run",
                "view",
                str(run_id),
                "--json",
                "status,conclusion",
            ])
            if success and output:
                try:
                    run_info = json.loads(output)
                    status = run_info.get("status")
                    conclusion = run_info.get("conclusion")

                    if status == "completed":
                        if conclusion == "success":
                            print("✅ ワークフローが成功しました!")
                            return True
                        print(f"❌ ワークフローが失敗しました: {conclusion}")
                        return False
                except json.JSONDecodeError as e:
                    print(f"JSON解析エラー: {e}", file=sys.stderr)

            print(f"⏳ 実行中... ({elapsed}秒経過)")
            time.sleep(check_interval)
            elapsed += check_interval

        print("⏱️  タイムアウト: ワークフローの完了を確認できませんでした")
        return False

    def fix_all_errors(self) -> bool:
        """全てのエラーを修正

        Returns:
            全ての修正が成功したかどうか
        """
        print("🚀 ワークフローエラー自動修正を開始します")
        print("=" * 50)

        # 最新のPR番号を取得
        success, output = self.run_command([
            "gh",
            "pr",
            "list",
            "--limit",
            "1",
            "--json",
            "number",
        ])
        if success and output:
            try:
                prs = json.loads(output)
                if prs:
                    self.pr_number = prs[0]["number"]
                    print(f"📋 PR #{self.pr_number} を対象にします")
            except json.JSONDecodeError as e:
                print(f"JSON解析エラー: {e}", file=sys.stderr)

        # エラーを解析
        errors = self.parse_error_from_comments()

        # エラーがない場合
        if not any(errors.values()):
            print("✅ 修正が必要なエラーは見つかりませんでした")
            return True

        # 各種エラーを修正
        fixed_any = False

        # ワークフロー設定エラー
        if self.fix_workflow_config_errors(errors):
            fixed_any = True

        # Ruffフォーマットエラー
        if errors["ruff_format"] and self.fix_ruff_format_errors():
            fixed_any = True

        # Ruffリンティングエラー
        if errors["ruff_lint"] and self.fix_ruff_lint_errors():
            fixed_any = True

        # YAMLエラー
        if errors["yaml_lint"] and self.fix_yaml_errors():
            fixed_any = True

        # 修正をコミット・プッシュ
        if fixed_any and self.commit_and_push_fixes():
            # 修正結果を確認
            return self.verify_fixes()

        return fixed_any


def main() -> None:
    """メイン処理"""
    fixer = WorkflowErrorFixer()

    try:
        if fixer.fix_all_errors():
            print("\n✅ ワークフローエラーの修正が完了しました")
            sys.exit(0)
        else:
            print("\n❌ エラーの修正に失敗しました")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 処理を中断しました")
        sys.exit(1)
    except SystemExit:
        raise
    except (
        subprocess.CalledProcessError,
        json.JSONDecodeError,
        KeyError,
        FileNotFoundError,
    ) as e:
        print(f"\n❌ 予期しないエラーが発生しました: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
