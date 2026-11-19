import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_script_parses_and_uninstall_removes_only_its_files(tmp_path):
    assert subprocess.run(["sh", "-n", str(ROOT / "install.sh")]).returncode == 0
    for f in ("opt/citrine/bin/x", "usr/local/bin/citrine", "usr/local/bin/citrine-gui", "usr/share/applications/citrine.desktop", "usr/local/bin/other"):
        (tmp_path / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / f).write_text("x")
    done = subprocess.run(["sh", str(ROOT / "install.sh"), "--uninstall"], env={**os.environ, "CITRINE_PREFIX": str(tmp_path)})
    assert done.returncode == 0
    assert [p.name for p in tmp_path.rglob("*") if p.is_file()] == ["other"]
