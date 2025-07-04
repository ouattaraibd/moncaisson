#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import ssl
from django.core.management import execute_from_command_line
from django.core.servers.basehttp import ThreadedWSGIServer

def create_ssl_socket(sock):
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain('cert.pem', 'key.pem')
    return context.wrap_socket(sock, server_side=True)

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moncaisson.settings")
    
    if 'runssl' in sys.argv:
        ThreadedWSGIServer.socket = create_ssl_socket(ThreadedWSGIServer.socket)
        sys.argv[sys.argv.index('runssl')] = 'runserver'
    
    execute_from_command_line(sys.argv)
    
def run_ssl_server(addr, port, wsgi_handler, ipv6=False):
    server_address = (addr, port)
    httpd = ThreadedWSGIServer(
        server_address,
        WSGIRequestHandler,
        ipv6=ipv6
    )
    
    # Configuration SSL
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain('cert.pem', 'key.pem')
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
    
    httpd.set_app(wsgi_handler)
    httpd.serve_forever()

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moncaisson.settings")
    
    if 'runssl' in sys.argv:
        from django.core.wsgi import get_wsgi_application
        application = get_wsgi_application()
        run_ssl_server('127.0.0.1', 8000, application)
    else:
        execute_from_command_line(sys.argv)

def main():
    """Run administrative tasks."""
    os.environ['DJANGO_SETTINGS_MODULE'] = 'moncaisson.settings'
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

