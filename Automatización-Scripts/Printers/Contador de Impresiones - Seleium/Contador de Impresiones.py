import os
import smtplib
from email.message import EmailMessage
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv

def setup_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--start-maximized")
    options.add_argument("--window-size=1920,1080")
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    return webdriver.Chrome(options=options)

def get_counter(driver, url, xpath, printer_name, screenshot_dir):
    try:
        driver.get(url)
        counter_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", counter_element)
        screenshot_path = os.path.join(screenshot_dir, f"{printer_name}.png")
        driver.save_screenshot(screenshot_path)
        print(f"Captura guardada: {screenshot_path}")
        return counter_element.text.strip()
    except TimeoutException:
        print(f"No se encontró el contador en {url} para {printer_name}.")
        return "No encontrado"

def login_and_get_counter(driver, login_url, login_xpath, password, counter_url, counter_xpath, printer_name, screenshot_dir):
    try:
        driver.get(login_url)
        input_element = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, login_xpath))
        )
        input_element.send_keys(password)
        input_element.submit()
        WebDriverWait(driver, 15).until(EC.url_changes(login_url))
        return get_counter(driver, counter_url, counter_xpath, printer_name, screenshot_dir)
    except TimeoutException:
        print(f"Error en login para {printer_name}.")
        return "No encontrado"

def parse_printers(printer_data):
    printers = []
    if printer_data:
        for entry in printer_data.split(";"):
            if entry.strip():
                parts = entry.split(",")
                if len(parts) == 2:
                    ip, name = parts[0].strip(), parts[1].strip()
                    printers.append({"ip": ip, "name": name})
    return printers

def send_email(headers, counters, screenshot_dir):
    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT"))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    receiver_email = os.getenv("RECEIVER_EMAIL")

    # Crear tabla HTML para el correo
    table_rows = ""
    for row in counters:
        table_rows += f"""
        <tr>
            <td style="border: 1px solid #ddd; padding: 8px;">{row[0]}</td>
            <td style="border: 1px solid #ddd; padding: 8px;">{row[1]}</td>
            <td style="border: 1px solid #ddd; padding: 8px;">{row[2]}</td>
            <td style="border: 1px solid #ddd; padding: 8px;">{row[3]}</td>
        </tr>
        """

    email_content = f"""
    <html>
    <body>
        <h2>Reporte de Contadores de Impresoras</h2>
        <table style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr style="background-color: #f2f2f2;">
                    <th style="border: 1px solid #ddd; padding: 8px;">Modelo</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Nombre</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">IP</th>
                    <th style="border: 1px solid #ddd; padding: 8px;">Contador</th>
                </tr>
            </thead>
            <tbody>
                {table_rows}
            </tbody>
        </table>
        <p>Se adjuntan las capturas de pantalla de los contadores.</p>
    </body>
    </html>
    """

    message = EmailMessage()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = "Reporte de Contadores de Impresoras"
    message.set_content("Por favor, vea los datos adjuntos en formato HTML y las capturas de pantalla.")
    message.add_alternative(email_content, subtype="html")

    # Adjuntar capturas
    for screenshot_file in sorted(os.listdir(screenshot_dir)):
        path = os.path.join(screenshot_dir, screenshot_file)
        try:
            with open(path, "rb") as f:
                file_data = f.read()
                message.add_attachment(file_data, maintype="image", subtype="png", filename=screenshot_file)
            print(f"Adjuntado: {screenshot_file}")
        except Exception as e:
            print(f"Error adjuntando {screenshot_file}: {e}")

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
            print(f"Correo enviado a {receiver_email}")
    except Exception as e:
        print(f"Error enviando correo: {e}")
    finally:
        # Limpiar capturas
        for file in os.listdir(screenshot_dir):
            os.remove(os.path.join(screenshot_dir, file))
        print("Capturas eliminadas.")

def main():
    load_dotenv()

    screenshot_dir = "screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)
    counters = []

    # Cargar impresoras y datos desde .env
    ricoh_printers = parse_printers(os.getenv("RICOH_PRINTERS"))
    brother_printers = parse_printers(os.getenv("BROTHER_PRINTERS"))
    brother_passwords = os.getenv("BROTHER_PASSWORDS", "").split(",")
    lexmark_printers = parse_printers(os.getenv("LEXMARK_PRINTERS"))
    epson_printers = parse_printers(os.getenv("EPSON_L5590_PRINTERS"))
    develop_printers = parse_printers(os.getenv("DEVELOP_PRINTERS"))

    ricoh_url = os.getenv("RICOH_URL")
    ricoh_xpath = os.getenv("RICOH_XPATH")

    brother_login_url = os.getenv("BROTHER_LOGIN_URL")
    brother_login_xpath = os.getenv("BROTHER_LOGIN_XPATH")
    brother_counter_url = os.getenv("BROTHER_COUNTER_URL")
    brother_xpath = os.getenv("BROTHER_XPATH")

    lexmark_url = os.getenv("LEXMARK_URL")
    lexmark_xpath = os.getenv("LEXMARK_XPATH")

    epson_url = os.getenv("EPSON_L5590_URL")
    epson_xpath = os.getenv("EPSON_L5590_XPATH")

    develop_url = os.getenv("DEVELOP_URL")
    develop_xpath = os.getenv("DEVELOP_XPATH")

    driver = setup_driver()

    try:
        # Ricoh
        for printer in ricoh_printers:
            url = ricoh_url.format(printer["ip"])
            contador = get_counter(driver, url, ricoh_xpath, printer["name"], screenshot_dir)
            counters.append(["Ricoh P311", printer["name"], printer["ip"], contador])

        # Brother
        for printer, pwd in zip(brother_printers, brother_passwords):
            login_url = brother_login_url.format(printer["ip"])
            counter_url = brother_counter_url.format(printer["ip"])
            contador = login_and_get_counter(driver, login_url, brother_login_xpath, pwd, counter_url, brother_xpath, printer["name"], screenshot_dir)
            counters.append(["Brother DCP-T820DW", printer["name"], printer["ip"], contador])

        # Lexmark
        for printer in lexmark_printers:
            url = lexmark_url.format(printer["ip"])
            contador = get_counter(driver, url, lexmark_xpath, printer["name"], screenshot_dir)
            counters.append(["Lexmark XM1145", printer["name"], printer["ip"], contador])

        # Epson L5590
        for printer in epson_printers:
            url = epson_url.format(printer["ip"])
            contador = get_counter(driver, url, epson_xpath, printer["name"], screenshot_dir)
            counters.append(["Epson L5590", printer["name"], printer["ip"], contador])

        # Develop Ineo+ 258
        for printer in develop_printers:
            url = develop_url.format(printer["ip"])
            contador = get_counter(driver, url, develop_xpath, printer["name"], screenshot_dir)
            counters.append(["Develop Ineo+ 258", printer["name"], printer["ip"], contador])

    finally:
        driver.quit()

    headers = ["Modelo", "Nombre", "IP", "Contador"]
    send_email(headers, counters, screenshot_dir)


if __name__ == "__main__":
    main()
