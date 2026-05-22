import json
import os
import re
from pathlib import Path

from json2html import json_to_html
from html2docx import html_to_docx


DEFAULT_OPTIONS = {
    "person_name_mode": "initials",
    "person_order": "surname_first",
    "include_publisher": True,
    "include_pages": True,
}


def parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default

    text = str(value).strip().lower()

    if text in {"true", "tak", "yes", "1", "y", "t", "prawda", "☑", "checked"}:
        return True

    if text in {"false", "nie", "no", "0", "n", "f", "fałsz", "falsz", "☐", "unchecked"}:
        return False

    return default


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
    OPTIONS_END

    Brak bloku opcji oznacza ustawienia domyślne.
    """
    options = dict(DEFAULT_OPTIONS)

    match = re.search(r"OPTIONS_BEGIN\s*(.*?)\s*OPTIONS_END", body, flags=re.DOTALL | re.IGNORECASE)
    if not match:
        return options

    raw_options = match.group(1).strip()
    parsed: dict[str, str] = {}

    for line in raw_options.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        parsed[key.strip()] = value.strip()

    forma_osoby = parsed.get("forma_osoby", parsed.get("person_name_mode", ""))
    forma_osoby_lower = forma_osoby.strip().lower()

    if forma_osoby_lower in {"imiona", "imie", "imię", "names", "name", "full", "full_names"}:
        options["person_name_mode"] = "names"
    elif forma_osoby_lower in {"inicjały", "inicjaly", "inicjal", "inicjał", "initials", "initial"}:
        options["person_name_mode"] = "initials"

    szyk_osoby = parsed.get("szyk_osoby", parsed.get("person_order", ""))
    szyk_osoby_lower = szyk_osoby.strip().lower()

    if szyk_osoby_lower in {"przed nazwiskiem", "imie nazwisko", "imię nazwisko", "given_first", "name_first", "first_last"}:
        options["person_order"] = "given_first"
    elif szyk_osoby_lower in {"po nazwisku", "nazwisko imie", "nazwisko imię", "surname_first", "last_first"}:
        options["person_order"] = "surname_first"

    options["include_publisher"] = parse_bool(
        parsed.get("uwzglednij_wydawnictwo", parsed.get("include_publisher")),
        default=True,
    )

    options["include_pages"] = parse_bool(
        parsed.get("uwzglednij_strony", parsed.get("include_pages")),
        default=True,
    )

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

    print(f"Opcje: {options}")
    print(f"Zapisano: {output_path}")


if __name__ == "__main__":
    main()
