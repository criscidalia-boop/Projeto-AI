import os
import shutil
import zipfile
from io import BytesIO
from pathlib import Path

import streamlit as st

# -------------------------------------------------------------------
# IMPORTANTE:
# Ajusta este import conforme a tua estrutura:
# - Se tens process_pdf.py no mesmo diretório:      from process_pdf import make_job_dirs, process_pdf
# - Se está em app/process_pdf.py (módulo app):     from app.process_pdf import make_job_dirs, process_pdf
# -------------------------------------------------------------------
from process_pdf import make_job_dirs, process_pdf  # <-- ajusta se necessário


UPLOADS_ROOT = "uploads"
OUTPUTS_ROOT = "outputs"
MAX_MB = 20


def allowed_file(filename: str) -> bool:
    return filename.lower().endswith(".pdf")


def sanitize_filename(filename: str) -> str:
    return os.path.basename(filename)


def human_size(n: int) -> str:
    # simples e suficiente para UI
    for unit in ["B", "KB", "MB", "GB"]:
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n/ (1024 if unit=='KB' else 1):.2f} {unit}"
        n /= 1024
    return f"{n:.2f} GB"


def build_zip_bytes(out_dir: str) -> bytes:
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name in sorted(os.listdir(out_dir)):
            if name.endswith(".pdf"):
                zf.write(os.path.join(out_dir, name), arcname=name)
    buf.seek(0)
    return buf.read()


st.set_page_config(page_title="Processador de PDFs", layout="centered")

st.title("Processador de PDFs")
st.caption("Upload de PDF → processamento → downloads (PDFs e ZIP).")
# 👇 CONTEXTO / INSTRUÇÕES AQUI
with st.expander("ℹ️ Informações e instruções", expanded=True):
    st.markdown("""
    - Faz upload de um ficheiro PDF.
    - O sistema divide o PDF por páginas.
    - Cada página é analisada para identificar o número de processo.
    - No final podes descarregar os PDFs individuais ou um ZIP.

    **Nota:** PDFs digitalizados podem demorar mais tempo devido ao OCR.
    """)
uploaded = st.file_uploader("Escolhe um ficheiro PDF", type=["pdf"])

if uploaded is not None:
    # validações equivalentes às do FastAPI
    if not allowed_file(uploaded.name):
        st.error("Apenas PDFs são aceites.")
        st.stop()

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
            os.makedirs(up_dir, exist_ok=True)
            os.makedirs(out_dir, exist_ok=True)

            try:
                with open(pdf_path, "wb") as f:
                    f.write(data)

                # mantém a tua lógica existente
                process_pdf(pdf_path, out_dir)

            except Exception as e:
                # limpeza semelhante ao teu FastAPI
                try:
                    shutil.rmtree(up_dir, ignore_errors=True)
                    shutil.rmtree(out_dir, ignore_errors=True)
                except Exception:
                    pass
                st.error("Processamento falhou.")
                st.exception(e)
                st.stop()

        st.success(f"Concluído! Job: {jobid}")
        st.session_state["last_jobid"] = jobid

# Se já houve job processado nesta sessão, mostra resultados
jobid = st.session_state.get("last_jobid")
if jobid:
    out_dir = os.path.join(OUTPUTS_ROOT, jobid)

    st.divider()
    st.subheader(f"Resultados ({jobid})")

    if not os.path.isdir(out_dir):
        st.warning("Diretório de outputs não encontrado.")
        st.stop()

    pdfs = [f for f in sorted(os.listdir(out_dir)) if f.endswith(".pdf")]

    if not pdfs:
        st.info("Não foram gerados PDFs.")
    else:
        # botão ZIP (em memória)
        zip_bytes = build_zip_bytes(out_dir)
        st.download_button(
            "Descarregar ZIP com todos os PDFs",
            data=zip_bytes,
            file_name=f"{jobid}.zip",
            mime="application/zip",
            use_container_width=True,
        )

        st.markdown("### PDFs gerados")
        for fs_name in pdfs:
            logical_name = fs_name.replace("_", "/").replace(".pdf", "")
            file_path = os.path.join(out_dir, sanitize_filename(fs_name))
            file_size = os.path.getsize(file_path)

            col1, col2 = st.columns([3, 2])
            with col1:
                st.write(f"**{logical_name}**")
                st.caption(f"{fs_name} • {file_size / 1024:.1f} KB")

            with col2:
                with open(file_path, "rb") as f:
                    st.download_button(
                        "Descarregar",
                        data=f.read(),
                        file_name=fs_name,
                        mime="application/pdf",
                        key=f"dl_{jobid}_{fs_name}",
                        use_container_width=True,
                    )
