#!/usr/bin/env python3
"""
make_a4_print_order.py
----------------------
Reorder the pages of the rendered A5 songbook PDF into the fold-and-print order

    1, 3, 4, 2,  5, 7, 8, 6,  9, 11, 12, 10, ...

so it can be printed "2 pages per A4, double-sided" and each A4 sheet folded once
(over the short side) into an A5 booklet. Every group of 4 pages = one A4 sheet.

IMPORTANT: this works on the RENDERED PDF, not on index.html. Page breaks and the
printed page numbers are produced by the Paged.js renderer when the HTML is
exported to PDF. Reordering the PDF keeps each page's content AND its printed
number exactly as-is and only changes the order -- which is what we want.
So the workflow is:
    1. Export index.html -> PDF the way you already do (Zpevnik-a-Legendy-Svistu.pdf)
    2. Run this script:  python3 ./make_a4_print_order.py

If the total page count is not a multiple of 4, blank pages are appended at the
end so the last A4 sheet is complete.

Usage:
    python3 make_a4_print_order.py [input.pdf] [output.pdf]
Defaults:
    input  = Zpevnik-a-Legendy-Svistu.pdf
    output = Zpevnik-A4-tisk.pdf

You do NOT need to install anything by hand. On first run the script creates a
local .venv next to itself and installs pypdf there, then re-runs itself with it.
"""
import os
import subprocess
import sys


def _ensure_pypdf():
    """Make `import pypdf` work. If it isn't available in the current interpreter,
    create/use a local .venv, install pypdf there, and re-exec with that python."""
    try:
        import pypdf  # noqa: F401
        return
    except ImportError:
        pass

    here = os.path.dirname(os.path.abspath(__file__))
    venv = os.path.join(here, ".venv")
    vpy = os.path.join(venv, "bin", "python")            # POSIX (macOS/Linux)
    if not os.path.exists(vpy):
        vpy = os.path.join(venv, "Scripts", "python.exe")  # Windows fallback

    # NB: compare sys.prefix, not the executable path -- a venv's python is a
    # symlink to the same base binary, so realpath(sys.executable) is identical
    # in both. sys.prefix, however, points at the venv dir when running its python.
    already_in_venv = os.path.realpath(sys.prefix) == os.path.realpath(venv)

    try:
        if not os.path.exists(vpy):
            print("First run: creating local .venv and installing pypdf ...")
            subprocess.check_call([sys.executable, "-m", "venv", venv])
            vpy = os.path.join(venv, "bin", "python")
            if not os.path.exists(vpy):
                vpy = os.path.join(venv, "Scripts", "python.exe")
        # install/upgrade pypdf inside the venv (venvs are not PEP-668 locked)
        subprocess.check_call([vpy, "-m", "pip", "install", "--quiet",
                               "--disable-pip-version-check", "pypdf"])
    except (subprocess.CalledProcessError, OSError) as e:
        sys.exit(f"Could not set up pypdf automatically ({e}).\n"
                 f"Manual fix:\n"
                 f"    python3 -m venv .venv && ./.venv/bin/pip install pypdf\n"
                 f"then run:  ./.venv/bin/python make_a4_print_order.py")

    if already_in_venv:
        # We are the venv python and pypdf is now installed -> just continue.
        return
    # Re-launch this script with the venv's python.
    os.execv(vpy, [vpy, os.path.abspath(__file__)] + sys.argv[1:])


def main():
    _ensure_pypdf()
    from pypdf import PdfReader, PdfWriter, PageObject

    inp = sys.argv[1] if len(sys.argv) > 1 else "Zpevnik-a-Legendy-Svistu.pdf"
    out = sys.argv[2] if len(sys.argv) > 2 else "Zpevnik-A4-tisk.pdf"

    if not os.path.exists(inp):
        sys.exit(f"Input PDF not found: {inp}\n"
                 f"Export index.html to PDF first (your normal Paged.js export).")

    reader = PdfReader(inp)
    pages = list(reader.pages)
    n = len(pages)
    if n == 0:
        sys.exit("Input PDF has no pages.")

    # Pad up to a multiple of 4 with blank pages that match the last page's size.
    pad = (-n) % 4
    w = float(pages[-1].mediabox.width)
    h = float(pages[-1].mediabox.height)
    all_pages = pages + [PageObject.create_blank_page(width=w, height=h)
                         for _ in range(pad)]
    total = len(all_pages)

    # Per sheet of 4: keep page 1, then 3, 4, 2  (0-indexed: 0, 2, 3, 1)
    order = []
    for base in range(0, total, 4):
        order += [base + 0, base + 2, base + 3, base + 1]

    writer = PdfWriter()
    for idx in order:
        writer.add_page(all_pages[idx])

    with open(out, "wb") as f:
        writer.write(f)

    preview = ", ".join(str(i + 1) if i < n else "blank" for i in order[:12])
    print(f"Input : {inp}  ({n} pages)")
    if pad:
        print(f"Padded: +{pad} blank page(s) -> {total} pages")
    print(f"Sheets: {total // 4} A4 sheets (4 pages each)")
    print(f"Output: {out}")
    print(f"New order (first pages): {preview}{' ...' if total > 12 else ''}")
    print()
    print("PRINT SETTINGS:")
    print("  - Pages per sheet: 2   (A4)")
    print("  - Double-sided, flip on SHORT edge")
    print("  - Scale: 100% / Actual size  (two A5 fill one A4 exactly)")
    print("  - Fold each A4 sheet in half over the short side; stack in order.")
    print("  Tip: print ONE sheet first to confirm the duplex flip edge; if the")
    print("       back side is mismatched, switch the flip edge (short <-> long).")


if __name__ == "__main__":
    main()
