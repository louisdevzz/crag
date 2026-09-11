"""Mermaid Chart Renderer for Documentation (PNG & SVG).

Converts Mermaid diagram code into styled image files (PNG/SVG)
for embedding directly into Markdown reports and documentation.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import zlib
from pathlib import Path
from typing import Dict, List, Optional

import requests


class MermaidRenderer:
    """Renders Mermaid code into high-resolution PNG or vector SVG images."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def render_to_png(self, mermaid_code: str, output_path: Path | str, theme: str = "default") -> bool:
        """Render mermaid diagram to PNG image file via mermaid.ink / kroki.io."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        clean_code = mermaid_code.strip()

        # Method 1: mermaid.ink
        try:
            payload = {
                "code": clean_code,
                "mermaid": {"theme": theme}
            }
            json_str = json.dumps(payload)
            b64_encoded = base64.b64encode(json_str.encode("utf-8")).decode("ascii")
            url = f"https://mermaid.ink/img/{b64_encoded}?type=png"

            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200 and len(resp.content) > 100:
                output_path.write_bytes(resp.content)
                print(f"  [SUCCESS] Rendered PNG to {output_path} ({len(resp.content)} bytes)")
                return True
        except Exception as e:
            print(f"  [WARN] mermaid.ink PNG render failed: {e}")

        # Method 2: kroki.io fallback
        try:
            compressed = zlib.compress(clean_code.encode("utf-8"), 9)
            kroki_encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
            url = f"https://kroki.io/mermaid/png/{kroki_encoded}"

            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200 and len(resp.content) > 100:
                output_path.write_bytes(resp.content)
                print(f"  [SUCCESS] Rendered PNG via kroki.io to {output_path}")
                return True
        except Exception as e:
            print(f"  [ERROR] kroki.io PNG fallback failed: {e}")

        return False

    def render_to_svg(self, mermaid_code: str, output_path: Path | str) -> bool:
        """Render mermaid diagram to vector SVG file."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        clean_code = mermaid_code.strip()

        # Method 1: mermaid.ink SVG
        try:
            b64_encoded = base64.b64encode(clean_code.encode("utf-8")).decode("ascii")
            url = f"https://mermaid.ink/svg/{b64_encoded}"

            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200 and "<svg" in resp.text:
                output_path.write_text(resp.text, encoding="utf-8")
                print(f"  [SUCCESS] Rendered SVG to {output_path}")
                return True
        except Exception as e:
            print(f"  [WARN] mermaid.ink SVG render failed: {e}")

        # Method 2: kroki.io SVG fallback
        try:
            compressed = zlib.compress(clean_code.encode("utf-8"), 9)
            kroki_encoded = base64.urlsafe_b64encode(compressed).decode("ascii")
            url = f"https://kroki.io/mermaid/svg/{kroki_encoded}"

            resp = requests.get(url, timeout=self.timeout)
            if resp.status_code == 200 and "<svg" in resp.text:
                output_path.write_text(resp.text, encoding="utf-8")
                print(f"  [SUCCESS] Rendered SVG via kroki.io to {output_path}")
                return True
        except Exception as e:
            print(f"  [ERROR] kroki.io SVG fallback failed: {e}")

        return False


def extract_mermaid_blocks(markdown_content: str) -> List[Tuple[str, str]]:
    """Extract mermaid code blocks and optional titles/comments from markdown text."""
    pattern = re.compile(r"```mermaid\s*\n([\s\S]*?)\n```", re.MULTILINE)
    matches = pattern.findall(markdown_content)
    blocks = []
    for idx, code in enumerate(matches, start=1):
        name = f"diagram_{idx}"
        first_line = code.strip().split("\n")[0]
        if "%%" in first_line:
            custom_name = first_line.replace("%%", "").strip()
            name = re.sub(r"[^A-Za-z0-9_\-]", "_", custom_name).lower()
        blocks.append((name, code))
    return blocks


def render_markdown_diagrams(md_file: Path | str, output_dir: Path | str = "docs/images") -> Dict[str, str]:
    """Scan markdown file, extract all mermaid blocks, and render images."""
    md_file = Path(md_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not md_file.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_file}")

    content = md_file.read_text(encoding="utf-8")
    blocks = extract_mermaid_blocks(content)

    print(f"Found {len(blocks)} Mermaid diagram blocks in {md_file.name}")
    renderer = MermaidRenderer()
    rendered_map = {}

    for name, code in blocks:
        png_path = output_dir / f"{name}.png"
        svg_path = output_dir / f"{name}.svg"

        print(f"\nRendering '{name}'...")
        renderer.render_to_png(code, png_path)
        renderer.render_to_svg(code, svg_path)
        rendered_map[name] = str(png_path)

    return rendered_map


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render Mermaid diagrams in Markdown to PNG/SVG")
    parser.add_argument("markdown_file", nargs="?", default="docs/WORKFLOW.md", help="Path to markdown file")
    parser.add_argument("--output-dir", default="docs/images", help="Target directory for image outputs")
    args = parser.parse_args()

    render_markdown_diagrams(args.markdown_file, args.output_dir)
