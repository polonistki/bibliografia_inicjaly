import json
import os
import re
from pathlib import Path

from json2html import json_to_html
from html2docx import html_to_docx


def extract_json_from_issue_body(body: str) -> dict:
    """
    Wyciąga JSON z treści issue.
    Obsługuje:
    ```json
    {...}
    ```
    oraz sam czysty JSON.
    """
    body = body.strip()

    match = re.search(r"```json\s*(.*?)```", body, flags=re.DOTALL | re.IGNORECASE)
    if match:
        body = match.group(1).strip()

    return json.loads(body)


def extract_options_from_issue_body(body: str) -> dict:
    """
    Wyciąga opcje z bloku:

    OPTIONS_BEGIN
    forma_osoby=inicjały
    szyk_osoby=po nazwisku
    uwzglednij_wydawnictwo=true
    uwzglednij_strony=true
    oznaczenia_brakow=b.a.;b.m.;b.r.
    OPTIONS_END

    Brak bloku opcji oznacza ustawienia domyślne.
    """
    match = re.search(
        r"OPTIONS_BEGIN\s*(.*?)\s*OPTIONS_END",
        body,
        flags=re.DOTALL | re.IGNORECASE,
    )

    if not match:
        return {}

    options = {}
    block = match.group(1)

    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if key:
            options[key] = value

    return options


def main():
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise RuntimeError("Brak GITHUB_EVENT_PATH")

    event = json.loads(Path(event_path).read_text(encoding="utf-8"))

    issue = event["issue"]
    issue_number = issue["number"]
    issue_body = issue.get("body") or ""

    data = extract_json_from_issue_body(issue_body)
    options = extract_options_from_issue_body(issue_body)

    output_dir = Path("outputs") / f"issue-{issue_number}"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "bibliografia.docx"

    html_text = json_to_html(data, full_document=False, options=options)
    html_to_docx(html_text, output_path)

    print(f"Zapisano: {output_path}")


if __name__ == "__main__":
    main()
