import json
import sys
import html
import unicodedata
from pathlib import Path


DEFAULT_OPTIONS = {
    "person_name_mode": "initials",      # initials / names
    "person_order": "surname_first",     # surname_first / given_first
    "include_publisher": True,
    "include_pages": True,
    "missing_author": False,
    "missing_place": False,
    "missing_year": False,
}


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


def strip_accents(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in value if not unicodedata.combining(ch))


def norm_text(value) -> str:
    if value is None:
        return ""
    return strip_accents(str(value)).strip().lower()


def normalize_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value

    if value is None:
        return default

    text = norm_text(value)

    if text in {"true", "1", "yes", "y", "tak", "t", "on", "checked", "zaznaczone"}:
        return True

    if text in {"false", "0", "no", "n", "nie", "off", "unchecked", "niezaznaczone", ""}:
        return False

    return default


def option_value(options: dict, *keys, default=None):
    if not isinstance(options, dict):
        return default

    lowered = {norm_text(key).replace(" ", "_"): value for key, value in options.items()}

    for key in keys:
        normalized_key = norm_text(key).replace(" ", "_")
        if normalized_key in lowered:
            return lowered[normalized_key]

    return default


def selected_missing_markers(value) -> set:
    """
    Obsługuje różne formaty, które mogą przyjść z Power Automate dla wielokrotnego wyboru:
    - b.a.;b.m.;b.r.
    - b.a., b.m., b.r.
    - [{"Value":"b.a."},{"Value":"b.m."}]
    - tekst techniczny zawierający wartości.
    """
    if value is None:
        return set()

    if isinstance(value, list):
        combined_parts = []
        for item in value:
            if isinstance(item, dict):
                combined_parts.append(str(item.get("Value") or item.get("value") or item))
            else:
                combined_parts.append(str(item))
        value = ";".join(combined_parts)

    if isinstance(value, dict):
        value = str(value.get("Value") or value.get("value") or value)

    text = norm_text(value)
    text = text.replace("\\u002e", ".")

    result = set()

    if "b.a" in text or "brak autora" in text or "brak autor" in text or "bez autora" in text:
        result.add("author")

    if "b.m" in text or "brak miejsca" in text or "bez miejsca" in text:
        result.add("place")

    if "b.r" in text or "brak roku" in text or "bez roku" in text:
        result.add("year")

    return result


def normalize_options(options: dict | None = None) -> dict:
    result = dict(DEFAULT_OPTIONS)
    options = options or {}

    # Forma osoby: inicjały / imiona
    name_mode = option_value(
        options,
        "person_name_mode",
        "forma_osoby",
        "Forma osoby",
        "Inicjały czy pełne imiona",
        "Inicjaly czy pelne imiona",
        default=None,
    )
    if name_mode is not None:
        text = norm_text(name_mode)
        if text in {"imiona", "imie", "imie i nazwisko", "names", "name", "full", "full_names", "pelne imiona", "pełne imiona"}:
            result["person_name_mode"] = "names"
        elif text in {"inicjaly", "inicjały", "inicjal", "initials", "initial"}:
            result["person_name_mode"] = "initials"

    # Szyk osoby: przed nazwiskiem / po nazwisku
    order = option_value(
        options,
        "person_order",
        "szyk_osoby",
        "Szyk osoby",
        "Przed nazwiskiem czy po nim",
        default=None,
    )
    if order is not None:
        text = norm_text(order)
        if text in {"przed nazwiskiem", "imie nazwisko", "imię nazwisko", "given_first", "name_first", "first_last"}:
            result["person_order"] = "given_first"
        elif text in {"po nazwisku", "nazwisko imie", "nazwisko imię", "surname_first", "last_first"}:
            result["person_order"] = "surname_first"

    result["include_publisher"] = normalize_bool(
        option_value(
            options,
            "include_publisher",
            "uwzglednij_wydawnictwo",
            "Uwzględnij wydawnictwo",
            "Czy uwzględnić wydawnictwo",
            default=None,
        ),
        default=True,
    )

    result["include_pages"] = normalize_bool(
        option_value(
            options,
            "include_pages",
            "uwzglednij_strony",
            "Uwzględnij strony",
            "Czy uwzględnić numery stron",
            default=None,
        ),
        default=True,
    )

    missing_markers = selected_missing_markers(
        option_value(
            options,
            "missing_markers",
            "oznaczenia_brakow",
            "oznaczenia_braków",
            "Oznaczenia braków",
            "Oznacz braki",
            "Braki",
            "Braki bibliograficzne",
            default=None,
        )
    )

    if "author" in missing_markers:
        result["missing_author"] = True
    if "place" in missing_markers:
        result["missing_place"] = True
    if "year" in missing_markers:
        result["missing_year"] = True

    # Dodatkowe osobne flagi, gdyby kiedyś wygodniej było zrobić trzy checkboxy.
    result["missing_author"] = normalize_bool(
        option_value(options, "missing_author", "brak_autora", "Brak autora", default=None),
        default=result["missing_author"],
    )
    result["missing_place"] = normalize_bool(
        option_value(options, "missing_place", "brak_miejsca", "Brak miejsca", default=None),
        default=result["missing_place"],
    )
    result["missing_year"] = normalize_bool(
        option_value(options, "missing_year", "brak_roku", "Brak roku", default=None),
        default=result["missing_year"],
    )

    return result


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


