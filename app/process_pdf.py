import os
import re
from typing import Tuple, List
from uuid import uuid4

import pdfplumber
from pypdf import PdfWriter, PdfReader
from pdf2image import convert_from_path
import pytesseract

# Pattern amplo baseado no Processos_Submeter.py
PROCESS_NUMBER_PATTERN = re.compile(
    r"(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})|(\b\d{4,}([.\-/]\d{2,}){0,3}\b)"
)


def extract_text_from_page(pdf_path: str, page_num: int) -> str:
    """Extrai texto da página; faz OCR se necessário."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_num]
            text = page.extract_text() or ""
    except Exception:
        text = ""

    if text.strip():
        return text

    # Fallback - OCR (usa pdf2image + tesseract)
    images = convert_from_path(pdf_path, first_page=page_num + 1, last_page=page_num + 1)
    if images:
        return pytesseract.image_to_string(images[0], lang="por")
    return ""


def extract_process_number(text: str) -> str | None:
    """Extrai o número do processo do texto (primeira ocorrência válida)."""
    if not text:
        return None
    match = PROCESS_NUMBER_PATTERN.search(text)
    if not match:
        return None
    # primeira group não-vazia (ou fallback para o match completo)
    return next((g for g in match.groups() if g), match.group(0))


def sanitize_filename(name: str) -> str:
    """Sanitize para nomes de ficheiro seguros."""
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


def process_pdf(input_pdf_path: str, outputs_dir: str) -> List[Tuple[str, str, int]]:
    """
    Divide o PDF em páginas, tenta extrair nº de processo (ou fallback),
    salva cada página como PDF, retorna:
        [(nome_logico, caminho_ficheiro, tamanho_bytes), ...]
    """
    reader = PdfReader(input_pdf_path)
    process_numbers_seen: dict[str, int] = {}
    page_files: List[Tuple[str, str, int]] = []

    for i, page in enumerate(reader.pages):
        text = extract_text_from_page(input_pdf_path, i)
        nproc = extract_process_number(text)

        if nproc:
            logical_name = nproc
            base_fs_name = sanitize_filename(nproc)
        else:
            logical_name = f"SEM_PROCESSO_PAG_{i+1}"
            base_fs_name = logical_name

        # Garante unicidade: se já existir, incrementa sufixo
        c = process_numbers_seen.get(base_fs_name, 0)
        fs_name = f"{base_fs_name}_{c+1}" if c > 0 else base_fs_name
        process_numbers_seen[base_fs_name] = c + 1

        outfile = os.path.join(outputs_dir, f"{fs_name}.pdf")
        writer = PdfWriter()
        writer.add_page(page)
        with open(outfile, "wb") as f:
            writer.write(f)

        page_files.append((logical_name, outfile, os.path.getsize(outfile)))

    return page_files


def make_job_dirs(base_dir: str = "uploads", out_base: str = "outputs") -> Tuple[str, str, str]:
    """Cria pastas de job (uploads/jobid e outputs/jobid)."""
    jobid = str(uuid4())
    up_dir = os.path.join(base_dir, jobid)
    out_dir = os.path.join(out_base, jobid)
    os.makedirs(up_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    return jobid, up_dir, out_dir
