from fastapi import FastAPI, Response
from pydantic import BaseModel
import json
from io import BytesIO
from pathlib import Path
import tempfile

# import Twoje funkcje
from json2html import json_to_html
from html2docx import html_to_docx

app = FastAPI()

class InputData(BaseModel):
    data: dict

@app.get("/")
def root():
    return {"status": "ok"}

@app.post("/convert")
def convert(data: InputData):
    json_data = data.data

    # 1. JSON → HTML
    html_text = json_to_html(json_data, full_document=False)

    # 2. HTML → DOCX (plik tymczasowy)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        output_path = Path(tmp.name)

    html_to_docx(html_text, output_path)

    # 3. zwróć plik
    file_bytes = output_path.read_bytes()

    return Response(
        content=file_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": "attachment; filename=bibliografia.docx"
        }
    )