def missing_author_marker(options: dict) -> str:
    return "(b.a.)" if options.get("missing_author") else ""


def person_display_name(person: dict, options: dict, natural_order: bool = False) -> str:
    """
    Format osoby zgodny z opcjami.

    options["person_name_mode"]:
    - initials -> inicjał, np. J.
    - names    -> imię, a jeśli imienia brak, inicjał

    options["person_order"]:
    - surname_first -> Kowalski J. / Kowalski Jan
    - given_first   -> J. Kowalski / Jan Kowalski

    natural_order=True wymusza szyk J. Kowalski / Jan Kowalski, ale nadal respektuje
    wybór imię/inicjał. Używane dla tłumacza i redaktora po "w:".
    """
    if not isinstance(person, dict):
        return ""

    nazwisko = esc(person.get("nazwisko"))
    inicjal = esc(person.get("inicjal"))
    imie = esc(person.get("imie"))

    if options.get("person_name_mode") == "names":
        given = imie or inicjal
    else:
        given = inicjal or imie

    if natural_order:
        if given and nazwisko:
            return f"{given} {nazwisko}"
        if nazwisko:
            return nazwisko
        if given:
            return given
        return ""

    if options.get("person_order") == "given_first":
        if given and nazwisko:
            return f"{given} {nazwisko}"
        if nazwisko:
            return nazwisko
        if given:
            return given
        return ""

    if nazwisko and given:
        return f"{nazwisko} {given}"

    if nazwisko:
        return nazwisko

    if given:
        return given

    return ""


def format_people(people, i_inni: bool = False, options: dict | None = None, natural_order: bool = False) -> str:
    options = options or DEFAULT_OPTIONS

    if not isinstance(people, list):
        return ""

    formatted = [person_display_name(person, options, natural_order=natural_order) for person in people]
    formatted = [person for person in formatted if person]

    if not formatted:
        return ""

    result = ", ".join(formatted)

    if i_inni:
        result += " i in."

    return result


def authors(item: dict, options: dict) -> str:
    result = format_people(
        item.get("autorzy", []),
        item.get("autorzy_i_inni", False),
        options=options,
        natural_order=False,
    )

    if not result:
        return missing_author_marker(options)

    return result


def format_redactors(item: dict, options: dict, natural_order: bool = False) -> str:
    redaktorzy = format_people(
        item.get("redaktorzy", []),
        item.get("redaktorzy_i_inni", False),
        options=options,
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

    person = person_display_name(tlumacz, options, natural_order=True)

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


def place_year(item: dict, options: dict) -> str:
    miejsce = esc(item.get("miejsce"))
    rok = esc(item.get("rok"))

    if not miejsce and options.get("missing_place"):
        miejsce = "(b.m.)"

    if not rok and options.get("missing_year"):
        rok = "(b.r.)"

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
            place_year(item, options),
            should_mark_field(item, "miejsce") or should_mark_field(item, "rok")
        ),
        mark_if_needed(pages(item, options), should_mark_field(item, "numery_stron")),
        mark_if_needed(url(item), should_mark_field(item, "url"))
    ]

    return finish_sentence(join_nonempty(parts))


