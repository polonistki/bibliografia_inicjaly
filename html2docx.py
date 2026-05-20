import sys
import zipfile
from pathlib import Path
from html.parser import HTMLParser
from xml.sax.saxutils import escape


class SimpleHTMLToRunsParser(HTMLParser):
    """
    Obsługuje prosty HTML:
    <p>tekst <i>kursywa</i> <mark>podświetlenie</mark></p>
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paragraphs = []
        self.current_paragraph = None
        self.italic_level = 0
        self.mark_level = 0

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()

        if tag == "p":
            self.current_paragraph = []
            self.paragraphs.append(self.current_paragraph)

        elif tag in ("i", "em"):
            self.italic_level += 1

        elif tag == "mark":
            self.mark_level += 1

    def handle_endtag(self, tag):
        tag = tag.lower()

        if tag == "p":
            self.current_paragraph = None

        elif tag in ("i", "em"):
            self.italic_level = max(0, self.italic_level - 1)

        elif tag == "mark":
            self.mark_level = max(0, self.mark_level - 1)

    def handle_data(self, data):
        if not data:
            return

        if self.current_paragraph is None:
            if not data.strip():
                return
            self.current_paragraph = []
            self.paragraphs.append(self.current_paragraph)

        self.current_paragraph.append({
            "text": data,
            "italic": self.italic_level > 0,
            "mark": self.mark_level > 0
        })


def xml_text(text: str) -> str:
    return escape(text, {
        '"': "&quot;",
        "'": "&apos;"
    })


def make_run_xml(text: str, italic: bool = False, mark: bool = False) -> str:
    if text == "":
        return ""

    rpr_parts = []

    if italic:
        rpr_parts.append("<w:i/>")

    if mark:
        rpr_parts.append('<w:highlight w:val="yellow"/>')

    rpr = ""
    if rpr_parts:
        rpr = "<w:rPr>" + "".join(rpr_parts) + "</w:rPr>"

    preserve_space = ""
    if text.startswith(" ") or text.endswith(" ") or "  " in text:
        preserve_space = ' xml:space="preserve"'

    return (
        "<w:r>"
        f"{rpr}"
        f"<w:t{preserve_space}>{xml_text(text)}</w:t>"
        "</w:r>"
    )


def make_paragraph_xml(runs) -> str:
    run_xml = "".join(
        make_run_xml(
            run["text"],
            italic=run["italic"],
            mark=run["mark"]
        )
        for run in runs
    )

    return (
        "<w:p>"
        "<w:pPr>"
        '<w:spacing w:after="120"/>'
        "</w:pPr>"
        f"{run_xml}"
        "</w:p>"
    )


def make_document_xml(paragraphs) -> str:
    paragraphs_xml = "\n".join(make_paragraph_xml(p) for p in paragraphs)

    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document
  xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
  xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <w:body>
    {paragraphs_xml}
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>
    </w:sectPr>
  </w:body>
</w:document>
'''


def make_content_types_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
'''


def make_rels_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>
'''


def html_to_docx(html_text: str, output_path: Path):
    parser = SimpleHTMLToRunsParser()
    parser.feed(html_text)

    document_xml = make_document_xml(parser.paragraphs)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", make_content_types_xml())
        docx.writestr("_rels/.rels", make_rels_xml())
        docx.writestr("word/document.xml", document_xml)


def read_input() -> tuple[str, Path]:
    """
    Użycie:
    python html_to_docx_no_lib.py bibliografia.html bibliografia.docx
    """
    if len(sys.argv) != 3:
        raise SystemExit(
            "Użycie:\n"
            "python html_to_docx_no_lib.py input.html output.docx"
        )

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    html_text = input_path.read_text(encoding="utf-8")
    return html_text, output_path


def main():
    html_text, output_path = read_input()
    html_to_docx(html_text, output_path)


if __name__ == "__main__":
    main()