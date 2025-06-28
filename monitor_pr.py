#!/usr/bin/env python3
"""
PRのGitHub Actions実行状況とコメントを自動監視するスクリプト

使用方法:
    python monitor_pr.py [PR番号]
    
    PR番号を指定しない場合は最新のPRを監視
"""
import json
import subprocess
import time
import sys
from typing import Dict, List, Optional


def run_gh_command(cmd: List[str]) -> str:
    """GitHub CLIコマンドを実行して結果を取得する"""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"GitHub CLIコマンドエラー: {e}")
        print(f"エラー出力: {e.stderr}")
        return ""


def get_latest_pr_number() -> Optional[int]:
    """最新のPR番号を取得する"""
    output = run_gh_command([
        "gh", "pr", "list", "--json", "number", "--limit", "1"
    ])
    if not output:
        return None
    
    try:
        prs = json.loads(output)
        if prs and len(prs) > 0:
            return prs[0]["number"]
    except json.JSONDecodeError:
        print("PR一覧の取得に失敗しました")
    return None


def get_pr_status(pr_number: int) -> Dict:
    """PRの詳細情報を取得する"""
    output = run_gh_command([
        "gh", "pr", "view", str(pr_number), 
        "--json", "number,title,state,mergeable,statusCheckRollup"
    ])
    if not output:
        return {}
    
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        print(f"PR#{pr_number}の詳細取得に失敗しました")
        return {}


def get_pr_comments(pr_number: int) -> List[Dict]:
    """PRのコメントを取得する"""
    output = run_gh_command([
        "gh", "pr", "view", str(pr_number), 
        "--json", "comments"
    ])
    if not output:
        return []
    
    try:
        data = json.loads(output)
        return data.get("comments", [])
    except json.JSONDecodeError:
        print(f"PR#{pr_number}のコメント取得に失敗しました")
        return []


def format_check_status(checks: List[Dict]) -> str:
    """チェック状況をフォーマットして表示用の文字列を生成する"""
    if not checks:
        return "⏳ チェック待機中..."
    
    status_icons = {
        "SUCCESS": "✅",
        "FAILURE": "❌", 
        "PENDING": "⏳",
        "IN_PROGRESS": "🔄",
        "NEUTRAL": "⚪",
        "SKIPPED": "⏭️"
    }
    
    results = []
    for check in checks:
        icon = status_icons.get(check.get("state", "UNKNOWN"), "❓")
        name = check.get("name", "Unknown")
        results.append(f"{icon} {name}")
    
    return "\n".join(results)


def find_code_quality_comment(comments: List[Dict]) -> Optional[str]:
    """コード品質チェックのコメントを探す"""
    for comment in comments:
        if comment.get("author", {}).get("login") == "github-actions[bot]":
            body = comment.get("body", "")
            if "コード品質チェック結果" in body or "YAMLコード品質" in body:
                return body
    return None


def monitor_pr(pr_number: int, check_interval: int = 10):
    """PRを監視してリアルタイムで状況を表示する"""
    print(f"🔍 PR#{pr_number} の監視を開始します...")
    print(f"⏰ {check_interval}秒間隔でチェックします")
    print("=" * 60)
    
    last_status = None
    last_comment_count = 0
    
    while True:
        # PR情報を取得
        pr_info = get_pr_status(pr_number)
        if not pr_info:
            print("❌ PR情報の取得に失敗しました")
            time.sleep(check_interval)
            continue
        
        # チェック状況を表示
        checks = pr_info.get("statusCheckRollup", [])
        current_status = format_check_status(checks)
        
        if current_status != last_status:
            print(f"\n🔄 チェック状況更新 ({time.strftime('%H:%M:%S')})")
            print("-" * 40)
            print(current_status)
            print("-" * 40)
            last_status = current_status
        
        # コメントをチェック
        comments = get_pr_comments(pr_number)
        if len(comments) > last_comment_count:
            print(f"\n💬 新しいコメントが追加されました ({time.strftime('%H:%M:%S')})")
            
            # コード品質チェックのコメントを探す
            quality_comment = find_code_quality_comment(comments)
            if quality_comment:
                print("📊 コード品質チェック結果:")
                print("-" * 40)
                # コメントから結果部分のみを抽出して表示
                lines = quality_comment.split('\n')
                in_result_section = False
                for line in lines:
                    if line.startswith('##') or line.startswith('###'):
                        in_result_section = True
                        print(line)
                    elif in_result_section and (line.startswith('✅') or line.startswith('❌')):
                        print(line)
                print("-" * 40)
            
            last_comment_count = len(comments)
        
        # 全てのチェックが完了しているかを確認
        if checks:
            all_complete = all(
                check.get("state") in ["SUCCESS", "FAILURE", "NEUTRAL", "SKIPPED"] 
                for check in checks
            )
            if all_complete:
                print(f"\n🎉 全てのチェックが完了しました! ({time.strftime('%H:%M:%S')})")
                break
        
        # 少し待機
        print(f"⏳ 次回チェック: {check_interval}秒後...", end="\r")
        time.sleep(check_interval)


def main():
    """メイン処理"""
    # PR番号を取得
    if len(sys.argv) > 1:
        try:
            pr_number = int(sys.argv[1])
        except ValueError:
            print("❌ エラー: PR番号は数値で指定してください")
            sys.exit(1)
    else:
        print("🔍 最新のPRを検索中...")
        pr_number = get_latest_pr_number()
        if pr_number is None:
            print("❌ 開いているPRが見つかりませんでした")
            sys.exit(1)
        print(f"📋 最新のPR: #{pr_number}")
    
    # GitHub CLIが利用可能かチェック
    try:
        subprocess.run(["gh", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ エラー: GitHub CLI (gh) がインストールされていないか、認証されていません")
        print("💡 'gh auth login' を実行してください")
        sys.exit(1)
    
    # 監視開始
    try:
        monitor_pr(pr_number)
    except KeyboardInterrupt:
        print(f"\n\n👋 PR#{pr_number} の監視を終了しました")


if __name__ == "__main__":
    main()