def format_artykul_w_czasopismie(item: dict, options: dict) -> str:
    czasopismo = esc(item.get("czasopismo"))
    rok = esc(item.get("rok"))

    if not rok and options.get("missing_year"):
        rok = "(b.r.)"

    journal_part = ""

    if czasopismo and rok:
        journal_part = f"„{czasopismo}” {rok}"
    elif czasopismo:
        journal_part = f"„{czasopismo}”"
    elif rok:
        journal_part = rok

    journal_part = mark_if_needed(
        journal_part,
        should_mark_field(item, "czasopismo") or should_mark_field(item, "rok")
    )

    parts = [
        mark_if_needed(authors(item, options), should_mark_field(item, "autorzy")),
        mark_if_needed(
            italic(item.get("tytul_artykulu_rozdzialu")),
            should_mark_field(item, "tytul_artykulu_rozdzialu")
        ),
        journal_part,
        mark_if_needed(journal_volume(item), should_mark_field(item, "tom")),
        mark_if_needed(number(item), should_mark_field(item, "numer")),
        mark_if_needed(pages(item, options), should_mark_field(item, "numery_stron")),
        mark_if_needed(url(item), should_mark_field(item, "url"))
    ]

    return finish_sentence(join_nonempty(parts))


def format_praca_zbiorowa(item: dict, options: dict) -> str:
    redactors = format_redactors(item, options, natural_order=False)

    # Przy pracy zbiorowej brak autora nie jest automatycznie sygnalizowany,
    # jeśli są redaktorzy. Jeśli nie ma ani autorów, ani redaktorów, można dodać (b.a.).
    responsible = redactors or missing_author_marker(options)

    parts = [
        mark_if_needed(responsible, should_mark_field(item, "redaktorzy") or should_mark_field(item, "autorzy")),
        mark_if_needed(italic(item.get("tytul_tomu")), should_mark_field(item, "tytul_tomu")),
        mark_if_needed(volume(item), should_mark_field(item, "tom")),
        mark_if_needed(format_translator(item, options), should_mark_field(item, "tlumacz")),
        mark_if_needed(publisher(item, options), should_mark_field(item, "wydawnictwo")),
        mark_if_needed(
            place_year(item, options),
            should_mark_field(item, "miejsce") or should_mark_field(item, "rok")
        ),
        mark_if_needed(pages(item, options), should_mark_field(item, "numery_stron")),
        mark_if_needed(url(item), should_mark_field(item, "url"))
    ]

    return finish_sentence(join_nonempty(parts))


def format_rozdzial_w_pracy_zbiorowej(item: dict, options: dict) -> str:
    redactors = mark_if_needed(
        format_redactors(item, options, natural_order=True),
        should_mark_field(item, "redaktorzy")
    )

    volume_title = mark_if_needed(
        italic(item.get("tytul_tomu")),
        should_mark_field(item, "tytul_tomu")
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
            should_mark_field(item, "tytul_artykulu_rozdzialu")
        ),
        in_part,
        mark_if_needed(volume(item), should_mark_field(item, "tom")),
        mark_if_needed(format_translator(item, options), should_mark_field(item, "tlumacz")),
        mark_if_needed(publisher(item, options), should_mark_field(item, "wydawnictwo")),
        mark_if_needed(
            place_year(item, options),
            should_mark_field(item, "miejsce") or should_mark_field(item, "rok")
        ),
        mark_if_needed(pages(item, options), should_mark_field(item, "numery_stron")),
        mark_if_needed(url(item), should_mark_field(item, "url"))
    ]

    return finish_sentence(join_nonempty(parts))


def format_strona_internetowa(item: dict, options: dict) -> str:
    parts = [
        mark_if_needed(authors(item, options), should_mark_field(item, "autorzy")),
        mark_if_needed(
            italic(item.get("tytul_artykulu_rozdzialu")),
            should_mark_field(item, "tytul_artykulu_rozdzialu")
        ),
        mark_if_needed(esc(item.get("nazwa_portalu")), should_mark_field(item, "nazwa_portalu")),
        mark_if_needed(url(item), should_mark_field(item, "url"))
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
