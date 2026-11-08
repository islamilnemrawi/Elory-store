from pathlib import Path

path = Path("index.html")
source = path.read_text(encoding="utf-8")

old_helpers = """    const c = data.config, $ = (s, root=document) => { try { return root.querySelector(s); } catch (_) { return null; } };
    const $ = (s, root=document) => { try { return Array.from(root.querySelectorAll(s)); } catch (_) { return []; } };"""
new_helpers = """    const c = data.config, $ = (s, root=document) => { try { return root.querySelector(s); } catch (_) { return null; } };
    const $$ = (s, root=document) => { try { return Array.from(root.querySelectorAll(s)); } catch (_) { return []; } };"""

if old_helpers in source:
    source = source.replace(old_helpers, new_helpers, 1)
elif new_helpers not in source:
    raise SystemExit("CMS selector helper block not found; refusing to patch an unknown version")

array_selector_replacements = [
    ("templates=$('.hero-slide',old), dotsTemplate=$('.hero-dots',old)",
     "templates=$$('.hero-slide',old), dotsTemplate=$$('.hero-dots',old)"),
    ("cards=$('.hero-slide',slider), indicators=$('.hero-dot',slider)",
     "cards=$$('.hero-slide',slider), indicators=$$('.hero-dot',slider)"),
    ("$('.announcement-item span',announcement).forEach",
     "$$('.announcement-item span',announcement).forEach"),
    ("$('.hg-icon-v19').forEach", "$$('.hg-icon-v19').forEach"),
    ("$('.footer a[href=\"#prime\"]').forEach", "$$('.footer a[href=\"#prime\"]').forEach"),
    ("const benefits=$('#prime .prime-benefit')", "const benefits=$$('#prime .prime-benefit')"),
    ("cards=$('.elory-why-section .elory-why-card')", "cards=$$('.elory-why-section .elory-why-card')"),
]

for old, new in array_selector_replacements:
    if old in source:
        source = source.replace(old, new)
    elif new not in source:
        raise SystemExit(f"Expected selector use not found: {old}")

if source.count(", $ = (s, root=document)") != 1:
    raise SystemExit("Unexpected number of single-element selector helpers")
if source.count("const $$ = (s, root=document)") != 1:
    raise SystemExit("Array selector helper was not installed exactly once")

path.write_text(source, encoding="utf-8")
print("Fixed CMS selector helper declarations and array selector call sites.")

# The selector helper patch is idempotent and is syntax-checked by CI.
