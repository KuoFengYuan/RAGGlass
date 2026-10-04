"""Check bilingual documentation links and required delivery files without network access."""

import hashlib
import json
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
    "docs/DEMO",
    "docs/CLEANUP",
    "docs/USABILITY",
    "docs/INGESTION",
    "docs/WORKFLOWS",
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
    "docs/media/demo-embeds.json",
    "docs/media/demo-tutorial.json",
    "docs/media/demo-tutorial-render.json",
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

render = json.loads((ROOT / "docs/media/demo-tutorial-render.json").read_text())
tutorial = json.loads((ROOT / "docs/media/demo-tutorial.json").read_text())
recording_bytes = (ROOT / "docs/media/demo-recording.json").read_bytes()
recording = json.loads(recording_bytes)
assert render["source_recording_sha256"] == hashlib.sha256(recording_bytes).hexdigest()
assert (
    render["renderer_sha256"]
    == hashlib.sha256((ROOT / "scripts/demo_media.mjs").read_bytes()).hexdigest()
)
assert (
    render["tutorial_sha256"]
    == hashlib.sha256((ROOT / "docs/media/demo-tutorial.json").read_bytes()).hexdigest()
)
assert render["playback_speed"] == 1 and render["live_queries_added"] == 0
for language in ["en", "zh-TW"]:
    suffix = "" if language == "en" else ".zh-TW"
    for extension in ["srt", "vtt"]:
        captions = (ROOT / "docs/media" / f"ragglass-demo{suffix}.{extension}").read_text()
        for scene in recording["scenes"]:
            for line in tutorial["scenes"][scene["id"]][language].values():
                assert line in captions, f"Missing {language} tutorial line: {scene['id']}"
    output = render["media"][language]
    assert output["codec_name"] == "h264" and output["pix_fmt"] == "yuv420p"
    assert (output["width"], output["height"]) == (1440, 1200)
    assert 0 < output["bytes"] < 10_000_000
    assert abs(output["duration_seconds"] - recording["media"][language]["duration_seconds"]) < 0.1

embeds = json.loads((ROOT / "docs/media/demo-embeds.json").read_text())
for language, filename, heading, watch_link in [
    ("en", "README.md", "Watch the demo", "[Watch the demo](#watch-the-demo)"),
    ("zh-TW", "README.zh-TW.md", "觀看操作示範", "[觀看操作示範](#觀看操作示範)"),
]:
    text = (ROOT / filename).read_text()
    video = embeds["videos"][language]
    assert re.fullmatch(r"https://github\.com/user-attachments/assets/[0-9a-f-]{36}", video["url"])
    assert re.fullmatch(r"[0-9a-f]{64}", video["sha256"])
    assert 0 < video["bytes"] < 10_000_000
    for field in ["sha256", "bytes", "duration_seconds", "width", "height", "codec_name"]:
        assert video[field] == render["media"][language][field], (
            f"Embed does not match the rendered tutorial: {language} {field}"
        )
    assert f"## {heading}\n\n{video['url']}\n\n" in text, f"Missing inline player: {filename}"
    assert watch_link in text, f"Demo navigation must stay in the README: {filename}"
    assert not re.search(r"https://[^\s)]+/releases/download/[^\s)]+\.mp4", text), (
        f"Demo must play inline instead of opening a download: {filename}"
    )

markdown = [*ROOT.glob("*.md"), *ROOT.glob("docs/*.md"), *ROOT.glob("examples/*.md")]
for document in markdown:
    for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", document.read_text()):
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            continue
        resolved = (document.parent / unquote(url.path)).resolve()
        assert resolved.is_file(), f"Broken local link in {document.name}: {target}"
print("Bilingual documentation, screenshots, local links, and delivery files: OK")
