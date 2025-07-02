#!/usr/bin/env python3
"""ShellCheckのJSON出力をSARIF 2.1.0形式に変換するスクリプト

使用方法:
    python convert_shellcheck_to_sarif.py input.json output.sarif
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def convert_shellcheck_to_sarif(input_file: str, output_file: str) -> None:
    """ShellCheckのJSON出力をSARIF 2.1.0形式に変換"""
    try:
        shellcheck_results = json.loads(Path(input_file).read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        shellcheck_results = []

    sarif_report = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "ShellCheck",
                        "version": "0.10.0",
                        "informationUri": "https://github.com/koalaman/shellcheck",
                        "semanticVersion": "0.10.0",
                        "rules": []
                    }
                },
                "results": [],
                "columnKind": "utf16CodeUnits"
            }
        ]
    }

    # ルールとアラートを処理
    rules_map = {}
    results = []

    for finding in shellcheck_results:
        rule_id = f"SC{finding.get('code', '0000')}"

        # ルール情報を追加
        if rule_id not in rules_map:
            rules_map[rule_id] = {
                "id": rule_id,
                "shortDescription": {
                    "text": finding.get("message", "ShellCheck finding")
                },
                "fullDescription": {
                    "text": finding.get("message", "ShellCheck finding")
                },
                "helpUri": f"https://www.shellcheck.net/wiki/{rule_id}",
                "properties": {
                    "category": "security"
                }
            }

        # レベルをSARIFレベルに変換
        level_map = {
            "error": "error",
            "warning": "warning",
            "info": "note",
            "style": "note"
        }
        level = level_map.get(finding.get("level", "warning"), "warning")

        # 結果を追加
        result = {
            "ruleId": rule_id,
            "level": level,
            "message": {
                "text": finding.get("message", "ShellCheck finding")
            },
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": finding.get("file", "unknown")
                        },
                        "region": {
                            "startLine": finding.get("line", 1),
                            "startColumn": finding.get("column", 1),
                            "endLine": finding.get(
                                "endLine", finding.get("line", 1)
                            ),
                            "endColumn": finding.get(
                                "endColumn", finding.get("column", 1)
                            )
                        }
                    }
                }
            ]
        }
        results.append(result)

    # ルールをツールドライバーに追加
    sarif_report["runs"][0]["tool"]["driver"]["rules"] = list(rules_map.values())
    sarif_report["runs"][0]["results"] = results

    # SARIF結果を出力
    Path(output_file).write_text(json.dumps(sarif_report, indent=2))

    print(f"Converted {len(results)} findings to SARIF format")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_shellcheck_to_sarif.py input.json output.sarif")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    convert_shellcheck_to_sarif(input_file, output_file)
