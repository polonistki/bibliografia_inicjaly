import json
import sys
import html
from pathlib import Path
from typing import Any


DEFAULT_OPTIONS = {
    "person_name_mode": "initials",       # initials | names
    "person_order": "surname_first",      # surname_first | given_first
    "include_publisher": True,
    "include_pages": True,
}


def normalize_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    text = str(value).strip().lower()

    if text in {"true", "tak", "yes", "1", "y", "t", "prawda", "☑", "checked"}:
        return True

    if text in {"false", "nie", "no", "0", "n", "f", "fałsz", "falsz", "☐", "unchecked"}:
        return False

    return default


def normalize_options(options: dict | None = None) -> dict:
    """
    Normalizuje opcje przekazane z Power Automate.

    Obsługiwane wartości wejściowe są celowo liberalne, żeby działały zarówno
    z polskimi nazwami z List, jak i z wartościami technicznymi.
    """
    result = dict(DEFAULT_OPTIONS)

    if not isinstance(options, dict):
        return result

    # Forma osoby: inicjały / imiona
    name_mode = (
        options.get("person_name_mode")
        or options.get("forma_osoby")
        or options.get("Forma_osoby")
        or options.get("Forma osoby")
    )

    if name_mode is not None:
        text = str(name_mode).strip().lower()
        if text in {"imiona", "imie", "imię", "names", "name", "full", "full_names"}:
            result["person_name_mode"] = "names"
        elif text in {"inicjały", "inicjaly", "inicjal", "inicjał", "initials", "initial"}:
            result["person_name_mode"] = "initials"

    # Szyk osoby: po nazwisku / przed nazwiskiem
    order = (
        options.get("person_order")
        or options.get("szyk_osoby")
        or options.get("Szyk_osoby")
        or options.get("Szyk osoby")
    )

    if order is not None:
        text = str(order).strip().lower()
        if text in {"przed nazwiskiem", "imie nazwisko", "imię nazwisko", "given_first", "name_first", "first_last"}:
            result["person_order"] = "given_first"
        elif text in {"po nazwisku", "nazwisko imie", "nazwisko imię", "surname_first", "last_first"}:
            result["person_order"] = "surname_first"

    result["include_publisher"] = normalize_bool(
        options.get("include_publisher", options.get("uwzglednij_wydawnictwo", options.get("Uwzględnij wydawnictwo"))),
        default=True,
    )

    result["include_pages"] = normalize_bool(
        options.get("include_pages", options.get("uwzglednij_strony", options.get("Uwzględnij strony"))),
        default=True,
    )

    return result


def clean_code_fence(text: str) -> str:
    """Usuwa ewentualne znaczniki ```json ... ``` z odpowiedzi modelu."""
    text = text.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    return text


