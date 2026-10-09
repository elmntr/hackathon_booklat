"""Bounded, local text extraction. Original uploads are never saved."""
from io import BytesIO
from pathlib import PurePosixPath
import posixpath
from html.parser import HTMLParser
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile, BadZipFile

MAX_UPLOAD = 10 * 1024 * 1024
MAX_TEXT = 100_000
MAX_EXPANDED = 30 * 1024 * 1024


def clean_text(text: str) -> str:
    text = text.replace('\x00', '').replace('\u00ad', '')
    return re.sub(r'\s+', ' ', text).strip()


class BookText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        elif tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3'):
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        elif tag in ('p', 'div', 'li', 'h1', 'h2', 'h3'):
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def xml(data: bytes):
    # Document imports do not need DTDs or entity declarations.
    if re.search(br'<!\s*(DOCTYPE|ENTITY)', data, re.I):
        raise ValueError('This document contains unsupported XML declarations.')
    return ET.fromstring(data)


def archive_text(data: bytes, extension: str) -> str:
    with ZipFile(BytesIO(data)) as archive:
        if len(archive.infolist()) > 5000 or sum(i.file_size for i in archive.infolist()) > MAX_EXPANDED:
            raise ValueError('This book is too large to import. Export a shorter excerpt as TXT or PDF.')
        if extension == '.docx':
            root = xml(archive.read('word/document.xml'))
            ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            return ' '.join(''.join(n.text or '' for n in p.iter(ns + 't')) for p in root.iter(ns + 'p'))
        container = xml(archive.read('META-INF/container.xml'))
        package_path = next(n.attrib['full-path'] for n in container.iter() if n.tag.endswith('}rootfile'))
        package = xml(archive.read(package_path))
        items = {n.attrib['id']: n.attrib['href'] for n in package.iter() if n.tag.endswith('}item')}
        chapters = []
        for item in package.iter():
            if not item.tag.endswith('}itemref') or item.attrib.get('linear') == 'no':
                continue
            href = items[item.attrib['idref']].split('#')[0]
            from urllib.parse import unquote
            path = posixpath.normpath(posixpath.join(posixpath.dirname(package_path), unquote(href)))
            parser = BookText()
            parser.feed(archive.read(path).decode('utf-8-sig'))
            chapters.append(''.join(parser.parts))
            if sum(map(len, chapters)) > MAX_TEXT:
                break
        return ' '.join(chapters)


def extract(data: bytes, filename: str) -> dict:
    if not data or len(data) > MAX_UPLOAD:
        raise ValueError('Choose a nonempty file up to 10 MB.')
    filename = filename.replace('\\', '/').split('/')[-1]
    extension = PurePosixPath(filename).suffix.lower()
    source_truncated = False
    try:
        if extension in ('.txt', '.md'):
            encoding = 'utf-16' if data.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig'
            text = data.decode(encoding)
        elif extension in ('.docx', '.epub'):
            text = archive_text(data, extension)
        elif extension == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise ValueError('Use an unlocked PDF or paste the text below.')
            pages = []
            source_truncated = len(reader.pages) > 200
            for page in reader.pages[:200]:
                contents = page.get_contents()
                if contents and len(contents.get_data()) > MAX_EXPANDED:
                    raise ValueError('This PDF page is too complex. Export a short excerpt as TXT.')
                pages.append(page.extract_text() or '')
                if sum(map(len, pages)) > MAX_TEXT:
                    break
            text = ' '.join(pages)
        else:
            raise ValueError('Supported files: TXT, Markdown, PDF, DOCX, and EPUB. You can also paste text.')
    except ImportError:
        raise ValueError('PDF support needs setup again: run .\\setup-windows.cmd, then restart Booklat.')
    except (BadZipFile, KeyError, ET.ParseError, StopIteration, UnicodeError):
        raise ValueError('Could not read this document. Try an unprotected file or paste its text.')
    text = clean_text(text)
    if not text:
        raise ValueError('No readable text found. Scanned PDFs need OCR first, or you can paste the words.')
    return dict(title=PurePosixPath(filename).stem[:100], text=text[:MAX_TEXT],
                source=filename[:200], truncated=source_truncated or len(text) > MAX_TEXT,
                word_count=len(text[:MAX_TEXT].split()))
