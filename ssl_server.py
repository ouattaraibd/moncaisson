import os
import sys
import socket
from django.core.management import execute_from_command_line
from django.core.servers.basehttp import ThreadedWSGIServer, WSGIRequestHandler
import ssl
from django.core.wsgi import get_wsgi_application

def run_ssl_server():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moncaisson.settings")
    application = get_wsgi_application()
    
    server_address = ('127.0.0.1', 8000)
    httpd = ThreadedWSGIServer(
        server_address,
        WSGIRequestHandler
    )
    
    # Configuration SSL moderne
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    
    # Configuration des versions minimales et maximales de TLS
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    ssl_context.maximum_version = ssl.TLSVersion.TLSv1_3
    
    # Configuration des cipher suites
    ssl_context.set_ciphers('ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-CHACHA20-POLY1305:ECDHE-RSA-CHACHA20-POLY1305')
    
    # Chargement des certificats
    try:
        ssl_context.load_default_certs()
        ssl_context.load_cert_chain('cert.pem', 'key.pem')
    except Exception as e:
        print(f"Erreur de chargement des certificats: {str(e)}")
        sys.exit(1)
    
    # Configuration du socket
    httpd.socket = ssl_context.wrap_socket(
        httpd.socket,
        server_side=True,
        do_handshake_on_connect=True,
        suppress_ragged_eofs=True
    )
    
    # Permet la réutilisation de l'adresse
    httpd.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    print(f"✓ Serveur HTTPS démarré sur https://{server_address[0]}:{server_address[1]}")
    print(f"Certificat: {os.path.abspath('cert.pem')}")
    print(f"Clé: {os.path.abspath('key.pem')}")
    print("Appuyez sur Ctrl+C pour arrêter le serveur")
    
    try:
        httpd.set_app(application)
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur...")
        httpd.shutdown()
        sys.exit(0)
    except Exception as e:
        print(f"\nErreur du serveur: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Vérification des fichiers de certificat
    if not all(os.path.exists(f) for f in ['cert.pem', 'key.pem']):
        print("Erreur: cert.pem ou key.pem manquant")
        print("Générez-les avec cette commande:")
        print("openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365 -subj \"/CN=localhost\"")
        sys.exit(1)
    
    run_ssl_server()