"""markdown 파일 맨 앞 frontmatter의 좁은 부분집합 파서.

지원: 한 줄짜리 `key: value`. value는 따옴표 문자열("…" JSON 규칙, '…' YAML 규칙),
따옴표 없는 스칼라, 한 줄 flow 목록 `[a, "b"]`. 값 뒤의 ` # 주석`은 버린다.
그 밖의 YAML(들여쓰기, 블록 목록, 여러 줄 문자열, 매핑, 앵커, 태그)은 조용히 넘기지 않고 오류로 낸다.
스칼라는 모두 문자열로 돌려준다. 타입 변환은 읽는 쪽이 한다.
"""
from __future__ import annotations

import json
import re

Value = str | list[str]

_KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
_UNSUPPORTED_START = "{|>&*!%@`-"


class FrontmatterError(ValueError):
    def __init__(self, line: int, message: str):
        self.line = line
        self.message = message
        super().__init__(f"{line}번 줄: {message}")


def split(text: str) -> tuple[dict[str, Value], str]:
    """frontmatter와 본문으로 나눈다. frontmatter가 없으면 오류."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        raise FrontmatterError(1, "첫 줄이 '---'가 아니다(frontmatter 없음)")
    for end in range(1, len(lines)):
        if lines[end].rstrip("\r") == "---":
            break
    else:
        raise FrontmatterError(1, "frontmatter를 닫는 '---'가 없다")
    data = parse(lines[1:end], first_line=2)
    return data, "\n".join(lines[end + 1:])


def parse(lines: list[str], first_line: int = 1) -> dict[str, Value]:
    data: dict[str, Value] = {}
    for offset, raw in enumerate(lines):
        n = first_line + offset
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[0] in " \t":
            raise FrontmatterError(n, "들여쓴 줄은 지원하지 않는다(한 줄 `key: value`만)")
        if ":" not in line:
            raise FrontmatterError(n, "`key: value` 형식이 아니다")
        key, rest = line.split(":", 1)
        key = key.strip()
        if not _KEY.match(key):
            raise FrontmatterError(n, f"키 이름이 올바르지 않다: {key!r}")
        if key in data:
            raise FrontmatterError(n, f"키가 두 번 나온다: {key}")
        data[key] = _value(rest, n)
    return data


def _value(rest: str, n: int) -> Value:
    s = rest.strip()
    if not s or s.startswith("#"):
        raise FrontmatterError(n, "값이 비어 있다(여러 줄 값은 지원하지 않는다)")
    if s[0] == "[":
        items, tail = _flow_list(s, n)
        _only_comment(tail, n)
        return items
    value, tail = _scalar(s, n, stop=None)
    _only_comment(tail, n)
    return value


def _flow_list(s: str, n: int) -> tuple[list[str], str]:
    items: list[str] = []
    i = 1
    while True:
        while i < len(s) and s[i] in " \t":
            i += 1
        if i >= len(s):
            raise FrontmatterError(n, "목록을 닫는 ']'가 없다")
        if s[i] == "]":
            if items:
                raise FrontmatterError(n, "목록이 ','로 끝난다")
            return items, s[i + 1:]
        if s[i] == "[":
            raise FrontmatterError(n, "중첩 목록은 지원하지 않는다")
        item, rest = _scalar(s[i:], n, stop=",]")
        items.append(item)
        rest = rest.lstrip(" \t")
        if rest.startswith(","):
            s, i = rest, 1
            continue
        if rest.startswith("]"):
            return items, rest[1:]
        raise FrontmatterError(n, "목록 항목 뒤에 ',' 또는 ']'가 와야 한다")


def _scalar(s: str, n: int, stop: str | None) -> tuple[str, str]:
    """s 앞에서 스칼라 하나를 읽고 (값, 남은 문자열)을 돌려준다."""
    if s[0] == '"':
        try:
            value, end = json.JSONDecoder().raw_decode(s)
        except json.JSONDecodeError as e:
            raise FrontmatterError(n, f"큰따옴표 문자열이 올바르지 않다: {e.msg}") from None
        return value, s[end:]
    if s[0] == "'":
        out, i = [], 1
        while i < len(s):
            if s[i] == "'":
                if s[i + 1:i + 2] == "'":
                    out.append("'")
                    i += 2
                    continue
                return "".join(out), s[i + 1:]
            out.append(s[i])
            i += 1
        raise FrontmatterError(n, "작은따옴표 문자열이 닫히지 않았다")
    if s[0] in _UNSUPPORTED_START:
        raise FrontmatterError(n, f"'{s[0]}'로 시작하는 값은 지원하지 않는다(따옴표로 감싸라)")
    end = len(s)
    for i, ch in enumerate(s):
        if stop and ch in stop:
            end = i
            break
        if ch == "#" and i > 0 and s[i - 1] in " \t":
            end = i - 1  # 남은 문자열이 공백으로 시작해야 _only_comment가 주석으로 본다
            break
    value = s[:end].strip()
    if not value:
        raise FrontmatterError(n, "빈 값")
    if ": " in value:
        raise FrontmatterError(n, "따옴표 없는 값에 ': '가 있다(따옴표로 감싸라)")
    return value, s[end:]


def _only_comment(tail: str, n: int) -> None:
    t = tail.strip()
    if t and not (t.startswith("#") and tail[:1] in " \t"):
        raise FrontmatterError(n, f"값 뒤에 알 수 없는 내용: {t!r}")
