# Processador de PDFs Judiciais

## Como executar localmente

1. Instale Python 3.9+
2. Instale os requisitos:

   ```bash
   pip install -r requirements.txt
   ```

3. Instale dependências do sistema (Linux):

   ```bash
   sudo apt install tesseract-ocr poppler-utils
   ```

   No Windows, baixe executáveis Tesseract e Poppler (veja notas no código e requirements.txt).

4. Execute:

   ```bash
   uvicorn app.main:app --reload
   ```

5. Aceda em: <http://127.0.0.1:8000/>

Uploads e outputs ficam em `uploads/` e `outputs/`, organizados por UUID/job.

## Notas
- Só .pdf, tamanho máximo configurável em main.py
- Sem BDs, tudo via filesystem
- Processamento modular em `app/process_pdf.py` e `app/utils.py`
- Logs e tratamento de erros básicos
