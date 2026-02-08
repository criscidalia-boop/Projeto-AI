import os
import shutil
from typing import Tuple, List
from uuid import uuid4

import pdfplumber
from pypdf import PdfWriter, PdfReader
from pdf2image import convert_from_path
import pytesseract
import re

def extract_text_from_page(pdf_path, page_num):
    """Extrai texto da página, faz OCR se necessário."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_num]
            text = page.extract_text() or ""
    except Exception:
        text = ""
    if text.strip():
        return text
    # Fallback - OCR
    images = convert_from_path(pdf_path, first_page=page_num+1, last_page=page_num+1)
    if images:
        ocr_text = pytesseract.image_to_string(images[0], lang="por")
        return ocr_text
    return ""

# Pattern amplo baseado no Processos_Submeter.py
PROCESS_NUMBER_PATTERN = re.compile(
    r"(\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4})|(\b\d{4,}([.\-/]\d{2,}){0,3}\b)"
)

def extract_process_number(text: str) -> str | None:
    """Extrai o número do processo do texto (primeira ocorrência válida)."""
    if text:
        match = PROCESS_NUMBER_PATTERN.search(text)
        if match:
            return next((g for g in match.groups() if g), match.group(0))
    return None

def sanitize_filename(name):
    """Sanitize para nomes de ficheiro seguros."""
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)

def process_pdf(input_pdf_path: str, outputs_dir: str) -> List[Tuple[str, str, int]]:
    """
    Split PDF, extrai nº processo (ou fallback), salva cada página como PDF, retorna [(nome_logico, caminho, tamanho)]
    """
    reader = PdfReader(input_pdf_path)
    process_numbers_seen = {}
    page_files = []

    for i, page in enumerate(reader.pages):
        text = extract_text_from_page(input_pdf_path, i)
        nproc = extract_process_number(text)

        if nproc:
            logical_name = nproc
            fs_name = sanitize_filename(nproc)
        else:
            logical_name = f"SEM_PROCESSO_PAG_{i+1}"
            fs_name = logical_name

        # Único: se já existir, incrementa sufixo
        base_fs_name = fs_name
        c = process_numbers_seen.get(fs_name, 0)
        if c > 0:
            fs_name = f"{base_fs_name}_{c+1}"
        process_numbers_seen[base_fs_name] = c + 1

        outfile = os.path.join(outputs_dir, f"{fs_name}.pdf")
        writer = PdfWriter()
        writer.add_page(page)
        with open(outfile, "wb") as f:
            writer.write(f)
        page_files.append((logical_name, outfile, os.path.getsize(outfile)))
    return page_files

def make_job_dirs(base_dir="uploads", out_base="outputs") -> Tuple[str, str, str]:
    jobid = str(uuid4())
    up_dir = os.path.join(base_dir, jobid)
    out_dir = os.path.join(out_base, jobid)
    os.makedirs(up_dir, exist_ok=True)
    os.makedirs(out_dir, exist_ok=True)
    return jobid, up_dir, out_dir
import os
import zipfile
from io import BytesIO

import streamlit as st

# Se o ficheiro se chamar process_pdf.py e estiver no mesmo diretório:
from process_pdf import make_job_dirs, process_pdf  # <-- ajusta se necessário


UPLOADS_ROOT = "uploads"
OUTPUTS_ROOT = "outputs"
MAX_MB = 20


def build_zip_from_files(files: list[tuple[str, str, int]]) -> bytes:
    """
    files: [(logical_name, filepath, size)]
    Cria ZIP em memória com os PDFs (usa o nome do ficheiro no disco).
    """
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for _, filepath, _size in files:
            arcname = os.path.basename(filepath)
            zf.write(filepath, arcname=arcname)
    buf.seek(0)
    return buf.read()


st.set_page_config(page_title="Processador de PDFs", layout="centered")
st.title("Processador de PDFs")
st.caption("Upload → split por página → extração do nº de processo → downloads.")

uploaded = st.file_uploader("Escolhe um PDF", type=["pdf"])

if uploaded is not None:
    data = uploaded.getvalue()
    size = len(data)

    if size > MAX_MB * 1024 * 1024:
        st.error(f"Ficheiro demasiado grande (máx. {MAX_MB} MB).")
        st.stop()

    st.write(f"**Ficheiro:** {uploaded.name}")
    st.write(f"**Tamanho:** {size / (1024*1024):.2f} MB")

    if st.button("Processar", type="primary"):
        with st.spinner("A processar..."):
            jobid, up_dir, out_dir = make_job_dirs(UPLOADS_ROOT, OUTPUTS_ROOT)

            pdf_path = os.path.join(up_dir, "input.pdf")
            with open(pdf_path, "wb") as f:
                f.write(data)

            try:
                results = process_pdf(pdf_path, out_dir)  # [(logical, filepath, size), ...]
            except Exception as e:
                st.error("Processamento falhou.")
                st.exception(e)
                st.stop()

        # Guardar na sessão para persistir no UI após rerun
        st.session_state["jobid"] = jobid
        st.session_state["results"] = results

# Mostrar resultados se existirem na sessão
jobid = st.session_state.get("jobid")
results = st.session_state.get("results")

if jobid and results is not None:
    st.divider()
    st.subheader(f"Resultados ({jobid})")

    if len(results) == 0:
        st.info("Não foram gerados PDFs.")
        st.stop()

    # ZIP
    zip_bytes = build_zip_from_files(results)
    st.download_button(
        "Descarregar ZIP com todos os PDFs",
        data=zip_bytes,
        file_name=f"{jobid}.zip",
        mime="application/zip",
        use_container_width=True,
    )

    st.markdown("### PDFs gerados")
    for idx, (logical_name, filepath, fsize) in enumerate(results, start=1):
        filename = os.path.basename(filepath)

        col1, col2 = st.columns([3, 2])
        with col1:
            st.write(f"**{idx}. {logical_name}**")
            st.caption(f"{filename} • {fsize/1024:.1f} KB")
        with col2:
            with open(filepath, "rb") as f:
                st.download_button(
                    "Descarregar",
                    data=f.read(),
                    file_name=filename,
                    mime="application/pdf",
                    key=f"dl_{jobid}_{idx}",
                    use_container_width=True,
                )