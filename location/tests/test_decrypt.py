from cryptography.fernet import Fernet
import os
from dotenv import load_dotenv

load_dotenv()

def test_decrypt(var_name):
    try:
        cle = os.getenv('ENCRYPTION_KEY')
        cipher = Fernet(cle.encode())
        valeur = os.getenv(var_name)
        print(f"{var_name}: {cipher.decrypt(valeur.encode()).decode()}")
        return True
    except Exception as e:
        print(f"Erreur avec {var_name}: {str(e)}")
        return False

test_decrypt('STRIPE_API_KEY')
test_decrypt('STRIPE_WEBHOOK_SECRET')
test_decrypt('ORANGE_MONEY_API_KEY')
test_decrypt('ORANGE_MONEY_MERCHANT_CODE')