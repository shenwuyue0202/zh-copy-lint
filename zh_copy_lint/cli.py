"""Command line interface for zh-copy-lint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List

from .rules import RULE_DESCRIPTIONS, fix_text, lint_text

DEFAULT_SUFFIXES = {".md", ".markdown", ".txt"}


def iter_files(paths: Iterable[str]) -> Iterable[Path]:
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and child.suffix.lower() in DEFAULT_SUFFIXES:
                    yield child
        elif path.is_file():
            yield path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zh-copy-lint",
        description="检查中文文稿里常见的排版问题：中英文空格、半角标点、省略号、破折号等。",
    )
    parser.add_argument("paths", nargs="*", default=["."], help="要检查的文件或目录，默认当前目录")
    parser.add_argument("--fix", action="store_true", help="自动修复可修复的问题并写回文件")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="输出格式")
    parser.add_argument("--ignore", action="append", default=[], metavar="RULE", help="忽略指定规则，可重复使用")
    parser.add_argument(
        "--cjk-space",
        choices=("keep", "none"),
        default="keep",
        help="中英文之间的空格：keep 保留（默认），none 视为问题并要求删掉",
    )
    parser.add_argument("--list-rules", action="store_true", help="列出全部规则后退出")
    parser.add_argument("--strict", action="store_true", help="警告也按错误处理（当前版本所有问题都计入退出码）")
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_rules:
        for rule, desc in sorted(RULE_DESCRIPTIONS.items()):
            print(f"{rule}  {desc}")
        return 0

    files = list(iter_files(args.paths or ["."]))
    if not files:
        print("没有找到可检查的文件", file=sys.stderr)
        return 2

    total = 0
    payload = []
    for path in files:
        original = path.read_text(encoding="utf-8")
        if args.fix:
            fixed = fix_text(original, cjk_space=args.cjk_space)
            if fixed != original:
                path.write_text(fixed, encoding="utf-8")
                original = fixed
        for issue in lint_text(original, str(path), ignore=args.ignore, cjk_space=args.cjk_space):
            total += 1
            if args.format == "text":
                print(issue.format())
            else:
                payload.append(
                    {
                        "path": issue.path,
                        "line": issue.line,
                        "col": issue.col,
                        "rule": issue.rule,
                        "message": issue.message,
                        "fixable": issue.fixable,
                    }
                )

    if args.format == "json":
        print(json.dumps({"issues": payload, "count": total}, ensure_ascii=False, indent=2))

    if total and args.format == "text":
        print(f"\n共 {total} 处问题", file=sys.stderr)
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
