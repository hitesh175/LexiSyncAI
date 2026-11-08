"""Recognize image-only pages locally with the Windows OCR engine."""
from contextlib import closing
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

import pypdfium2 as pdfium


def read_scan(content, page_number):
    if sys.platform != "win32":
        raise ImportError("Windows OCR is unavailable on this platform.")
    with TemporaryDirectory(prefix="lexisync-ocr-") as temp:
        png = Path(temp) / "page.png"
        with closing(pdfium.PdfDocument(content)) as pdf, closing(pdf[page_number - 1]) as page:
            scale = min(2.5, 2400 / max(page.get_size()))
            with closing(page.render(scale=scale)) as bitmap:
                bitmap.to_pil().save(png, format="PNG")
        process = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(Path(__file__).with_name("windows_ocr.ps1")), str(png)],
            capture_output=True, encoding="utf-8", errors="replace", timeout=40,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    if process.returncode == 2:
        raise ImportError("Windows OCR language resources are unavailable.")
    process.check_returncode()
    return process.stdout.strip()