def esc(value) -> str:
    """Escapuje tekst do HTML."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True).strip()


def italic(value) -> str:
    text = esc(value)
    return f"<i>{text}</i>" if text else ""


def join_nonempty(parts, sep=", ") -> str:
    return sep.join([part for part in parts if part])


def finish_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""

    if text.endswith("."):
        return text

    return text + "."


def check_fields(item: dict) -> set:
    """
    Zwraca zestaw pól wskazanych do sprawdzenia, np.
    ["autorzy", "redaktorzy"].
    """
    fields = item.get("pola_do_sprawdzenia", [])

    if not isinstance(fields, list):
        return set()

    return {str(field) for field in fields}


def should_mark_field(item: dict, field_name: str) -> bool:
    """
    Czy podświetlić konkretne pole.
    """
    return (
        item.get("wymaga_sprawdzenia") is True
        and field_name in check_fields(item)
    )


def should_mark_record(item: dict) -> bool:
    """
    Czy podświetlić cały rekord.

    Zachowanie wstecznie zgodne:
    jeśli wymaga_sprawdzenia=true, ale nie ma pola pola_do_sprawdzenia
    albo jest ono puste, podświetla cały rekord.
    """
    if item.get("wymaga_sprawdzenia") is not True:
        return False

    fields = check_fields(item)

    if not fields:
        return True

    return "rekord" in fields


def mark_if_needed(text: str, active: bool) -> str:
    if text and active:
        return f"<mark>{text}</mark>"
    return text


def preferred_given_part(person: dict, options: dict) -> str:
    """
    Zwraca imię albo inicjał według ustawienia.
    Jeśli wybrano imiona, ale imienia brak, używa inicjału.
    Jeśli wybrano inicjały, ale inicjału brak, używa imienia.
    """
    imie = esc(person.get("imie"))
    inicjal = esc(person.get("inicjal"))

    if options.get("person_name_mode") == "names":
        return imie or inicjal

    return inicjal or imie


def person_formatted(person: dict, options: dict, natural_order: bool = False) -> str:
    """
    Formatuje osobę według ustawień.

    natural_order=True wymusza szyk: Imię/Inicjał Nazwisko.
    Używane dla tłumacza oraz redaktorów po „w:”.
    """
    if not isinstance(person, dict):
        return ""

    nazwisko = esc(person.get("nazwisko"))
    given = preferred_given_part(person, options)

    if natural_order:
        if given and nazwisko:
            return f"{given} {nazwisko}"
        return given or nazwisko

    order = options.get("person_order")

    if order == "given_first":
        if given and nazwisko:
            return f"{given} {nazwisko}"
        return given or nazwisko

    # Domyślnie: po nazwisku, np. Kowalski J. / Kowalski Jan
    if nazwisko and given:
        return f"{nazwisko} {given}"

    return nazwisko or given


def format_people(people, options: dict, i_inni: bool = False, natural_order: bool = False) -> str:
    if not isinstance(people, list):
        return ""

    formatted = [person_formatted(person, options, natural_order=natural_order) for person in people]
    formatted = [person for person in formatted if person]

    if not formatted:
        return ""

    result = ", ".join(formatted)

    if i_inni:
        result += " i in."

    return result


def authors(item: dict, options: dict) -> str:
    return format_people(
        item.get("autorzy", []),
        options,
        item.get("autorzy_i_inni", False),
    )


def format_redactors(item: dict, options: dict, natural_order: bool = False) -> str:
    redaktorzy = format_people(
        item.get("redaktorzy", []),
        options,
        item.get("redaktorzy_i_inni", False),
        natural_order=natural_order,
    )

    if not redaktorzy:
        return ""

    redaktorzy_typ = item.get("redaktorzy_typ")

    if redaktorzy_typ == "red":
        return f"{redaktorzy} (red.)"

    if redaktorzy_typ == "oprac":
        return f"{redaktorzy} (oprac.)"

    return redaktorzy


def format_translator(item: dict, options: dict) -> str:
    tlumacz = item.get("tlumacz")

    if not isinstance(tlumacz, dict):
        return ""

    person = person_formatted(tlumacz, options, natural_order=True)

    if not person:
        return ""

    return f"tłum. {person}"


def volume(item: dict) -> str:
    value = esc(item.get("tom"))
    return f"t. {value}" if value else ""


def journal_volume(item: dict) -> str:
    value = esc(item.get("tom"))
    return f"R. {value}" if value else ""


def number(item: dict) -> str:
    value = esc(item.get("numer"))
    return f"nr {value}" if value else ""


def pages(item: dict, options: dict) -> str:
    if not options.get("include_pages", True):
        return ""

    value = esc(item.get("numery_stron"))
    return f"s. {value}" if value else ""


def publisher(item: dict, options: dict) -> str:
    if not options.get("include_publisher", True):
        return ""

    return esc(item.get("wydawnictwo"))


def url(item: dict) -> str:
    return esc(item.get("url"))


def place_year(item: dict) -> str:
    miejsce = esc(item.get("miejsce"))
    rok = esc(item.get("rok"))

    if miejsce and rok:
        return f"{miejsce} {rok}"

    if miejsce:
        return miejsce

    if rok:
        return rok

    return ""


def format_monografia(item: dict, options: dict) -> str:
    parts = [
        mark_if_needed(authors(item, options), should_mark_field(item, "autorzy")),
        mark_if_needed(italic(item.get("tytul_tomu")), should_mark_field(item, "tytul_tomu")),
        mark_if_needed(volume(item), should_mark_field(item, "tom")),
        mark_if_needed(format_translator(item, options), should_mark_field(item, "tlumacz")),
        mark_if_needed(publisher(item, options), should_mark_field(item, "wydawnictwo")),
        mark_if_needed(
            place_year(item),
            should_mark_field(item, "miejsce") or should_mark_field(item, "rok"),
        ),
        mark_if_needed(pages(item, options), should_mark_field(item, "numery_stron")),
        mark_if_needed(url(item), should_mark_field(item, "url")),
    ]

    return finish_sentence(join_nonempty(parts))


def format_artykul_w_czasopismie(item: dict, options: dict) -> str:
    czasopismo = esc(item.get("czasopismo"))
    rok = esc(item.get("rok"))

    journal_part = ""

    if czasopismo and rok:
        journal_part = f"„{czasopismo}” {rok}"
    elif czasopismo:
        journal_part = f"„{czasopismo}”"
    elif rok:
        journal_part = rok

    journal_part = mark_if_needed(
        journal_part,
        should_mark_field(item, "czasopismo") or should_mark_field(item, "rok"),
    )

    parts = [
        mark_if_needed(authors(item, options), should_mark_field(item, "autorzy")),
        mark_if_needed(
            italic(item.get("tytul_artykulu_rozdzialu")),
            should_mark_field(item, "tytul_artykulu_rozdzialu"),
        ),
        journal_part,
        mark_if_needed(journal_volume(item), should_mark_field(item, "tom")),
        mark_if_needed(number(item), should_mark_field(item, "numer")),
        mark_if_needed(pages(item, options), should_mark_field(item, "numery_stron")),
        mark_if_needed(url(item), should_mark_field(item, "url")),
    ]

    return finish_sentence(join_nonempty(parts))


def format_praca_zbiorowa(item: dict, options: dict) -> str:
    parts = [
        mark_if_needed(format_redactors(item, options), should_mark_field(item, "redaktorzy")),
        mark_if_needed(italic(item.get("tytul_tomu")), should_mark_field(item, "tytul_tomu")),
        mark_if_needed(volume(item), should_mark_field(item, "tom")),
        mark_if_needed(format_translator(item, options), should_mark_field(item, "tlumacz")),
        mark_if_needed(publisher(item, options), should_mark_field(item, "wydawnictwo")),
        mark_if_needed(
            place_year(item),
            should_mark_field(item, "miejsce") or should_mark_field(item, "rok"),
        ),
        mark_if_needed(pages(item, options), should_mark_field(item, "numery_stron")),
        mark_if_needed(url(item), should_mark_field(item, "url")),
    ]

    return finish_sentence(join_nonempty(parts))


def format_rozdzial_w_pracy_zbiorowej(item: dict, options: dict) -> str:
    # Po „w:” redaktor ma mieć zawsze szyk naturalny, niezależnie od globalnego szyku osoby.
    redactors = mark_if_needed(
        format_redactors(item, options, natural_order=True),
        should_mark_field(item, "redaktorzy"),
    )

    volume_title = mark_if_needed(
        italic(item.get("tytul_tomu")),
        should_mark_field(item, "tytul_tomu"),
    )

    in_part = ""

    if redactors and volume_title:
        in_part = f"w: {redactors}, {volume_title}"
    elif redactors:
        in_part = f"w: {redactors}"
    elif volume_title:
        in_part = f"w: {volume_title}"

    parts = [
        mark_if_needed(authors(item, options), should_mark_field(item, "autorzy")),
        mark_if_needed(
            italic(item.get("tytul_artykulu_rozdzialu")),
            should_mark_field(item, "tytul_artykulu_rozdzialu"),
        ),
        in_part,
        mark_if_needed(volume(item), should_mark_field(item, "tom")),
        mark_if_needed(format_translator(item, options), should_mark_field(item, "tlumacz")),
        mark_if_needed(publisher(item, options), should_mark_field(item, "wydawnictwo")),
        mark_if_needed(
            place_year(item),
            should_mark_field(item, "miejsce") or should_mark_field(item, "rok"),
        ),
        mark_if_needed(pages(item, options), should_mark_field(item, "numery_stron")),
        mark_if_needed(url(item), should_mark_field(item, "url")),
    ]

    return finish_sentence(join_nonempty(parts))


def format_strona_internetowa(item: dict, options: dict) -> str:
    parts = [
        mark_if_needed(authors(item, options), should_mark_field(item, "autorzy")),
        mark_if_needed(
            italic(item.get("tytul_artykulu_rozdzialu")),
            should_mark_field(item, "tytul_artykulu_rozdzialu"),
        ),
        mark_if_needed(esc(item.get("nazwa_portalu")), should_mark_field(item, "nazwa_portalu")),
        mark_if_needed(url(item), should_mark_field(item, "url")),
    ]

    return finish_sentence(join_nonempty(parts))


def format_item(item: dict, options: dict) -> str:
    item_type = item.get("type")

    if item_type == "monografia":
        result = format_monografia(item, options)

    elif item_type == "artykul_w_czasopismie":
        result = format_artykul_w_czasopismie(item, options)

    elif item_type == "praca_zbiorowa":
        result = format_praca_zbiorowa(item, options)

    elif item_type == "rozdzial_w_pracy_zbiorowej":
        result = format_rozdzial_w_pracy_zbiorowej(item, options)

    elif item_type == "strona_internetowa":
        result = format_strona_internetowa(item, options)

    else:
        result = esc(item.get("raw_record"))

    if should_mark_record(item):
        result = f"<mark>{result}</mark>"

    return f"<p>{result}</p>"


def json_to_html(data: dict, full_document: bool = False, options: dict | None = None) -> str:
    options = normalize_options(options)
    items = data.get("items", [])

    if not isinstance(items, list):
        items = []

    body = "\n".join(
        format_item(item, options)
        for item in items
        if isinstance(item, dict)
    )

    if not full_document:
        return body

    return (
        "<!doctype html>\n"
        "<html>\n"
        "<head>\n"
        '  <meta charset="utf-8">\n'
        "  <title>Bibliografia</title>\n"
        "</head>\n"
        "<body>\n"
        f"{body}\n"
        "</body>\n"
        "</html>\n"
    )


def read_input() -> str:
    """
    Sposoby użycia:

    1. python json2html.py input.json output.html
    2. python json2html.py input.json
    3. type input.json | python json2html.py
    """
    if len(sys.argv) >= 2:
        input_path = Path(sys.argv[1])
        return input_path.read_text(encoding="utf-8")

    return sys.stdin.read()


def write_output(html_text: str) -> None:
    if len(sys.argv) >= 3:
        output_path = Path(sys.argv[2])
        output_path.write_text(html_text, encoding="utf-8")
    else:
        print(html_text)


def main() -> None:
    raw = read_input()
    raw = clean_code_fence(raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        message = (
            "Nie udało się odczytać JSON-a.\n"
            f"Błąd: {error}\n"
        )
        raise SystemExit(message)

    html_text = json_to_html(data, full_document=False)
    write_output(html_text)


if __name__ == "__main__":
    main()
