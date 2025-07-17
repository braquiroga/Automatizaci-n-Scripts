import random
import string
from pyad import pyad
from pyad.pyadexceptions import InvalidObjectException, noObjectFoundException
from dotenv import load_dotenv
import os

load_dotenv()

ldap_server = os.getenv("LDAP_SERVER")
username = os.getenv("USERNAME")
password = os.getenv("PASSWORD")

pyad.set_defaults(ldap_server=ldap_server, username=username, password=password)
def generate_random_name(prefix='PC'):
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"{prefix}_{suffix}"

def generate_random_mac():
    return ':'.join(['{:02x}'.format(random.randint(0, 255)) for _ in range(6)]).upper()

def create_computer(name):
    try:
       container_dn = "CN=Computers,DC=soporte,DC=lnx" 
        
    
        try:
            container = pyad.adcontainer.ADContainer.from_dn(container_dn)
        except noObjectFoundException:
            print(f"El contenedor '{container_dn}' no se encontró.")
            return
        

        computer = pyad.adcomputer.ADComputer.create(name, container)
        
        mac_address = generate_random_mac()
        computer.update(description=f"MAC: {mac_address}")
        
        print(f"Equipo '{name}' creado exitosamente con MAC '{mac_address}'.")
        
    except InvalidObjectException as e:
        print(f"Error creando Equipo '{name}': {e}")
    except Exception as e:
        print(f"Error general: {e}")

def main():
    for i in range(20):
        computer_name = generate_random_name()
        create_computer(computer_name)
        print(f"Creando Equipo {i + 1}/20: {computer_name}")

if __name__ == "__main__":
    main()
