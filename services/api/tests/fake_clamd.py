"""A stand-in for the ClamAV daemon in tests: it speaks INSTREAM and calls a stream infected
when it holds the EICAR test string, as the real ClamAV does. The string is put together at
run time so that no antivirus flags this file."""

import socket
import socketserver
import struct
import threading

EICAR = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" + "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*").encode()
NAME = "Eicar-Test-Signature"


def _read_exact(sock: socket.socket, n: int) -> bytes:
    data = b""
    while len(data) < n:
        part = sock.recv(n - len(data))
        if not part:
            raise ConnectionError("client went away")
        data += part
    return data


class _Handler(socketserver.BaseRequestHandler):
    def handle(self) -> None:
        sock = self.request
        command = b""
        while not command.endswith(b"\0"):
            command += _read_exact(sock, 1)
        assert command == b"zINSTREAM\0", command
        body = b""
        while size := struct.unpack(">I", _read_exact(sock, 4))[0]:
            body += _read_exact(sock, size)
        reply = f"stream: {NAME} FOUND" if EICAR in body else "stream: OK"
        sock.sendall(reply.encode() + b"\0")


class _Server(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def start() -> tuple[str, int]:
    """Serve on a free local port for the whole test run; returns (host, port)."""
    server = _Server(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address
