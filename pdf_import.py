"""Fetch direct PDF links from supported public legal publishers."""
import re
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

PUBLISHERS = {
    "eur-lex.europa.eu", "www.edpb.europa.eu", "www.govinfo.gov",
    "www.legislation.gov.uk", "www.gesetze-im-internet.de", "www.recht.bund.de",
}
MAX_BYTES = 25 * 1024 * 1024


def validate_url(url):
    parts = urlsplit(url)
    if (parts.scheme != "https" or parts.hostname not in PUBLISHERS
            or parts.username is not None or parts.password is not None
            or parts.port not in (None, 443)):
        raise ValueError("Use a direct HTTPS PDF link from a supported official publisher.")
    return parts


class OfficialRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_pdf(url):
    validate_url(url)
    request = Request(url, headers={"Accept": "application/pdf", "User-Agent": "LexiSyncAI/1.0"})
    with build_opener(OfficialRedirects()).open(request, timeout=15) as response:
        content = response.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError("The linked PDF exceeds 25 MB. Download it and use the upload option.")
        if not content.startswith(b"%PDF-"):
            raise ValueError("The link returned a webpage. Copy the publisher's direct PDF download link.")
        parts = validate_url(response.geturl())
        filename = response.headers.get_filename() or unquote(parts.path)
    filename = PurePosixPath(filename.replace(chr(92), "/")).name
    filename = re.sub(r"[^\w. -]", "-", filename).strip(". ")[:112]
    if not filename.lower().endswith(".pdf"):
        filename = (filename if filename.lower() != "pdf" and filename else parts.hostname) + ".pdf"
    return filename, content
