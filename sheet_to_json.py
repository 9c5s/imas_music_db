"""Googleスプレッドシートをコピーし、指定のシートからデータを取得・整形します

このスクリプトは以下の手順を自動で実行します:
1. Google Drive APIを使用し、指定されたスプレッドシートを
   ユーザーのドライブにコピーする。
2. Google Sheets APIを使用し、コピーされたシートからデータを読み取る。
3. 読み取ったデータを設定に基づいて処理・整形し、IDの降順でソートする。
4. 処理後のデータをJSONファイルとして保存する。
5. 処理完了後、コピーされた一時的なスプレッドシートをドライブから完全に削除する。
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any, NotRequired, Self, TypedDict

import google.auth
from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


if TYPE_CHECKING:
    from types import TracebackType

    from googleapiclient.discovery import Resource


# --- 型定義 ---
class ColumnMapping(TypedDict):
    """列マッピングの型定義"""

    key: str
    is_array: NotRequired[bool]


class DataStructure(TypedDict):
    """データ構造設定の型定義"""

    data_start_row: int
    end_check_columns: tuple[str, str]


class Config(TypedDict):
    """設定全体の型定義"""

    source_spreadsheet_id: str
    target_sheet_name: str
    output_filename: str
    data_structure: DataStructure
    column_mapping: dict[str, ColumnMapping]
    ignore_values: set[str]


# --- 設定 (ここを編集してください) ---
CONFIG: Config = {
    # コピー元のスプレッドシートID
    "source_spreadsheet_id": "14Q2A-eeXVDI_Qdb_z_Jwr5IwerDsr5kfRTzRw1J1z18",
    # 読み取り対象のシート(タブ)の名前
    "target_sheet_name": "#非表示_初出",
    # 出力するJSONファイル名
    "output_filename": "imas_music_db.json",
    # データ構造に関する設定
    "data_structure": {
        # データが始まる行番号 (3行目)
        "data_start_row": 3,
        # データ終端を判定する列の範囲 (A列からO列)
        "end_check_columns": ("A", "O"),
    },
    # 列とJSONキーのマッピング
    "column_mapping": {
        # 列文字: { key: JSONキー名, is_array: 配列にするか }
        "B": {"key": "ID"},
        "C": {"key": "曲名"},
        "D": {"key": "よみがな"},
        "E": {"key": "CD題"},
        "F": {"key": "作詞", "is_array": True},
        "G": {"key": "作曲", "is_array": True},
        "H": {"key": "編曲", "is_array": True},
        "I": {"key": "ブランド", "is_array": True},
        "J": {"key": "時間"},
        "K": {"key": "歌唱", "is_array": True},
        "L": {"key": "歌唱", "is_array": True},  # Kと同じキーにマッピング
        "M": {"key": "CD品番"},
        "N": {"key": "CD名"},
        "O": {"key": "発売日"},
    },
    # 空文字として扱う値のセット
    "ignore_values": {"#不明", "未定", "#未定"},
}
# --- 設定ここまで ---

# --- Google API スコープ ---
SCOPES: list[str] = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

# --- 正規表現 ---
# 「歌唱」列の解析用 (例: "ユニット名[メンバー1,メンバー2]")
SINGER_PATTERN = re.compile(r"(.+?)\[(.+?)\]$")
# 「歌唱」列の分割用 (", "で分割するが、[]内は無視)
SINGER_SPLIT_PATTERN = re.compile(r",\s*(?![^[]*\])")


def _col_to_index(col: str) -> int:
    """列文字(A, B, ..)を0-basedのインデックスに変換します"""
    index = 0
    for char in col.upper():
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


class GoogleApiService:
    """Google DriveとSheets APIのサービスを管理するクラス"""

    def __init__(self) -> None:
        """GoogleApiServiceを初期化します"""
        self.drive: Resource | None = None
        self.sheets: Resource | None = None

    def initialize(self) -> bool:
        """APIサービスを初期化します"""
        print("[情報] Google APIサービスの初期化を開始します...")
        try:
            creds, _ = google.auth.default(scopes=SCOPES)
            self.drive = build("drive", "v3", credentials=creds)
            self.sheets = build("sheets", "v4", credentials=creds)
        except DefaultCredentialsError:
            print("[エラー] APIの認証情報の取得に失敗しました。")
            print(
                "  gcloud CLIで 'gcloud auth application-default login' を実行して"
                "ください。",
            )
            return False
        except HttpError as e:
            print(f"[エラー] APIサービスのビルド中にエラーが発生しました: {e}")
            return False
        else:
            print("[成功] APIサービスの初期化に成功しました。")
            return True


class SheetProcessor:
    """スプレッドシートの生データを処理、整形、ソートするクラス"""

    def __init__(self, config: Config) -> None:
        """SheetProcessorを初期化します"""
        self._config = config
        self._col_map = config["column_mapping"]
        self._ignore_values = config["ignore_values"]
        self._array_keys = list(
            dict.fromkeys(
                v["key"] for v in self._col_map.values() if v.get("is_array")
            ),
        )
        self._ordered_keys = list(
            dict.fromkeys(v["key"] for v in self._col_map.values()),
        )

    def process(self, sheet_data: list[list[str]]) -> list[dict[str, Any]]:
        """シートデータを処理し、整形・ソートされたリストを返します"""
        print("\n[情報] データの処理を開始します...")
        data_start_row = self._config["data_structure"]["data_start_row"]
        start_col, end_col = self._config["data_structure"]["end_check_columns"]
        start_col_idx = _col_to_index(start_col)
        end_col_idx = _col_to_index(end_col)

        data_rows = sheet_data[data_start_row - 1 :]
        processed_list: list[dict[str, Any]] = []

        for row in data_rows:
            # 指定範囲の列がすべて空ならデータ終端とみなす
            if not any(cell.strip() for cell in row[start_col_idx : end_col_idx + 1]):
                break
            record = self._process_row(row)
            processed_list.append(record)

        # IDで降順ソート
        processed_list.sort(key=self._sort_key, reverse=True)

        print(f"[情報] {len(processed_list)}件のデータを取得し、ソートしました。")
        return processed_list

    def _process_row(self, row: list[str]) -> dict[str, Any]:
        """単一の行データを処理します"""
        record: dict[str, Any] = {
            key: [] if key in self._array_keys else "" for key in self._ordered_keys
        }

        for col_letter, mapping in self._col_map.items():
            col_idx = _col_to_index(col_letter)
            key = mapping["key"]
            is_array = mapping.get("is_array", False)
            value = row[col_idx].strip() if col_idx < len(row) and row[col_idx] else ""

            if not value or value in self._ignore_values:
                continue

            if is_array:
                # '歌唱' 列の特殊処理
                if key == "歌唱":
                    new_values = self._parse_singers(value)
                # 'ブランド' 列の特殊処理
                elif key == "ブランド" and "越境" in value:
                    new_values = [
                        v.strip()
                        for v in value.split(":")
                        if v.strip() and v.strip() != "越境"
                    ]
                else:
                    new_values = [v.strip() for v in value.split(",") if v.strip()]
                record[key].extend(new_values)
            else:
                record[key] = value

        # 配列キーの重複を削除
        for key in self._array_keys:
            if record.get(key):
                seen = set()
                record[key] = [x for x in record[key] if not (x in seen or seen.add(x))]

        return record

    @staticmethod
    def _parse_singers(value: str) -> list[str]:
        """「歌唱」列の特殊な形式を解析し、名前のリストを返します"""
        new_values = []
        parts = SINGER_SPLIT_PATTERN.split(value)
        for part_item in parts:
            stripped_part = part_item.strip()
            if not stripped_part:
                continue

            match = SINGER_PATTERN.match(stripped_part)
            if match:
                unit, members_str = match.groups()
                new_values.append(unit.strip())
                new_values.extend(
                    m.strip() for m in members_str.split(",") if m.strip()
                )
            else:
                new_values.append(stripped_part)
        return new_values

    @staticmethod
    def _sort_key(item: dict[str, Any]) -> int:
        """ソート用のキーを返します"""
        try:
            return int(item.get("ID", 0))
        except (ValueError, TypeError):
            return 0


class SheetCopier:
    """スプレッドシートのコピーと削除を管理するコンテキストマネージャ"""

    def __init__(self, drive_service: Resource, source_id: str) -> None:
        """SheetCopierを初期化します"""
        self._drive_service = drive_service
        self._source_id = source_id
        self.copied_file_id: str | None = None

    def __enter__(self) -> Self:
        """コンテキストに入り、スプレッドシートをコピーします"""
        print(
            f"\n[情報] スプレッドシート (ID: {self._source_id}) のコピーを"
            "開始します...",
        )
        copy_title = f"tmp_copy_{uuid.uuid4().hex}"
        body = {"name": copy_title}
        try:
            response = (
                self._drive_service.files()  # type: ignore[attr-defined]
                .copy(fileId=self._source_id, body=body, fields="id")
                .execute()
            )
            self.copied_file_id = response.get("id")
            if self.copied_file_id:
                print(
                    f"[成功] スプレッドシートをコピーしました。"
                    f"新しいID: {self.copied_file_id}",
                )
                return self

            # HttpErrorを直接生成するのではなく、より適切な例外を使用
            error_message = "コピー後のファイルIDが取得できませんでした。"
            raise ValueError(error_message)
        except HttpError as e:
            print(f"[エラー] スプレッドシートのコピーに失敗しました: {e}")
            raise

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        """コンテキストを抜け、一時ファイルを削除します"""
        if self.copied_file_id:
            print(f"\n[情報] 一時ファイル (ID: {self.copied_file_id}) を削除します...")
            try:
                self._drive_service.files().delete(fileId=self.copied_file_id).execute()  # type: ignore[attr-defined]
                print("[成功] 一時ファイルを削除しました。")
            except HttpError as e:
                print(f"[エラー] 一時ファイルの削除に失敗しました: {e}")


def main() -> None:
    """メイン処理"""
    print("--- スプレッドシートのデータ取得処理を開始します ---")

    # 1. APIサービス初期化
    api_services = GoogleApiService()
    if (
        not api_services.initialize()
        or not api_services.drive
        or not api_services.sheets
    ):
        return

    try:
        # 2. スプレッドシートを一時的にコピー (コンテキストマネージャ使用)
        with SheetCopier(api_services.drive, CONFIG["source_spreadsheet_id"]) as copier:
            if not copier.copied_file_id:
                return

            # 3. シートからデータを取得
            sheet_name = CONFIG["target_sheet_name"]
            print(f"\n[情報] シート '{sheet_name}' からデータを取得します...")
            try:
                result = (
                    api_services.sheets.spreadsheets()  # type: ignore[attr-defined]
                    .values()
                    .get(
                        spreadsheetId=copier.copied_file_id,
                        range=f"'{sheet_name}'",
                        valueRenderOption="FORMATTED_VALUE",
                    )
                    .execute()
                )
            except HttpError as e:
                print(f"[エラー] シートデータの取得に失敗しました: {e}")
                return

            sheet_data = result.get("values", [])
            data_start_row = CONFIG["data_structure"]["data_start_row"]
            if not sheet_data or len(sheet_data) < data_start_row:
                print(
                    f"[警告] {data_start_row}行目以降のデータが見つかりませんでした。",
                )
                return

            # 4. データの処理と整形
            processor = SheetProcessor(CONFIG)
            processed_data = processor.process(sheet_data)

            # 5. JSONに変換
            json_output = json.dumps(
                processed_data,
                ensure_ascii=False,
                separators=(",", ":"),
            )

            # 6. ファイルに保存
            output_path = Path(CONFIG["output_filename"])
            output_path.write_text(json_output, encoding="utf-8")
            print(f"\n[成功] JSONデータを {output_path.resolve()} に保存しました。")

    except (OSError, HttpError, ValueError) as e:
        print(f"\n[エラー] メイン処理で予期せぬエラーが発生しました: {e}")

    except Exception as e:  # noqa: BLE001
        print(
            f"\n[エラー] 予期せぬ重大なエラーが発生しました ({type(e).__name__}): {e}",
        )
    finally:
        print("\n--- 全ての処理が完了しました ---")


if __name__ == "__main__":
    main()
