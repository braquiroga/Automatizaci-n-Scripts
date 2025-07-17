import os
import smtplib
from email.message import EmailMessage
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from dotenv import load_dotenv
from tabulate import tabulate

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
        print(f"Captura de pantalla guardada: {screenshot_path}")
        return counter_element.text
    except (TimeoutException, Exception) as e:
        print(f"Error: No se pudo encontrar el elemento del contador en {url} para {printer_name}. Detalle: {e}")
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
        print(f"Error: No se pudo realizar el login para {printer_name}.")
        return "No encontrado"

def parse_printers(printer_data):

    printers = []
    for entry in printer_data.split(";"):
        ip, name = entry.split(",")
        printers.append({"ip": ip.strip(), "name": name.strip()})
    return printers

def attach_file(message, file_path):

    try:

        if not os.path.exists(file_path):
            print(f"Error: El archivo {file_path} no existe.")
            return


        with open(file_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)

            # Configurar encabezado del archivo adjunto
            filename = os.path.basename(file_path)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{filename}"'
            )
            message.attach(part)
            print(f"Archivo adjuntado correctamente: {filename}")
    except Exception as e:
        print(f"Error al adjuntar {file_path}: {e}")


def send_email(headers, counters, screenshot_dir):

    smtp_server = os.getenv("SMTP_SERVER")
    smtp_port = int(os.getenv("SMTP_PORT"))
    sender_email = os.getenv("SENDER_EMAIL")
    sender_password = os.getenv("SENDER_PASSWORD")
    receiver_email = os.getenv("RECEIVER_EMAIL")

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

    for screenshot_file in sorted(os.listdir(screenshot_dir)):
        screenshot_path = os.path.join(screenshot_dir, screenshot_file)
        try:
            with open(screenshot_path, "rb") as attachment:
                file_data = attachment.read()
                file_name = os.path.basename(screenshot_path)
                message.add_attachment(
                    file_data,
                    maintype="image",
                    subtype="png",
                    filename=file_name,
                )
            print(f"Archivo adjuntado correctamente: {file_name}")
        except Exception as e:
            print(f"Error al adjuntar {screenshot_file}: {e}")

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(message)
            print(f"Correo enviado exitosamente a {receiver_email}")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
    finally:
        for screenshot_file in os.listdir(screenshot_dir):
            os.remove(os.path.join(screenshot_dir, screenshot_file))
        print("Capturas de pantalla eliminadas.")

def main():
    load_dotenv()

    screenshot_dir = "screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)
    counters = []

    ricoh_printers = parse_printers(os.getenv("RICOH_PRINTERS"))
    brother_printers = parse_printers(os.getenv("BROTHER_PRINTERS"))
    brother_passwords = os.getenv("BROTHER_PASSWORDS").split(",")
    lexmark_printers = parse_printers(os.getenv("LEXMARK_PRINTERS"))

    ricoh_url = "https://{}/counter.asp?Lang=en-us"
    ricoh_xpath = "/html/body/div/table/tbody/tr/td[2]/table[2]/tbody/tr[2]/td/table/tbody/tr/td[2]/table/tbody/tr/td/table/tbody/tr[3]/td/table/tbody/tr[2]/td[3]"

    brother_login_url = "http://{}/etc/loginerror.html?url=%2Fgeneral%2Finformation%2Ehtml%3Fkind%3Ditem"
    brother_login_xpath = "/html/body/div[2]/div/div/div[2]/form/div/input[1]"
    brother_counter_url = "https://{}/general/information.html?kind=item"
    brother_xpath = "/html/body/div[3]/div/div/div/div[2]/form/div[6]/dl/dd[1]"

    lexmark_url = "https://{}/cgi-bin/dynamic/printer/config/reports/devicestatistics.html"
    lexmark_xpath = "/html/body/table[5]/tbody/tr[21]/td[2]/p"

    driver = setup_driver()
    try:
        for printer in ricoh_printers:
            url = ricoh_url.format(printer["ip"])
            counter = get_counter(driver, url, ricoh_xpath, printer["name"], screenshot_dir)
            counters.append(["Ricoh P311", printer["name"], printer["ip"], counter])

        for printer, password in zip(brother_printers, brother_passwords):
            login_url = brother_login_url.format(printer["ip"])
            counter_url = brother_counter_url.format(printer["ip"])
            counter = login_and_get_counter(driver, login_url, brother_login_xpath, password, counter_url, brother_xpath, printer["name"], screenshot_dir)
            counters.append(["Brother DCP-T820DW", printer["name"], printer["ip"], counter])

        for printer in lexmark_printers:
            url = lexmark_url.format(printer["ip"])
            counter = get_counter(driver, url, lexmark_xpath, printer["name"], screenshot_dir)
            counters.append(["Lexmark XM1145", printer["name"], printer["ip"], counter])

    finally:
        driver.quit()

    headers = ["Modelo", "Nombre", "IP", "Contador"]
    send_email(headers, counters, screenshot_dir)

if __name__ == "__main__":
    main()
