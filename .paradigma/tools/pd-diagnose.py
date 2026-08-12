#!/usr/bin/env python3
"""Compatibility adapter for package-backed Harness diagnosis."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from _bootstrap import ensure_package

ensure_package()

from paradigma.application.diagnosis import (
    detect_version as _detect_version,
    diagnose_outcome,
    online_diagnose_outcome,
    upstream_version as _read_upstream_version,
)
from paradigma.errors import ParadigmaError, ParseFailure
from paradigma.cli.upstream import GitUpstreamResolver


def _format_human(data: dict) -> str:
    separator = "=" * 62
    version_match = data["version_match"]
    status = (
        "[OK] 版本一致"
        if version_match is True
        else "[!] 版本不一致，需要更新"
        if version_match is False
        else "[INFO] 远程 ref 没有可比较的发行版本"
    )
    lines = [
        separator,
        "  Paradigma Harness 诊断报告",
        f"  项目: {data['project_path']}",
        f"  检测版本: {data['detected_version']}",
        f"  上游版本: {data['upstream_version']}",
        f"  状态: {status}",
        separator,
        "",
    ]
    if data.get("online"):
        online = data["online"]
        lines[2:2] = [
            f"  比较来源: {data['comparison_source']}",
            f"  远程 ref: {online['resolved_ref']}",
            f"  远程 commit: {online['commit']}",
            f"  本地 freshness: {online['freshness']}",
        ]
    gaps = data["gaps"]
    if not gaps:
        lines.append("[OK] 未检测到差距。项目与上游 Paradigma 一致。")
        return "\n".join(lines)
    labels = {
        "structure": "目录结构",
        "tools": "工具链",
        "schema": "Schema",
        "config": "配置",
        "protocol": "协议文件",
        "upstream": "上游来源",
    }
    icons = {"error": "[ERR]", "warning": "[WARN]", "info": "[INFO]"}
    prefixes = {"missing": "-", "mismatch": "~", "outdated": "~", "extra": "+"}
    for category in ("structure", "tools", "schema", "config", "protocol", "upstream"):
        category_gaps = [item for item in gaps if item["category"] == category]
        if not category_gaps:
            continue
        counts: dict[str, int] = {}
        for item in category_gaps:
            counts[item["severity"]] = counts.get(item["severity"], 0) + 1
        summary = ", ".join(
            f"{icons.get(severity, severity)} x{count}"
            for severity, count in sorted(counts.items())
        )
        lines.append(f"{summary}  {labels.get(category, category)} ({len(category_gaps)} 项)")
        for item in category_gaps:
            lines.append(f"  {prefixes.get(item['kind'], '?')} {item['item']}")
            if item["detail"]:
                lines.append(f"     {item['detail']}")
        lines.append("")
    result = data["summary"]
    lines.extend(
        [
            separator,
            f"  合计: {result['errors']} errors, {result['warnings']} warnings, "
            f"{result['infos']} infos",
            "",
        ]
    )
    if result["errors"]:
        lines.extend(
            [
                "建议操作:",
                "  1. 审查上述结构、工具、配置和协议差距",
                "  2. 完成后运行 pd check 校验",
                "  3. 更新 installed_distribution_version",
            ]
        )
    elif result["warnings"]:
        lines.append("建议: 从上游更新缺失或过时的工具和 Schema。")
    lines.append(separator)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream")
    parser.add_argument("--online", action="store_true")
    parser.add_argument("--remote-url")
    parser.add_argument("--channel", choices=("stable", "main"))
    parser.add_argument("--ref", dest="upstream_ref")
    parser.add_argument("--project", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check-version", action="store_true")
    args = parser.parse_args()
    project = Path(args.project).resolve()
    upstream = Path(args.upstream).resolve() if args.upstream else None
    if upstream is not None and not upstream.is_dir():
        print(f"ERROR: upstream path does not exist: {upstream}", file=sys.stderr)
        return 2
    if not project.is_dir():
        print(f"ERROR: project path does not exist: {project}", file=sys.stderr)
        return 2
    if not args.online and upstream is None:
        print("ERROR: diagnose requires --upstream <path> or --online", file=sys.stderr)
        return 2
    if not args.online and any(
        value is not None for value in (args.remote_url, args.channel, args.upstream_ref)
    ):
        print("ERROR: remote options require --online", file=sys.stderr)
        return 2
    try:
        if args.online:
            outcome = online_diagnose_outcome(
                project,
                upstream=upstream,
                repository_url=args.remote_url,
                channel=args.channel,
                requested_ref=args.upstream_ref,
                resolver=GitUpstreamResolver(),
            )
            if args.check_version:
                return 0 if outcome.exit_code == 0 and outcome.data["version_match"] is True else 1
        elif args.check_version:
            assert upstream is not None
            return 0 if _detect_version(project) == _read_upstream_version(upstream) else 1
        else:
            assert upstream is not None
            outcome = diagnose_outcome(project, upstream)
    except (ParadigmaError, ParseFailure) as error:
        diagnostic = getattr(error, "diagnostic", None)
        if args.json:
            payload = (
                diagnostic.to_dict()
                if diagnostic is not None
                else {"code": error.code, "message": str(error)}
            )
            print(json.dumps({"error": payload}, indent=2, ensure_ascii=False))
        else:
            print(f"ERROR: {error.format()}", file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(outcome.data, indent=2, ensure_ascii=False))
    else:
        print(_format_human(outcome.data))
    return outcome.exit_code


if __name__ == "__main__":
    sys.exit(main())
