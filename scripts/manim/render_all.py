#!/usr/bin/env python3
"""
Render manim scenes at 720p30 and copy the MP4s to assets/videos/<set>/<scene-name>.mp4.

Sets:
    threadx   autosar_threadx_scenes.py -> assets/videos/autosar-threadx/
    security  security_scenes.py        -> assets/videos/embedded-security/

Usage (from the repo root):
    python3 scripts/manim/render_all.py                  # every set
    python3 scripts/manim/render_all.py security         # one set
    python3 scripts/manim/render_all.py security BootTimeline [...]   # single scenes

Requires manim (pip install manim). Intermediate files go to a temp directory.

Scenes of members-only articles live in the private repo (render_premium.py there).
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
SETS = {
    "threadx": (HERE / "autosar_threadx_scenes.py", ROOT / "assets" / "videos" / "autosar-threadx",
                ["EventsToThreads", "ResourceVsMutex", "IocCrossCore"]),
    "security": (HERE / "security_scenes.py", ROOT / "assets" / "videos" / "embedded-security",
                 ["HsmJobInterface", "BootTimeline"]),
}


def kebab(name):
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def render(src, out, scenes):
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as media:
        for scene in scenes:
            subprocess.run([sys.executable, "-m", "manim", "-qm", "--media_dir", media,
                            str(src), scene], check=True)
            mp4 = next(Path(media).rglob(f"720p30/{scene}.mp4"))
            dst = out / f"{kebab(scene)}.mp4"
            shutil.copy(mp4, dst)
            print(f"Wrote {dst.relative_to(ROOT)} ({dst.stat().st_size // 1024} KB)")


def main():
    args = sys.argv[1:]
    if args and args[0] in SETS:
        src, out, scenes = SETS[args[0]]
        render(src, out, args[1:] or scenes)
    elif args:
        sys.exit(f"unknown set {args[0]!r}, expected one of: {', '.join(SETS)}")
    else:
        for src, out, scenes in SETS.values():
            render(src, out, scenes)


if __name__ == "__main__":
    main()
