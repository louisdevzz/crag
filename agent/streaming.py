"""Incremental extraction of the live-visible `answer` text from the LLM's
structured JSON generation output, for token-level SSE streaming.

`generate_answer` (agent/nodes.py) constrains the LLM to emit a single JSON
object `{"answer": str, "claims": [...], "abstain": bool}` so that citation
claims stay machine-checkable by `validate_citations`. That contract can't be
dropped just to get live streaming — instead, `AnswerFieldExtractor` scans
the raw token stream as it arrives and forwards only the decoded contents of
the `"answer"` string field, so the user sees natural language appear live
while the full JSON is still assembled server-side for citation validation.
"""
from __future__ import annotations

import re
from typing import Dict, Optional

_KEY_RE = re.compile(r'"answer"\s*:\s*"')

_SIMPLE_ESCAPES: Dict[str, str] = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
}


class AnswerFieldExtractor:
    """Stateful, chunk-boundary-safe scanner for a streaming JSON `"answer"` field.

    Call `feed(chunk)` with each raw token piece as it arrives; it returns the
    decoded text delta to display, or `""` if nothing new is displayable yet
    (still looking for the key, or waiting for a split escape sequence to
    complete). Once the field's closing quote is seen, further `feed()` calls
    return `""` (the rest of the JSON — `claims`/`abstain` — is not streamed).
    """

    def __init__(self) -> None:
        self._raw = ""
        self._key_found = False
        self._cursor = 0
        self._closed = False

    def feed(self, chunk: str) -> str:
        if not chunk or self._closed:
            return ""
        self._raw += chunk

        if not self._key_found:
            m = _KEY_RE.search(self._raw)
            if not m:
                return ""
            self._key_found = True
            self._cursor = m.end()

        out_chars = []
        i = self._cursor
        n = len(self._raw)
        while i < n:
            ch = self._raw[i]
            if ch == "\\":
                if i + 1 >= n:
                    break  # escape split across chunks — wait for more data
                nxt = self._raw[i + 1]
                if nxt == "u":
                    if i + 6 > n:
                        break  # \uXXXX split across chunks — wait for more data
                    hex_code = self._raw[i + 2 : i + 6]
                    try:
                        out_chars.append(chr(int(hex_code, 16)))
                    except ValueError:
                        pass
                    i += 6
                    continue
                out_chars.append(_SIMPLE_ESCAPES.get(nxt, nxt))
                i += 2
                continue
            if ch == '"':
                self._closed = True
                i += 1
                break
            out_chars.append(ch)
            i += 1

        self._cursor = i
        return "".join(out_chars)


# Maps LangGraph node names to the 4 user-facing CRAG pipeline stages
# (mirrors the step labels in frontend/src/components/chat/agent-progress.tsx).
NODE_STAGE: Dict[str, int] = {
    "router": 0,
    "db": 1,
    "retrieve": 1,
    "evaluate": 1,
    "refine": 2,
    "rewrite": 2,
    "web": 2,
    "select_web": 2,
    "merge": 2,
    "generate": 3,
    "cite_validate": 3,
}


def node_stage(node_name: str) -> Optional[int]:
    return NODE_STAGE.get(node_name)
