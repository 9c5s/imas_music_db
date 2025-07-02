"""Googleスプレッドシートをコピーし、指定のシートからデータを取得・整形する

このスクリプトは以下の手順を自動で実行する:
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
import yaml
from google.auth.exceptions import DefaultCredentialsError
from googleapiclient.discovery import build  # type: ignore[import]
from googleapiclient.errors import HttpError


if TYPE_CHECKING:
    from types import TracebackType

    from googleapiclient._apis.drive.v3.resources import (  # type: ignore[import]
        DriveResource,
    )
    from googleapiclient._apis.sheets.v4.resources import (  # type: ignore[import]
        SheetsResource,
    )


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


# --- 設定読み込み機能 ---
def load_config(config_path: str = "config/sheet_config.yml") -> Config:
    """YAML設定ファイルを読み込み、Config型として返す

    Args:
        config_path: 設定ファイルのパス(デフォルト: config/sheet_config.yml)

    Returns:
        Config: 読み込んだ設定データ

    Raises:
        FileNotFoundError: 設定ファイルが見つからない場合
        yaml.YAMLError: YAML解析エラーの場合
        KeyError: 必須キーが不足している場合
        ValueError: 設定値が不正な場合
    """
    config_file = Path(config_path)

    if not config_file.exists():
        error_message = f"設定ファイルが見つかりません: {config_file.resolve()}"
        raise FileNotFoundError(error_message)

    try:
        with config_file.open("r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        error_message = f"YAML解析エラー: {e}"
        raise yaml.YAMLError(error_message) from e

    # YAML構造をConfig型に変換
    try:
        config: Config = {
            "source_spreadsheet_id": yaml_data["spreadsheet"]["source_id"],
            "target_sheet_name": yaml_data["spreadsheet"]["target_sheet"],
            "output_filename": yaml_data["output"]["filename"],
            "data_structure": {
                "data_start_row": yaml_data["data_structure"]["data_start_row"],
                # YAMLの辞書形式をtupleに変換
                "end_check_columns": (
                    yaml_data["data_structure"]["end_check_columns"]["start"],
                    yaml_data["data_structure"]["end_check_columns"]["end"],
                ),
            },
            "column_mapping": {
                col: ColumnMapping(
                    key=mapping["key"],
                    **(
                        {}
                        if "is_array" not in mapping
                        else {"is_array": mapping["is_array"]}
                    ),
                )
                for col, mapping in yaml_data["column_mapping"].items()
            },
            # YAMLのリストをsetに変換
            "ignore_values": set(yaml_data["ignore_values"]),
        }
    except KeyError as e:
        error_message = f"設定ファイルに必須キーが不足しています: {e}"
        raise KeyError(error_message) from e
    except (TypeError, ValueError) as e:
        error_message = f"設定値が不正です: {e}"
        raise ValueError(error_message) from e

    return config


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
    """列文字(A, B, ..)を0-basedのインデックスに変換する"""
    index = 0
    for char in col.upper():
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


class GoogleApiService:
    """Google DriveとSheets APIのサービスを管理するクラス"""

    def __init__(self) -> None:
        """GoogleApiServiceを初期化する"""
        self.drive: DriveResource | None = None
        self.sheets: SheetsResource | None = None

    def initialize(self) -> bool:
        """APIサービスを初期化する"""
        print("[情報] Google APIサービスの初期化を開始します...")
        try:
            auth_result = google.auth.default(scopes=SCOPES)
            creds = auth_result[0]  # type: ignore[misc]
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
        """SheetProcessorを初期化する"""
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
        """シートデータを処理し、整形・ソートされたリストを返す"""
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
        """単一の行データを処理する"""
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
                seen: set[str] = set()
                record[key] = [x for x in record[key] if not (x in seen or seen.add(x))]

        return record

    @staticmethod
    def _parse_singers(value: str) -> list[str]:
        """「歌唱」列の特殊な形式を解析し、名前のリストを返す"""
        new_values: list[str] = []
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
        """ソート用のキーを返す"""
        try:
            return int(item.get("ID", 0))
        except (ValueError, TypeError):
            return 0


class SheetCopier:
    """スプレッドシートのコピーと削除を管理するコンテキストマネージャ"""

    def __init__(self, drive_service: DriveResource, source_id: str) -> None:
        """SheetCopierを初期化する"""
        self._drive_service = drive_service
        self._source_id = source_id
        self.copied_file_id: str | None = None

    def __enter__(self) -> Self:
        """コンテキストに入り、スプレッドシートをコピーする"""
        print(
            f"\n[情報] スプレッドシート (ID: {self._source_id}) のコピーを"
            "開始します...",
        )
        copy_title = f"tmp_copy_{uuid.uuid4().hex}"
        body = {"name": copy_title}
        try:
            response = (
                self._drive_service.files()  # type: ignore[attr-defined]
                .copy(fileId=self._source_id, body=body, fields="id")  # type: ignore[arg-type]
                .execute()
            )
            self.copied_file_id = response.get("id")
            if self.copied_file_id:
                print(
                    f"[成功] スプレッドシートをコピーしました。"
                    f"新しいID: {self.copied_file_id}",
                )
                return self

            error_message = "コピー後のファイルIDが取得できませんでした。"
            raise ValueError(error_message)
        except HttpError as e:
            print(f"[エラー] スプレッドシートのコピーに失敗しました: {e}")
            raise

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc_val: BaseException | None,
        _exc_tb: TracebackType | None,
    ) -> None:
        """コンテキストを抜け、一時ファイルを削除する"""
        if self.copied_file_id:
            print(f"\n[情報] 一時ファイル (ID: {self.copied_file_id}) を削除します...")
            try:
                self._drive_service.files().delete(fileId=self.copied_file_id).execute()
                print("[成功] 一時ファイルを削除しました。")
            except HttpError as e:
                print(f"[エラー] 一時ファイルの削除に失敗しました: {e}")


def load_and_validate_config() -> Config | None:
    """設定ファイルの読み込みと検証を行う"""
    try:
        config = load_config()
        print("[成功] 設定ファイルを読み込みました。")
    except (FileNotFoundError, yaml.YAMLError, KeyError, ValueError) as e:
        print(f"[エラー] 設定ファイルの読み込みに失敗しました: {e}")
        return None
    else:
        return config


def initialize_api_services() -> GoogleApiService | None:
    """Google APIサービスの初期化を行う"""
    api_services = GoogleApiService()
    if (
        not api_services.initialize()
        or not api_services.drive
        or not api_services.sheets
    ):
        return None
    return api_services


def fetch_sheet_data(
    api_services: GoogleApiService, config: Config, copier: SheetCopier
) -> list[list[str]] | None:
    """スプレッドシートからデータを取得する"""
    if not copier.copied_file_id:
        return None

    sheet_name = config["target_sheet_name"]
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
        return None

    sheet_data = result.get("values", [])
    data_start_row = config["data_structure"]["data_start_row"]
    if not sheet_data or len(sheet_data) < data_start_row:
        print(
            f"[警告] {data_start_row}行目以降のデータが見つかりませんでした。",
        )
        return None

    return sheet_data


def process_and_save_data(config: Config, sheet_data: list[list[str]]) -> None:
    """データの処理とJSONファイルへの保存を行う"""
    processor = SheetProcessor(config)
    processed_data = processor.process(sheet_data)

    json_output = json.dumps(
        processed_data,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    output_path = Path(config["output_filename"])
    output_path.write_text(json_output, encoding="utf-8")
    print(f"\n[成功] JSONデータを {output_path.resolve()} に保存しました。")


def main() -> None:
    """メイン処理"""
    print("--- スプレッドシートのデータ取得処理を開始します ---")

    config = load_and_validate_config()
    if not config:
        return

    api_services = initialize_api_services()
    if not api_services:
        return

    # 型チェッカー向け: api_servicesがNoneでない場合、driveとsheetsもNoneではない
    assert api_services.drive is not None  # noqa: S101
    assert api_services.sheets is not None  # noqa: S101

    try:
        with SheetCopier(api_services.drive, config["source_spreadsheet_id"]) as copier:
            sheet_data = fetch_sheet_data(api_services, config, copier)
            if not sheet_data:
                return

            process_and_save_data(config, sheet_data)

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
