import csv
import json
import re
import requests

# --- グローバル定数定義 ---
# 取得先のシートURL (固定)
TARGET_SHEET_URL = "https://docs.google.com/spreadsheets/d/14Q2A-eeXVDI_Qdb_z_Jwr5IwerDsr5kfRTzRw1J1z18/edit?gid=1025592751#gid=1025592751"
# 出力ファイル名 (固定)
OUTPUT_FILENAME = "imas_music_db.json"

# --- 固定パラメータ定義 (関数内で使用) ---
# 行インデックス (0始まり)
HEADER_ROW_INDEX = 6  # 7行目に相当
DATA_START_ROW_INDEX = 8  # 9行目に相当

# JSONに含める対象列のインデックス (0始まり)
# C列=2, D列=3, F列=5, G列=6, H列=7, I列=8, J列=9, K列=10, N列=13, O列=14
TARGET_COLUMN_INDICES = [2, 3, 5, 6, 7, 8, 9, 10, 13, 14]

# データ終了判定に使用する列範囲 (C列～O列)
# この範囲の全てのセルが空になった時点でデータ終了とみなす
DATA_END_CHECK_COLUMN_START_INDEX = 2  # C列に相当
DATA_END_CHECK_COLUMN_END_INDEX = 14  # O列に相当


def generate_json_from_public_spreadsheet_table(sheet_url: str) -> str | None:
    """
    公開されているGoogleスプレッドシートのURLから、指定された列のデータを取得し、
    JSON文字列を生成します。
    ヘッダー行: HEADER_ROW_INDEX で指定された行。TARGET_COLUMN_INDICES で指定された列のみ対象。
                ヘッダー名が空文字または空白のみの列は無視されます。
    データ行: DATA_START_ROW_INDEX で指定された行以降。無視されなかったヘッダー列に対応するデータのみを処理。
                値が空文字または空白のみの項目は、生成されるJSONオブジェクトから除外されます。
                DATA_END_CHECK_COLUMN_START_INDEX から DATA_END_CHECK_COLUMN_END_INDEX の列の範囲が
                全て空になった時点でデータ終了とみなします。

    Args:
        sheet_url: Googleスプレッドシートの公開URL。

    Returns:
        成功した場合はJSON文字列、失敗した場合はNoneを返します。
    """
    sheet_id_match = re.search(r"/spreadsheets/d/([^/]+)", sheet_url)
    if not sheet_id_match:
        print("エラー: URLからシートIDを抽出できませんでした。")
        return None
    sheet_id = sheet_id_match.group(1)

    gid_match = re.search(r"[#&]gid=([^&]+)", sheet_url)
    gid = gid_match.group(1) if gid_match else "0"

    csv_export_url = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    )
    print(f"CSVエクスポートURL: {csv_export_url}")

    try:
        response = requests.get(csv_export_url, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        csv_text = response.text
    except requests.exceptions.RequestException as e:
        print(f"エラー: スプレッドシートの取得に失敗しました - {e}")
        return None
    except Exception as e:  # pylint: disable=broad-except
        print(f"予期せぬエラーが発生しました（リクエスト処理中）: {e}")
        return None

    try:
        if csv_text.startswith("\ufeff"):
            csv_text = csv_text[1:]
        if not csv_text.strip():
            print("警告: スプレッドシートが空か、内容がありません。")
            return json.dumps([], indent=2, ensure_ascii=False)

        lines = csv_text.splitlines()
        all_rows_raw = list(csv.reader(lines))

        if len(all_rows_raw) <= HEADER_ROW_INDEX:
            print(
                f"エラー: 指定されたヘッダー行 ({HEADER_ROW_INDEX + 1}行目) がシートに存在しません。"
            )
            return None

        header_candidate_row_full = all_rows_raw[HEADER_ROW_INDEX]

        valid_headers = []  # (ヘッダー名, 元のシートでの列インデックス) のタプルを格納
        for col_idx in TARGET_COLUMN_INDICES:
            if col_idx < len(header_candidate_row_full):
                h_val = header_candidate_row_full[col_idx]
                stripped_h_val = h_val.strip()
                if stripped_h_val:  # strip後が空文字でない場合のみ有効なヘッダーとする
                    valid_headers.append((stripped_h_val, col_idx))
            # else: ヘッダー行に対象列が存在しない場合はスキップ

        if not valid_headers:
            print("警告: 指定された対象列に有効なヘッダー名が見つかりませんでした。")
            return json.dumps([], indent=2, ensure_ascii=False)

        data_list = []
        if len(all_rows_raw) > DATA_START_ROW_INDEX:
            for row_index in range(DATA_START_ROW_INDEX, len(all_rows_raw)):
                current_data_row_full = all_rows_raw[row_index]

                # データ終了判定: C列～O列の範囲のセルが全てstripして空かチェック
                # この範囲の列数が不足している場合も考慮
                start_check = DATA_END_CHECK_COLUMN_START_INDEX
                end_check = DATA_END_CHECK_COLUMN_END_INDEX + 1  # スライス用に+1

                # データ行がデータ終了判定範囲より短い場合は、存在する範囲でチェック
                actual_end_check = min(end_check, len(current_data_row_full))

                if (
                    start_check < actual_end_check
                ):  # 判定範囲がデータ行に存在する場合のみチェック
                    target_columns_for_emptiness_check = current_data_row_full[
                        start_check:actual_end_check
                    ]
                    # 足りない分は空とみなすため、元の範囲の長さで空文字列リストを作成し、それで判定
                    full_range_check_values = [""] * (
                        DATA_END_CHECK_COLUMN_END_INDEX
                        - DATA_END_CHECK_COLUMN_START_INDEX
                        + 1
                    )
                    for i, val in enumerate(target_columns_for_emptiness_check):
                        if i < len(full_range_check_values):  # 念のため範囲チェック
                            full_range_check_values[i] = val
                else:  # データ行が短すぎて判定範囲が全くない場合は、空とみなさない（処理を続ける）
                    full_range_check_values = [
                        "dummy"
                    ]  # 空ではないと判定させるためのダミー

                if not any(val.strip() for val in full_range_check_values):
                    break

                record = {}
                # 有効なヘッダーに対応するデータのみを処理
                for header_name, original_sheet_col_idx in valid_headers:
                    if original_sheet_col_idx < len(current_data_row_full):
                        value = current_data_row_full[original_sheet_col_idx]
                        if value.strip():  # 値をstripして空文字でない場合のみ項目を追加
                            record[header_name] = value  # 元の値 (stripする前) を格納

                data_list.append(record)

        return json.dumps(data_list, indent=2, ensure_ascii=False)

    except csv.Error as e:
        print(f"エラー: CSVデータの解析に失敗しました - {e}")
        return None
    except Exception as e:  # pylint: disable=broad-except
        print(f"予期せぬエラーが発生しました（データ処理中）: {e}")
        return None


if __name__ == "__main__":
    print(f"--- スプレッドシートの指定範囲をJSON化 ({TARGET_SHEET_URL}) ---")
    json_output = generate_json_from_public_spreadsheet_table(TARGET_SHEET_URL)

    if json_output:
        try:
            with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"\nJSONデータを {OUTPUT_FILENAME} に保存しました。")
        except IOError as e:
            print(f"ファイルへの保存に失敗しました: {e}")
    else:
        print("JSONデータを生成できませんでした。")
