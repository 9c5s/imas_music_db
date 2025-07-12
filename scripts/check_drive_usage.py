#!/usr/bin/env python3
"""Google Drive使用量調査スクリプト

サービスアカウントのGoogle Driveストレージ使用状況を調査し、
一時ファイルや不要なファイルを特定します。
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from google.auth import default
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource


def initialize_drive_service() -> Resource:
    """Google Drive APIサービスを初期化する"""
    try:
        credentials, project = default(scopes=["https://www.googleapis.com/auth/drive"])
        service = build("drive", "v3", credentials=credentials)
        print("[成功] Google Drive APIサービスが初期化されました")
        return service
    except (ValueError, OSError, HttpError) as e:
        print(f"[エラー] APIサービスの初期化に失敗: {e}")
        sys.exit(1)


def get_drive_usage_info(service: Resource) -> dict[str, Any]:
    """ドライブの使用量情報を取得する"""
    try:
        about = service.about().get(fields="storageQuota,user").execute()
        storage_quota = about.get("storageQuota", {})
        user_info = about.get("user", {})

        return {
            "total": int(storage_quota.get("limit", 0)),
            "used": int(storage_quota.get("usage", 0)),
            "user_email": user_info.get("emailAddress", "Unknown"),
        }
    except HttpError as e:
        print(f"[エラー] ストレージ情報の取得に失敗: {e}")
        return {}


def list_all_files(service: Resource) -> list[dict[str, Any]]:
    """全ファイルのリストを取得する"""
    files = []
    page_token = None

    print("[情報] ファイル一覧を取得中...")

    while True:
        try:
            # ファイル一覧を取得(詳細情報付き)
            results = (
                service.files()
                .list(
                    pageSize=1000,
                    fields=(
                        "nextPageToken, files(id, name, size, createdTime, "
                        "modifiedTime, mimeType, owners)"
                    ),
                    pageToken=page_token,
                )
                .execute()
            )

            batch_files = results.get("files", [])
            files.extend(batch_files)
            print(f"[情報] {len(batch_files)}件のファイルを取得")

            page_token = results.get("nextPageToken")
            if not page_token:
                break

        except HttpError as e:
            print(f"[エラー] ファイル一覧の取得に失敗: {e}")
            break

    print(f"[成功] 合計{len(files)}件のファイルを取得しました")
    return files


def analyze_files(files: list[dict[str, Any]]) -> dict[str, Any]:
    """ファイルを分析して統計情報を作成する"""
    total_size = 0
    temp_files = []
    old_files = []
    large_files = []

    # 30日前の日付
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)

    for file in files:
        # ファイルサイズ(Driveフォルダなどサイズがない場合は0)
        size = int(file.get("size", 0))
        total_size += size

        # ファイル名
        name = file.get("name", "")

        # 作成日時
        created_time_str = file.get("createdTime", "")
        if created_time_str:
            created_time = datetime.fromisoformat(created_time_str)

            # 古いファイル(30日以上前)
            if created_time < thirty_days_ago:
                old_files.append({
                    "name": name,
                    "size": size,
                    "created": created_time_str,
                    "id": file.get("id"),
                })

        # 一時ファイルの特定(名前にコピーを含む、または特定パターン)
        if (
            "コピー" in name
            or "Copy" in name
            or name.startswith("imas_music_db")
            or "temp" in name.lower()
        ):
            temp_files.append({
                "name": name,
                "size": size,
                "created": file.get("createdTime", ""),
                "id": file.get("id"),
            })

        # 大きなファイル(10MB以上)
        if size > 10 * 1024 * 1024:
            large_files.append({
                "name": name,
                "size": size,
                "size_mb": round(size / 1024 / 1024, 2),
                "id": file.get("id"),
            })

    return {
        "total_files": len(files),
        "total_size": total_size,
        "total_size_mb": round(total_size / 1024 / 1024, 2),
        "temp_files": temp_files,
        "old_files": old_files,
        "large_files": large_files,
    }


def print_analysis_report(usage_info: dict[str, Any], analysis: dict[str, Any]) -> None:
    """分析結果のレポートを出力する"""
    print("\n" + "=" * 60)
    print("🔍 Google Drive使用量調査レポート")
    print("=" * 60)

    # 基本情報
    print(f"\n📧 サービスアカウント: {usage_info.get('user_email', 'Unknown')}")

    # ストレージ使用量
    total_gb = usage_info.get("total", 0) / (1024**3)
    used_gb = usage_info.get("used", 0) / (1024**3)
    usage_percent = (used_gb / total_gb * 100) if total_gb > 0 else 0

    print("\n💾 ストレージ使用量:")
    print(f"   使用量: {used_gb:.2f} GB / {total_gb:.2f} GB ({usage_percent:.1f}%)")

    # ファイル統計
    print("\n📊 ファイル統計:")
    print(f"   総ファイル数: {analysis['total_files']:,}件")
    print(f"   総サイズ: {analysis['total_size_mb']:.2f} MB")

    # 一時ファイル
    print(f"\n🗂️ 一時ファイル ({len(analysis['temp_files'])}件):")
    if analysis["temp_files"]:
        for file in analysis["temp_files"][:10]:  # 上位10件
            size_mb = file["size"] / 1024 / 1024
            print(f"   - {file['name']} ({size_mb:.2f} MB)")
        if len(analysis["temp_files"]) > 10:
            print(f"   ... 他{len(analysis['temp_files']) - 10}件")
    else:
        print("   一時ファイルは見つかりませんでした")

    # 古いファイル
    print(f"\n📅 古いファイル(30日以上前, {len(analysis['old_files'])}件):")
    if analysis["old_files"]:
        for file in analysis["old_files"][:5]:  # 上位5件
            size_mb = file["size"] / 1024 / 1024
            print(f"   - {file['name']} ({size_mb:.2f} MB, {file['created']})")
        if len(analysis["old_files"]) > 5:
            print(f"   ... 他{len(analysis['old_files']) - 5}件")
    else:
        print("   古いファイルは見つかりませんでした")

    # 大きなファイル
    print(f"\n📦 大きなファイル(10MB以上, {len(analysis['large_files'])}件):")
    if analysis["large_files"]:
        large_files_sorted = sorted(
            analysis["large_files"], key=lambda x: x["size"], reverse=True
        )
        for file in large_files_sorted[:5]:
            print(f"   - {file['name']} ({file['size_mb']} MB)")
        if len(analysis["large_files"]) > 5:
            print(f"   ... 他{len(analysis['large_files']) - 5}件")
    else:
        print("   大きなファイルは見つかりませんでした")

    # 推奨アクション
    print("\n💡 推奨アクション:")
    temp_size = sum(f["size"] for f in analysis["temp_files"]) / 1024 / 1024
    old_size = sum(f["size"] for f in analysis["old_files"]) / 1024 / 1024

    if temp_size > 0:
        print(f"   - 一時ファイルの削除で {temp_size:.2f} MB の容量を削減可能")
    if old_size > 0:
        print(f"   - 古いファイルの削除で {old_size:.2f} MB の容量を削減可能")

    if usage_percent > 80:
        print(f"   ⚠️ 使用量が{usage_percent:.1f}%に達しています。容量削減を推奨")
    elif usage_percent > 90:
        print(f"   🚨 使用量が{usage_percent:.1f}%に達しています。早急な容量削減が必要")


def main() -> None:
    """メイン処理"""
    print("🔍 Google Drive使用量調査を開始します...")

    # APIサービス初期化
    service = initialize_drive_service()

    # ストレージ使用量情報取得
    print("[情報] ストレージ使用量を取得中...")
    usage_info = get_drive_usage_info(service)

    # ファイル一覧取得
    files = list_all_files(service)

    # ファイル分析
    print("[情報] ファイルを分析中...")
    analysis = analyze_files(files)

    # レポート出力
    print_analysis_report(usage_info, analysis)

    print("\n✅ 調査が完了しました")


if __name__ == "__main__":
    main()
