import os
import sys
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- Logging diário + consola ---
HOJE = datetime.now().strftime("%Y-%m-%d")
LOG_FILE = f"robot_bupi_{HOJE}.log"
LOG_FMT = "%(asctime)s %(levelname)s %(message)s"

logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE, mode='a', encoding='utf-8')
file_handler.setFormatter(logging.Formatter(LOG_FMT))
logger.addHandler(file_handler)
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FMT))
logger.addHandler(console_handler)

# --- CONFIGURAÇÃO ---
LOGIN_URL = "https://bo.bupi.gov.pt"
USERNAME = os.getenv("BUPI_USER")      # Ou define: 'meu_utilizador'
PASSWORD = os.getenv("BUPI_PASS")      # Ou define: 'minha_senha'
PDF_FOLDER = r"C:\CAMINHO\PARA\PDFs"   # Ex: r"C:\bupi\pdfs"
PROCESS_LIST = ["4196746"]             # Lista de processos a submeter

def human_delay(a=0.8, b=2.5):
    time.sleep(a + (b - a) * os.urandom(1)[0] / 255)

def setup_driver(headless=False):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    return webdriver.Chrome(options=options)

def login(driver):
    try:
        driver.get(LOGIN_URL)
        human_delay()
        driver.find_element(By.ID, "username").send_keys(USERNAME)
        driver.find_element(By.ID, "password").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[contains(text(), 'Entrar')]").click()
        # Confirma login (ajusta para algo específico após login)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(., 'Pesquisar processos')]"))
        )
        logging.info("Login realizado com sucesso.")
    except Exception as e:
        logging.exception("Erro no login. Robot interrompido.")
        driver.save_screenshot("erro_login.png")
        sys.exit("Erro crítico no login. Robot interrompido.")

def pesquisar_processo(driver, num_processo, timeout=10):
    try:
        driver.get(f"{LOGIN_URL}/SearchProcess")
        human_delay()
        input_proc = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='123456']"))
        )
        input_proc.clear()
        input_proc.send_keys(num_processo)
        driver.find_element(By.XPATH, "//button[contains(., 'Pesquisar')]").click()
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, "//table"))
        )
        linhas = driver.find_elements(By.XPATH, f"//table//tr[td[1][text()='{num_processo}']]")
        if not linhas:
            logging.error(f"{num_processo}: Processo não encontrado.")
            raise Exception("Processo não encontrado")
        cols = linhas[0].find_elements(By.TAG_NAME, "td")
        resultado = {
            "num_processo": cols[0].text.strip(),
            "estado": cols[4].text.strip(),
            "tecnico": cols[5].text.strip(),
        }
        logging.info(f"{num_processo}: Processo encontrado: {resultado}")
        # Clica seta para abrir processo (ajuste se necessário)
        btn_abrir = linhas[0].find_element(By.XPATH, ".//button | .//*[name()='svg']/ancestor::button")
        btn_abrir.click()
        return resultado
    except Exception as e:
        logging.exception(f"{num_processo}: Erro ao pesquisar processo")
        driver.save_screenshot(f"erro_pesq_{num_processo}.png")
        sys.exit(f"Erro crítico ao pesquisar processo {num_processo}. Robot interrompido.")

def upload_e_submeter(driver, num_processo, pdf_folder, timeout=15):
    try:
        sanitized = str(num_processo).replace("/", "_")
        pdf_path = os.path.join(pdf_folder, f"{sanitized}.pdf")
        if not os.path.exists(pdf_path):
            logging.error(f"{num_processo}: PDF não encontrado: {pdf_path}")
            raise FileNotFoundError(f"PDF não encontrado: {pdf_path}")

        # Pode ser desnecessário se já estiver na página certa
        # driver.get(f"{LOGIN_URL}/FinishProcess")
        human_delay()

        # Botão carregar termo da seção Passo 2
        carregar_btn = WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((
                By.XPATH, "//button[.//span[contains(text(),'Carregar termo de responsabilidade') or contains(text(),'Carregar termo')]]"
            ))
        )
        input_file = driver.find_element(By.XPATH, "//input[@type='file' and @accept='.pdf']")
        driver.execute_script("arguments[0].style.display = 'block';", input_file)  # Desoculta o input se necessário
        input_file.send_keys(pdf_path)
        logging.info(f"{num_processo}: Upload iniciado: {pdf_path}")
        human_delay(0.8, 2.2)
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Carregado') or contains(text(),'Sucesso')]"))
        )
        logging.info(f"{num_processo}: Upload concluído com sucesso.")

        checkbox = driver.find_element(By.XPATH, "//input[@type='checkbox']")
        if not checkbox.is_selected():
            checkbox.click()
        logging.info(f"{num_processo}: Declaração aceite.")

        btn_submeter = driver.find_element(By.XPATH, "//button[contains(.,'Submeter processo')]")
        btn_submeter.click()
        logging.info(f"{num_processo}: Clique no Submeter realizado.")

        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, "//span[contains(text(),'Submetido') or contains(text(),'sucesso') or contains(text(),'Em validação')]"))
        )
        logging.info(f"{num_processo}: Processo submetido com sucesso!")
        print(f"{num_processo}: Processo submetido!")
    except Exception as e:
        logging.exception(f"{num_processo}: Erro no upload/submissão: {e}")
        driver.save_screenshot(f"erro_upload_{num_processo}.png")
        sys.exit(f"Erro durante upload/submissão do processo {num_processo}. Robot interrompido.")

def main():
    driver = setup_driver(headless=False)  # Mude para True para modo invisível
    try:
        login(driver)
        for num_processo in PROCESS_LIST:
            proc = pesquisar_processo(driver, num_processo)
            if proc["estado"].lower() != "aguarda termo de responsabilidade":
                logging.info(f"{num_processo}: Estado inválido ({proc['estado']})")
                continue
            # Adapte aqui se quiser validar também o técnico autenticado
            upload_e_submeter(driver, num_processo, PDF_FOLDER)
    finally:
        driver.quit()
        print("Robot terminado. Verifique os logs.")

if __name__ == "__main__":
    main()