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
from typing import Dict, List, Optional, Tuple

import requests


class MermaidRenderer:
    """Renders Mermaid code into high-resolution PNG or vector SVG images."""

    def __init__(self, timeout: int = 20):
        self.timeout = timeout

    def render_to_png(self, mermaid_code: str, output_path: Path | str, theme: str = "default") -> bool:
        """Render mermaid diagram to PNG image file via mermaid.ink / kroki.io with white background."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        clean_code = mermaid_code.strip()

        # Method 1: mermaid.ink
        try:
            payload = {
                "code": clean_code,
                "mermaid": {
                    "theme": theme,
                    "themeVariables": {"background": "#FFFFFF"}
                }
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
            payload = {
                "code": clean_code,
                "mermaid": {
                    "themeVariables": {"background": "#FFFFFF"}
                }
            }
            b64_encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
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


def render_file(input_file: Path | str, output_dir: Path | str = "docs/images") -> Dict[str, str]:
    """Render a .mmd or .md file into PNG and SVG images."""
    input_path = Path(input_file)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    content = input_path.read_text(encoding="utf-8")
    renderer = MermaidRenderer()
    results = {}

    if input_path.suffix.lower() == ".mmd":
        stem = input_path.stem
        out_png = output_dir / f"{stem}.png"
        out_svg = output_dir / f"{stem}.svg"
        print(f"Rendering '{input_path.name}' -> PNG & SVG...")
        renderer.render_to_png(content, out_png)
        renderer.render_to_svg(content, out_svg)
        results[stem] = str(out_png)
    else:
        # Markdown file: extract mermaid blocks
        pattern = re.compile(r"```mermaid\s*\n([\s\S]*?)\n```", re.MULTILINE)
        matches = pattern.findall(content)
        for idx, code in enumerate(matches, start=1):
            name = f"{input_path.stem}_diagram_{idx}"
            first_line = code.strip().split("\n")[0]
            if "%%" in first_line:
                name = re.sub(r"[^A-Za-z0-9_\-]", "_", first_line.replace("%%", "").strip()).lower()
            out_png = output_dir / f"{name}.png"
            out_svg = output_dir / f"{name}.svg"
            print(f"Rendering block '{name}' -> PNG & SVG...")
            renderer.render_to_png(code, out_png)
            renderer.render_to_svg(code, out_svg)
            results[name] = str(out_png)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Render Mermaid diagrams to PNG/SVG with white background")
    parser.add_argument("input_file", nargs="?", default="docs/workflow.mmd", help="Path to .mmd or .md file")
    parser.add_argument("--output-dir", default="docs/images", help="Target directory for images")
    args = parser.parse_args()

    render_file(args.input_file, args.output_dir)
