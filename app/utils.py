import re
from typing import Optional

LABELLED_REGEX = re.compile(
    r"""
    (?:
        (?:n[ºo\.-]*\s*)?          # variantes de "nº" opcionais
        (?:de|do)?\s*
        processo[:\-\s]*            # variantes de "processo"
        |                           # ou só "processo" isolado
        processo[:\-\s]*
    )
    ([0-9]{4,8}\/[0-9]{2}\.[0-9A-Z\-\.]{1,})  # formato núm. proceso
    """,
    re.IGNORECASE | re.VERBOSE
)

LOOSE_REGEX = re.compile(
    r'([0-9]{4,8}\/[0-9]{2}\.[0-9A-Z\-\.]{1,})'
)

def extract_process_number(page_text: str) -> Optional[str]:
    if not page_text:
        return None

    # Labelled first
    match = LABELLED_REGEX.search(page_text)
    if match:
        return normalize(match.group(1))
    # Then loose/strict
    match = LOOSE_REGEX.search(page_text)
    if match:
        return normalize(match.group(1))
    return None

def normalize(proc: str) -> str:
    """Remove espaços em branco e normaliza o número do processo."""
    proc = proc.strip()
    proc = re.sub(r'\s+', '', proc)
    return proc
