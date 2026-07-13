#!/usr/bin/env python3
"""
optimize_legend_images.py
-------------------------
Shrink the black-and-white contour PNGs in ./legend_images/ by flattening any
transparency onto white and quantizing to a 64-color indexed palette. Pixel
dimensions are kept EXACTLY as-is (resolution is already ideal for A5 print),
so index.html needs no changes.

Scope: only touches files inside ./legend_images/. Originals are backed up once
into ./legend_images/_originals/ before anything is overwritten.

Run:
    python3 ./optimize_legend_images.py
On first run it creates/uses a local .venv and installs Pillow there (your system
Python is left untouched), then re-launches itself with it.
"""
import os
import shutil
import subprocess
import sys

COLORS = 256
IMG_DIR = "legend_images"
BACKUP_DIR = os.path.join(IMG_DIR, "_originals")


def _ensure_pillow():
    """Make `import PIL` work; bootstrap a local .venv with Pillow if needed."""
    try:
        import PIL  # noqa: F401
        return
    except ImportError:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    venv = os.path.join(here, ".venv")
    vpy = os.path.join(venv, "bin", "python")
    if not os.path.exists(vpy):
        vpy = os.path.join(venv, "Scripts", "python.exe")  # Windows fallback

    # Compare sys.prefix (not the executable path): a venv's python is a symlink
    # to the same base binary, so the resolved executable path is identical.
    already_in_venv = os.path.realpath(sys.prefix) == os.path.realpath(venv)

    try:
        if not os.path.exists(vpy):
            print("First run: creating local .venv and installing Pillow ...")
            subprocess.check_call([sys.executable, "-m", "venv", venv])
            vpy = os.path.join(venv, "bin", "python")
            if not os.path.exists(vpy):
                vpy = os.path.join(venv, "Scripts", "python.exe")
        subprocess.check_call([vpy, "-m", "pip", "install", "--quiet",
                               "--disable-pip-version-check", "Pillow"])
    except (subprocess.CalledProcessError, OSError) as e:
        sys.exit(f"Could not set up Pillow automatically ({e}).\n"
                 f"Manual fix:\n"
                 f"    python3 -m venv .venv && ./.venv/bin/pip install Pillow\n"
                 f"then run:  ./.venv/bin/python optimize_legend_images.py")

    if already_in_venv:
        return
    os.execv(vpy, [vpy, os.path.abspath(__file__)] + sys.argv[1:])


def _fmt(nbytes):
    n = float(nbytes)
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return f"{n:.0f}{unit}" if unit == "B" else f"{n:.1f}{unit}"
        n /= 1024


def main():
    _ensure_pillow()
    from PIL import Image

    if not os.path.isdir(IMG_DIR):
        sys.exit(f"Directory not found: {IMG_DIR} (run from the project root)")

    os.makedirs(BACKUP_DIR, exist_ok=True)

    # top-level PNGs only; never recurse into the _originals backup dir
    files = sorted(
        f for f in os.listdir(IMG_DIR)
        if f.lower().endswith(".png") and os.path.isfile(os.path.join(IMG_DIR, f))
    )
    if not files:
        sys.exit(f"No PNGs found in {IMG_DIR}/")

    total_before = total_after = 0
    print(f"{'FILE':<14}{'BEFORE':>10}{'AFTER':>10}{'SAVED':>9}   SIZE(px)")
    for name in files:
        path = os.path.join(IMG_DIR, name)
        backup = os.path.join(BACKUP_DIR, name)

        # back up original once; ALWAYS optimize from the pristine original so
        # re-runs restore full quality instead of re-crushing a reduced file.
        if not os.path.exists(backup):
            shutil.copy2(path, backup)
        source = backup

        before = os.path.getsize(source)

        im = Image.open(source)
        w, h = im.size

        # flatten any transparency onto white
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            rgba = im.convert("RGBA")
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(rgba, mask=rgba.split()[-1])
            im = bg
        else:
            im = im.convert("RGB")

        # quantize to a 64-color palette, no dithering (clean lines, smaller file)
        q = im.quantize(colors=COLORS, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
        q.save(path, format="PNG", optimize=True)

        after = os.path.getsize(path)
        total_before += before
        total_after += after
        saved = 100 * (1 - after / before) if before else 0
        print(f"{name:<14}{_fmt(before):>10}{_fmt(after):>10}{saved:>8.0f}%   {w}x{h}")

    saved_total = 100 * (1 - total_after / total_before) if total_before else 0
    print("-" * 55)
    print(f"{'TOTAL':<14}{_fmt(total_before):>10}{_fmt(total_after):>10}{saved_total:>8.0f}%")
    print(f"\nOriginals backed up in: {BACKUP_DIR}/")
    print("Pixel dimensions unchanged; index.html needs no edits.")


if __name__ == "__main__":
    main()
