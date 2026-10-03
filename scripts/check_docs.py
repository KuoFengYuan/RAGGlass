"""Check bilingual documentation links and required delivery files without network access."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for name in ["README", "AGENTS", "CONTRIBUTING", "docs/MILESTONE", "examples/README"]:
    en = ROOT / f"{name}.md"
    zh = ROOT / f"{name}.zh-TW.md"
    assert en.is_file() and zh.is_file(), f"Missing bilingual pair: {name}"
    assert zh.name in en.read_text(), f"Missing Chinese link: {en}"
    assert en.name in zh.read_text(), f"Missing English link: {zh}"
for file in [
    ".env.example",
    "uv.lock",
    "frontend/package-lock.json",
    "compose.yaml",
    "examples/ragglass-field-guide.pdf",
    ".github/pull_request_template.md",
]:
    assert (ROOT / file).is_file(), f"Missing delivery file: {file}"
print("Bilingual documentation and delivery files: OK")
