#!/usr/bin/env python3
"""Google Drive自動クリーンアップスクリプト

サービスアカウントのGoogle Driveから一時ファイルや古いファイルを自動削除し、
ストレージ容量を削減します。
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from google.auth import default  # type: ignore[import-untyped]
from googleapiclient.discovery import build  # type: ignore[import-untyped]
from googleapiclient.errors import HttpError  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from googleapiclient.discovery import Resource


def initialize_drive_service() -> Resource:
    """Google Drive APIサービスを初期化する"""
    try:
        credentials, project = default(scopes=["https://www.googleapis.com/auth/drive"])  # type: ignore[misc]
        service = build("drive", "v3", credentials=credentials)  # type: ignore[arg-type]
        print("[成功] Google Drive APIサービスが初期化されました")
        return service  # type: ignore[return-value]
    except (ValueError, OSError, HttpError) as e:
        print(f"[エラー] APIサービスの初期化に失敗: {e}")
        sys.exit(1)


def get_drive_usage_info(service: Resource) -> dict[str, Any]:
    """ドライブの使用量情報を取得する"""
    try:
        about = service.about().get(fields="storageQuota,user").execute()  # type: ignore[attr-defined]
        storage_quota = about.get("storageQuota", {})  # type: ignore[attr-defined]
        user_info = about.get("user", {})  # type: ignore[attr-defined]

        return {
            "total": int(storage_quota.get("limit", 0)),  # type: ignore[arg-type]
            "used": int(storage_quota.get("usage", 0)),  # type: ignore[arg-type]
            "user_email": user_info.get("emailAddress", "Unknown"),  # type: ignore[attr-defined]
        }
    except HttpError as e:
        print(f"[エラー] ストレージ情報の取得に失敗: {e}")
        return {}


def find_cleanup_candidates(service: Resource) -> dict[str, list[dict[str, Any]]]:
    """クリーンアップ対象ファイルを特定する"""
    cleanup_candidates = {
        "temp_files": [],
        "old_files": [],
    }

    page_token = None
    thirty_days_ago = datetime.now(UTC) - timedelta(days=30)

    print("[情報] クリーンアップ対象ファイルを検索中...")

    while True:
        try:
            # 一時ファイルと古いファイルを検索
            results = (  # type: ignore[misc]
                service.files()  # type: ignore[attr-defined]
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

            batch_files = results.get("files", [])  # type: ignore[attr-defined]

            for file in batch_files:
                name = file.get("name", "")
                created_time_str = file.get("createdTime", "")
                file_id = file.get("id", "")
                size = int(file.get("size", 0))

                # 一時ファイルの特定
                if (
                    "コピー" in name
                    or "Copy" in name
                    or name.startswith(("tmp_copy_", "imas_music_db"))
                    or "temp" in name.lower()
                ):
                    cleanup_candidates["temp_files"].append({
                        "id": file_id,
                        "name": name,
                        "size": size,
                        "created": created_time_str,
                    })

                # 古いファイル(30日以上前)の特定
                if created_time_str:
                    try:
                        created_time = datetime.fromisoformat(
                            created_time_str.rstrip("Z")
                        ).replace(tzinfo=UTC)
                        if created_time < thirty_days_ago:
                            cleanup_candidates["old_files"].append({
                                "id": file_id,
                                "name": name,
                                "size": size,
                                "created": created_time_str,
                            })
                    except ValueError as e:
                        print(f"[警告] 日付解析エラー: {created_time_str} - {e}")
                        continue

            page_token = results.get("nextPageToken")  # type: ignore[attr-defined]
            if not page_token:
                break

        except HttpError as e:
            print(f"[エラー] ファイル検索中にエラーが発生: {e}")
            break

    return cleanup_candidates


def cleanup_files(
    service: Resource,
    files_to_delete: list[dict[str, Any]],
    category: str,
) -> tuple[int, int]:
    """指定されたファイルを削除する

    Returns:
        (削除成功数, 削除失敗数)
    """
    success_count = 0
    error_count = 0
    total_size = sum(f.get("size", 0) for f in files_to_delete)

    if not files_to_delete:
        print(f"[情報] {category}: 削除対象ファイルがありません")
        return 0, 0

    print(f"[情報] {category}: {len(files_to_delete)}件のファイルを削除中...")
    print(f"[情報] 削除予定容量: {total_size / 1024 / 1024:.2f} MB")

    for file in files_to_delete:
        file_id = file.get("id")
        file_name = file.get("name", "Unknown")

        if not file_id:
            print(f"[警告] ファイルIDが見つかりません: {file_name}")
            error_count += 1
            continue

        try:
            service.files().delete(fileId=file_id).execute()  # type: ignore[attr-defined]
            success_count += 1
            size_mb = file.get("size", 0) / 1024 / 1024
            print(f"[成功] 削除: {file_name} ({size_mb:.2f} MB)")
        except HttpError as e:
            error_count += 1
            print(f"[エラー] 削除失敗: {file_name} - {e}")

    print(f"[完了] {category}: {success_count}件削除成功, {error_count}件削除失敗")
    return success_count, error_count


def main() -> None:
    """メイン処理"""
    print("🧹 Google Drive自動クリーンアップを開始します...")

    # APIサービス初期化
    service = initialize_drive_service()

    # クリーンアップ前の使用量確認
    print("\n[情報] クリーンアップ前のストレージ使用量を確認中...")
    usage_before = get_drive_usage_info(service)

    if usage_before:
        used_gb_before = usage_before.get("used", 0) / (1024**3)
        total_gb = usage_before.get("total", 0) / (1024**3)
        usage_percent_before = (used_gb_before / total_gb * 100) if total_gb > 0 else 0

        usage_info = (
            f"{used_gb_before:.2f} GB / {total_gb:.2f} GB ({usage_percent_before:.1f}%)"
        )
        print(f"[情報] 使用量: {usage_info}")
        print(f"[情報] アカウント: {usage_before.get('user_email', 'Unknown')}")
    else:
        print("[エラー] ストレージ使用量の取得に失敗しました")
        return

    # クリーンアップ対象ファイルの検索
    cleanup_candidates = find_cleanup_candidates(service)

    temp_files = cleanup_candidates["temp_files"]
    old_files = cleanup_candidates["old_files"]

    print(f"\n[情報] 一時ファイル: {len(temp_files)}件")
    print(f"[情報] 古いファイル: {len(old_files)}件")

    # 削除実行
    total_deleted = 0
    total_errors = 0

    # 一時ファイルの削除
    if temp_files:
        deleted, errors = cleanup_files(service, temp_files, "一時ファイル")
        total_deleted += deleted
        total_errors += errors

    # 古いファイルの削除(最大100件まで)
    if old_files:
        # 古いファイルは多数存在する可能性があるため、サイズの大きいものから優先削除
        sorted_old_files = sorted(
            old_files, key=lambda x: x.get("size", 0), reverse=True
        )
        limited_old_files = sorted_old_files[:100]  # 最大100件

        if len(old_files) > 100:
            msg = (
                f"古いファイルが{len(old_files)}件見つかりましたが、"
                "今回は上位100件のみ削除します"
            )
            print(f"[情報] {msg}")

        deleted, errors = cleanup_files(service, limited_old_files, "古いファイル")
        total_deleted += deleted
        total_errors += errors

    # クリーンアップ後の使用量確認
    print("\n[情報] クリーンアップ後のストレージ使用量を確認中...")
    usage_after = get_drive_usage_info(service)

    if usage_after:
        used_gb_after = usage_after.get("used", 0) / (1024**3)
        usage_percent_after = (used_gb_after / total_gb * 100) if total_gb > 0 else 0
        freed_gb = used_gb_before - used_gb_after

        usage_info_after = (
            f"{used_gb_after:.2f} GB / {total_gb:.2f} GB ({usage_percent_after:.1f}%)"
        )
        print(f"[情報] 使用量: {usage_info_after}")
        print(f"[成功] 削減された容量: {freed_gb:.2f} GB")

    # 結果サマリー
    print(f"\n{'=' * 60}")
    print("🧹 クリーンアップ結果サマリー")
    print(f"{'=' * 60}")
    print(f"削除成功: {total_deleted}件")
    print(f"削除失敗: {total_errors}件")

    if usage_before and usage_after:
        print(f"使用量変化: {used_gb_before:.2f} GB → {used_gb_after:.2f} GB")
        print(f"削減容量: {freed_gb:.2f} GB")

        if usage_percent_after < 80:
            print("✅ ストレージ使用量が正常範囲内になりました")
        elif usage_percent_after < 90:
            print("⚠️ ストレージ使用量がまだ高めです。")
            print("追加のクリーンアップを検討してください")
        else:
            print("🚨 ストレージ使用量がまだ高い状態です。手動での追加削除が必要です")

    print("\n✅ クリーンアップが完了しました")


if __name__ == "__main__":
    main()
