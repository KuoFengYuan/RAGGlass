"""Check bilingual documentation links and required delivery files without network access."""

import re
import struct
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
for name in [
    "README",
    "AGENTS",
    "CONTRIBUTING",
    "docs/MILESTONE",
    "docs/USAGE",
    "docs/DEPLOYMENT",
    "docs/LAUNCH",
    "docs/ANNOUNCEMENT",
    "docs/CASE_STUDY",
    "docs/RELEASE-v0.1.0",
    "examples/README",
]:
    en = ROOT / f"{name}.md"
    zh = ROOT / f"{name}.zh-TW.md"
    assert en.is_file() and zh.is_file(), f"Missing bilingual pair: {name}"
    assert zh.name in en.read_text(), f"Missing Chinese link: {en}"
    assert en.name in zh.read_text(), f"Missing English link: {zh}"
for file in [
    "LICENSE",
    ".env.example",
    "uv.lock",
    "frontend/package-lock.json",
    "compose.yaml",
    "examples/ragglass-field-guide.pdf",
    ".github/pull_request_template.md",
    "docs/media/demo-recording.json",
]:
    assert (ROOT / file).is_file(), f"Missing delivery file: {file}"
for filename in ["workbench", "document-library", "parsed-content", "run-history", "run-settings"]:
    for suffix in ["", ".zh-TW"]:
        assert (ROOT / "docs" / "images" / f"{filename}{suffix}.png").is_file()
for suffix in ["", ".zh-TW"]:
    cover = (ROOT / "docs/images" / f"social-preview{suffix}.png").read_bytes()
    assert cover[:8] == b"\x89PNG\r\n\x1a\n" and len(cover) < 1_000_000
    assert struct.unpack(">II", cover[16:24]) == (1280, 640), "Invalid social preview dimensions"
    gif = (ROOT / "docs/images" / f"demo{suffix}.gif").read_bytes()
    assert gif[:6] in (b"GIF87a", b"GIF89a") and len(gif) < 3_000_000

markdown = [*ROOT.glob("*.md"), *ROOT.glob("docs/*.md"), *ROOT.glob("examples/*.md")]
for document in markdown:
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text()):
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            continue
        resolved = (document.parent / unquote(url.path)).resolve()
        assert resolved.is_file(), f"Broken local link in {document.name}: {target}"
print("Bilingual documentation, screenshots, local links, and delivery files: OK")
