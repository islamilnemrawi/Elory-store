from pathlib import Path
import os
root = Path(os.environ.get("PROJECT_DIR", "/mnt/data/elory-patched/project"))
pin = root / "app/src/main/java/com/pinky/dashboard/ui/components/OwnerDataResetControls.kt"
s = pin.read_text(encoding="utf-8")
if "import com.pinky.dashboard.ui.theme.PinkPrimary" not in s:
    s = s.replace("import kotlinx.coroutines.launch\n", "import kotlinx.coroutines.launch\nimport com.pinky.dashboard.ui.theme.PinkPrimary\n")
pin.write_text(s, encoding="utf-8")
web = root / "app/src/main/java/com/pinky/dashboard/ui/screens/website/WebsiteEditorScreen.kt"
s = web.read_text(encoding="utf-8")
s = s.replace("onClick = {\n                    onSaveConfig(config)\n                },", "onClick = {\n                    if (saveState != \"saving\") onSaveConfig(config)\n                },", 1)
s = s.replace(',\n                enabled = saveState != \"saving\"', '', 1)
web.write_text(s, encoding="utf-8")
assert "import com.pinky.dashboard.ui.theme.PinkPrimary" in pin.read_text(encoding="utf-8")
assert "enabled = saveState != \"saving\"" not in web.read_text(encoding="utf-8")
assert "if (saveState != \"saving\") onSaveConfig(config)" in web.read_text(encoding="utf-8")
print("PASS Compose compile compatibility fixes")
