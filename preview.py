"""Render a PDF page and mark a uniquely located citation when possible."""
from contextlib import closing

import pypdfium2 as pdfium
from PIL import Image, ImageDraw


def render_citation(content, page_number, quote):
    with closing(pdfium.PdfDocument(content)) as pdf, closing(pdf[page_number - 1]) as page:
        with closing(page.render(scale=1.4)) as bitmap:
            preview = bitmap.to_pil().convert("RGBA")
        if page.get_rotation() or not quote.strip():
            return preview, False
        with closing(page.get_textpage()) as text:
            with closing(text.search(quote.strip(), match_case=True)) as search:
                match = search.get_next()
                if match is None or search.get_next() is not None:
                    return preview, False
            count = text.count_rects(*match)
            if not count:
                return preview, False
            x0, y0, x1, y1 = page.get_bbox()
            sx, sy = preview.width / (x1 - x0), preview.height / (y1 - y0)
            overlay = Image.new("RGBA", preview.size)
            draw = ImageDraw.Draw(overlay)
            for i in range(count):
                left, bottom, right, top = text.get_rect(i)
                draw.rectangle(((left - x0) * sx, (y1 - top) * sy,
                                (right - x0) * sx, (y1 - bottom) * sy),
                               fill=(245, 191, 52, 92), outline=(155, 103, 0, 200))
            return Image.alpha_composite(preview, overlay), True
