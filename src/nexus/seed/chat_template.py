"""Qwen2.5 ChatML render for /completion. Does not edit local_model_runtime."""
from __future__ import annotations

import struct
from pathlib import Path

QWEN25_DEFAULT_SYSTEM = (
    "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."
)
IM_START = "<|im_start|>"
IM_END = "<|im_end|>"
PROMPT_STYLES = ("raw", "chatml")
TIE_BREAK = ("chatml", "raw")


def apply_qwen25_chatml(user_text: str, system: str = QWEN25_DEFAULT_SYSTEM) -> str:
    """Official Qwen2.5 Instruct ChatML. Caller still posts this as prompt."""
    return (
        f"{IM_START}system\n{system}{IM_END}\n"
        f"{IM_START}user\n{user_text}{IM_END}\n"
        f"{IM_START}assistant\n"
    )


def extract_chatml_user(rendered: str) -> str | None:
    start = f"{IM_START}user\n"
    end = f"{IM_END}\n{IM_START}assistant\n"
    if start not in rendered or end not in rendered:
        return None
    return rendered.split(start, 1)[1].rsplit(end, 1)[0]


def render_prompt(style: str, user_text: str) -> tuple[str, dict]:
    if style == "raw":
        return user_text, {
            "style": "raw",
            "chat_template": None,
            "system": None,
            "rendered_has_im_start": IM_START in user_text,
            "user_equals_raw": True,
            "endpoint": "/completion",
        }
    if style != "chatml":
        raise ValueError("unknown_prompt_style")
    rendered = apply_qwen25_chatml(user_text)
    return rendered, {
        "style": "chatml",
        "chat_template": "qwen2.5_instruct_chatml",
        "system": QWEN25_DEFAULT_SYSTEM,
        "rendered_has_im_start": True,
        "user_equals_raw": extract_chatml_user(rendered) == user_text,
        "endpoint": "/completion",
    }


def gguf_metadata_string(path: str | Path, key: str = "tokenizer.chat_template") -> str | None:
    """Read one GGUF string. Skips tokenizer arrays. Does not load weights."""
    with Path(path).open("rb") as handle:
        def number(fmt: str):
            size = struct.calcsize(fmt)
            raw = handle.read(size)
            if len(raw) != size:
                raise ValueError("truncated GGUF")
            return struct.unpack(fmt, raw)[0]

        def string() -> str:
            n = number("<Q")
            if n > 16_000_000:
                raise ValueError("GGUF string bound")
            return handle.read(n).decode("utf-8")

        def skip(kind: int) -> None:
            if kind == 8:
                n = number("<Q")
                if n > 16_000_000:
                    raise ValueError("GGUF string bound")
                handle.seek(n, 1)
                return
            if kind == 9:
                sub = number("<I")
                count = number("<Q")
                if count > 1_000_000 or sub == 9:
                    raise ValueError("GGUF array bound")
                for _ in range(count):
                    skip(sub)
                return
            fmt = {
                0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 6: "<f",
                7: "<?", 10: "<Q", 11: "<q", 12: "<d",
            }[kind]
            handle.read(struct.calcsize(fmt))

        if handle.read(4) != b"GGUF" or number("<I") not in (2, 3):
            raise ValueError("GGUF v2/v3 model required")
        number("<Q")
        count = number("<Q")
        if count > 10000:
            raise ValueError("GGUF metadata bound")
        for _ in range(count):
            name = string()
            kind = number("<I")
            if name == key and kind == 8:
                return string()
            skip(kind)
    return None


def gguf_has_chatml_tokens(path: str | Path) -> bool:
    template = gguf_metadata_string(path, "tokenizer.chat_template") or ""
    return IM_START in template and IM_END in template


def style_score(row: dict) -> int:
    return (
        int(bool(row.get("syntax_valid")))
        + int(not row.get("placeholder"))
        + int(bool(row.get("executed")))
        + int(bool(row.get("public_passed")))
        + int(bool(row.get("semantic_correct")))
    )


def choose_best_style(rows: list[dict]) -> str:
    totals = {
        style: sum(style_score(row) for row in rows if row.get("prompt_style") == style)
        for style in PROMPT_STYLES
    }
    best = max(totals.values()) if totals else 0
    for style in TIE_BREAK:
        if totals.get(style) == best:
            return style
    return TIE_BREAK[0]
