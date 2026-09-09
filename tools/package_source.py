"""Rebuild the downloadable source ZIP from Git-tracked and new nonignored files."""
from pathlib import Path
import os
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist" / "printflow-source.zip"


def main():
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
    ).decode().split("\0")
    names = sorted({name for name in names if name and not name.startswith(".openai/")
                    and name != "dist/printflow-source.zip"})
    temporary = OUTPUT.with_name("printflow-source.tmp.zip")
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name in names:
                entry = zipfile.ZipInfo("printflow-lab/" + name, date_time=(2026, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, (ROOT / name).read_bytes())
        with zipfile.ZipFile(temporary) as archive:
            assert archive.testzip() is None
            for name in names:
                assert archive.read("printflow-lab/" + name) == (ROOT / name).read_bytes()
        os.replace(temporary, OUTPUT)
        print(f"Packaged and verified {len(names)} source files: {OUTPUT}")
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
