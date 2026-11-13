"""Jalankan aplikasi Usaha Baru.

    python run.py            -> server di http://localhost:5000 (bisa diakses dari HP di WiFi yang sama)
    python run.py --debug    -> mode pengembangan (auto-reload)
"""
import socket
import sys

from app import create_app

HOST = "0.0.0.0"
PORT = 5000


def ip_lokal():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


def main():
    app = create_app()
    if "--debug" in sys.argv:
        app.run(host=HOST, port=PORT, debug=True)
        return

    from waitress import serve

    print(f"Usaha Baru berjalan di http://localhost:{PORT}")
    ip = ip_lokal()
    if ip:
        print(f"Dari HP (WiFi yang sama): http://{ip}:{PORT}")
    print("Tekan Ctrl+C untuk berhenti.")
    serve(app, host=HOST, port=PORT)


if __name__ == "__main__":
    main()
