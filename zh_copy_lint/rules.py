"""Rule definitions for zh-copy-lint.

Every rule is a small function that receives one physical line plus a small
context object and yields ``Issue`` records.  Rules never mutate the line;
fixing is done by the ``FIXES`` table so that ``--fix`` stays predictable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Pattern


@dataclass(frozen=True)
class Issue:
    path: str
    line: int
    col: int
    rule: str
    message: str
    fixable: bool = False

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: {self.rule} {self.message}"


CJK = r"\u4e00-\u9fff\u3400-\u4dbf"
# Characters that end a clause and need the full-width form in Chinese copy.
HALF_TO_FULL = {",": "，", ".": "。", ";": "；", ":": "：", "!": "！", "?": "？"}


@dataclass
class Context:
    """Per-file state so rules can skip fenced code blocks."""

    in_fence: bool = False
    fence_marker: str = ""


@dataclass
class Options:
    """Behaviour switches that change which rules apply.

    ``cjk_space="keep"`` (the default) leaves the spacing between Chinese and
    Latin text alone, because adding that space is a common and accepted
    convention. ``cjk_space="none"`` turns on C001 and strips it instead.
    """

    cjk_space: str = "keep"


def strip_code_spans(line: str) -> str:
    """Blank out inline code and URLs so rules do not lint inside them.

    The padding character is NUL rather than a space: NUL is neither
    whitespace, CJK nor Latin, so it cannot itself trigger a spacing rule
    while keeping every later column number intact.
    """
    line = re.sub(r"`[^`]*`", lambda m: "\x00" * len(m.group(0)), line)
    line = re.sub(r"https?://\S+", lambda m: "\x00" * len(m.group(0)), line)
    return line


def _iter_matches(pattern: Pattern[str], text: str) -> Iterator[re.Match]:
    return pattern.finditer(text)


# --- individual rules -------------------------------------------------------

SPACE_BETWEEN_CJK_AND_LATIN = re.compile(
    rf"(?<=[{CJK}])[ \t]+(?=[A-Za-z0-9])|(?<=[A-Za-z0-9])[ \t]+(?=[{CJK}])"
)
SPACE_BETWEEN_CJK = re.compile(rf"(?<=[{CJK}])[ \t]+(?=[{CJK}])")
HALF_PUNCT = re.compile(r"(?<![\d.,])[,;:!?](?![\d/\\])")
HALF_PERIOD = re.compile(rf"(?<=[{CJK}])\s*\.(?!\d)")
ELLIPSIS = re.compile(r"(?<!\.)\.\.\.(?!\.)|。{3,}")
DASH = re.compile(r"(?<!-)--(?!-)|(?<!—)—(?!—)")
REPEATED_PUNCT = re.compile(r"([？！。，、；：])\1+")
HALF_PAREN_WITH_CJK = re.compile(rf"\(([^()]*[{CJK}][^()]*)\)")
NUM_UNIT_SPACE = re.compile(r"(?<=\d)[ \t]+(℃|°C|%|kg|g|mm|cm|mAh|Wh|W|Hz|GHz|GB|MB|TB|ms|km)(?![A-Za-z])")
CJK_CHAR_THEN_EOL = re.compile(rf"[{CJK}）】」』”’]$")
CJK_ANY = re.compile(rf"[{CJK}]")


def check_line(
    line: str, ctx: Context, opts: Optional[Options] = None
) -> List[tuple[str, int, str, bool]]:
    """Return ``(rule_id, column, message, fixable)`` tuples for one line."""
    opts = opts or Options()
    stripped = line.strip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        marker = stripped[:3]
        ctx.in_fence = not ctx.in_fence
        ctx.fence_marker = marker
        return []
    if ctx.in_fence:
        return []
    if stripped.startswith("#") or stripped.startswith(">") or re.match(r"^([-*+]|\d+\.)\s+", stripped):
        # Headings, quotes and list items are allowed to end without a full stop.
        allow_no_period = True
    else:
        allow_no_period = False

    text = strip_code_spans(line)
    found: List[tuple[str, int, str, bool]] = []

    if opts.cjk_space == "none":
        for m in _iter_matches(SPACE_BETWEEN_CJK_AND_LATIN, text):
            found.append(("C001", m.start() + 1, "中文与英文/数字之间不应有空格", True))

    for m in _iter_matches(SPACE_BETWEEN_CJK, text):
        found.append(("C002", m.start() + 1, "中文字符之间不应有空格", True))

    if CJK_ANY.search(text):
        for m in _iter_matches(HALF_PUNCT, text):
            punct = m.group(0)
            found.append(("C003", m.start() + 1, f"中文句子里应使用全角标点：{punct} -> {HALF_TO_FULL[punct]}", True))
        for m in _iter_matches(HALF_PERIOD, text):
            found.append(("C003", m.start() + 1, "中文句子里应使用全角句号：. -> 。", True))

    for m in _iter_matches(ELLIPSIS, text):
        found.append(("C004", m.start() + 1, "省略号应写成……", True))

    for m in _iter_matches(DASH, text):
        found.append(("C005", m.start() + 1, "破折号应写成——", True))

    for m in _iter_matches(REPEATED_PUNCT, text):
        found.append(("C006", m.start() + 1, "重复标点只保留一个", True))

    for m in _iter_matches(HALF_PAREN_WITH_CJK, text):
        found.append(("C007", m.start() + 1, "含中文的括号应使用全角（）", True))

    for m in _iter_matches(NUM_UNIT_SPACE, text):
        found.append(("C008", m.start() + 1, "数字与单位之间不留空格", True))

    body = line.rstrip()
    if (
        not allow_no_period
        and body
        and not body.endswith(("。", "！", "？", "：", "；", "）", "」", "』", "”", "…", "|", "\\"))
        and CJK_CHAR_THEN_EOL.search(body)
        and len(body) > 12
    ):
        found.append(("C009", len(body), "段末缺少句末标点", False))

    if re.search(r"、、", text):
        found.append(("C010", text.index("、、") + 1, "顿号连用，检查是否漏了内容", False))

    return found


# --- fixes ------------------------------------------------------------------

def fix_line(line: str, ctx: Context, opts: Optional[Options] = None) -> str:
    opts = opts or Options()
    stripped = line.strip()
    if stripped.startswith("```") or stripped.startswith("~~~"):
        ctx.in_fence = not ctx.in_fence
        return line
    if ctx.in_fence:
        return line

    # Keep inline code and URLs out of the rewrite by splicing them back in.
    protected: List[str] = []

    def stash(match: re.Match) -> str:
        protected.append(match.group(0))
        return f"\x00{len(protected) - 1}\x00"

    work = re.sub(r"`[^`]*`|https?://\S+", stash, line)

    work = SPACE_BETWEEN_CJK.sub("", work)
    if opts.cjk_space == "none":
        work = SPACE_BETWEEN_CJK_AND_LATIN.sub("", work)

    if CJK_ANY.search(work):
        work = HALF_PUNCT.sub(lambda m: HALF_TO_FULL[m.group(0)], work)
        work = HALF_PERIOD.sub("。", work)

    work = ELLIPSIS.sub("……", work)
    work = DASH.sub("——", work)
    work = REPEATED_PUNCT.sub(r"\1", work)
    work = HALF_PAREN_WITH_CJK.sub(lambda m: f"（{m.group(1)}）", work)
    work = NUM_UNIT_SPACE.sub(r"\1", work)

    work = re.sub(r"\x00(\d+)\x00", lambda m: protected[int(m.group(1))], work)
    return work


RULE_DESCRIPTIONS = {
    "C001": "CJK next to Latin/digits should not be separated by a space (opt-in via --cjk-space=none)",
    "C002": "CJK characters should not be separated by a space",
    "C003": "Chinese copy should use full-width punctuation",
    "C004": "Ellipsis should be written as two full-width characters",
    "C005": "Em dash should be written as two full-width characters",
    "C006": "Repeated punctuation",
    "C007": "Parentheses containing CJK should be full-width",
    "C008": "No space between a number and its unit",
    "C009": "Paragraph should end with terminal punctuation",
    "C010": "Suspicious consecutive enumeration commas",
}


def lint_text(
    text: str,
    path: str = "<text>",
    ignore: Optional[Iterable[str]] = None,
    cjk_space: str = "keep",
) -> List[Issue]:
    ignored = set(ignore or ())
    opts = Options(cjk_space=cjk_space)
    ctx = Context()
    issues: List[Issue] = []
    for number, line in enumerate(text.splitlines(), start=1):
        for rule, col, message, fixable in check_line(line, ctx, opts):
            if rule in ignored:
                continue
            issues.append(Issue(path, number, col, rule, message, fixable))
    issues.sort(key=lambda i: (i.line, i.col, i.rule))
    return issues


def fix_text(text: str, cjk_space: str = "keep") -> str:
    opts = Options(cjk_space=cjk_space)
    ctx = Context()
    out = []
    for line in text.split("\n"):
        out.append(fix_line(line, ctx, opts))
    return "\n".join(out)
