"""Run the local Delta demonstration server."""

from wsgiref.simple_server import make_server

from delta.web import DeltaWebApp


if __name__ == "__main__":
    with make_server("127.0.0.1", 8000, DeltaWebApp()) as server:
        print("Delta demo listening at http://127.0.0.1:8000")
        server.serve_forever()
