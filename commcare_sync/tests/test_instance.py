"""Tests for single-instance detection (commcare_sync/launcher/instance.py)."""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from commcare_sync.launcher.instance import (
    LOOPBACK,
    read_live_instance,
    remove_instance_file,
    write_instance_file,
)


class _AnyResponseHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass  # keep test output quiet


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((LOOPBACK, 0))
        return sock.getsockname()[1]


class TestWriteReadRemoveRoundTrip:
    def test_write_then_read_back(self, tmp_path):
        write_instance_file(tmp_path, port=12345, pid=999)

        contents = json.loads((tmp_path / 'instance.json').read_text())

        assert contents == {'port': 12345, 'pid': 999}

    def test_remove_is_idempotent(self, tmp_path):
        write_instance_file(tmp_path, port=12345, pid=999)

        remove_instance_file(tmp_path)
        remove_instance_file(tmp_path)  # does not raise

        assert not (tmp_path / 'instance.json').exists()


class TestReadLiveInstance:
    def test_live_server_is_detected(self, tmp_path):
        server = HTTPServer((LOOPBACK, 0), _AnyResponseHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            write_instance_file(tmp_path, port=port, pid=1)

            assert read_live_instance(tmp_path) == port
            assert (tmp_path / 'instance.json').exists()
        finally:
            server.shutdown()
            thread.join()

    def test_stale_instance_is_removed(self, tmp_path):
        # A port nothing listens on: bind, then close, so it's free again.
        port = find_free_port()
        write_instance_file(tmp_path, port=port, pid=1)

        assert read_live_instance(tmp_path) is None
        assert not (tmp_path / 'instance.json').exists()

    def test_malformed_json_is_removed(self, tmp_path):
        (tmp_path / 'instance.json').write_text('not json')

        assert read_live_instance(tmp_path) is None
        assert not (tmp_path / 'instance.json').exists()

    def test_missing_file_returns_none(self, tmp_path):
        assert read_live_instance(tmp_path) is None

    def test_missing_port_key_is_removed(self, tmp_path):
        (tmp_path / 'instance.json').write_text(json.dumps({'pid': 1}))

        assert read_live_instance(tmp_path) is None
        assert not (tmp_path / 'instance.json').exists()

    def test_non_integer_port_is_removed(self, tmp_path):
        (tmp_path / 'instance.json').write_text(
            json.dumps({'port': 'not-a-port', 'pid': 1})
        )

        assert read_live_instance(tmp_path) is None
        assert not (tmp_path / 'instance.json').exists()

    def test_boolean_port_is_removed(self, tmp_path):
        # bool is a subclass of int in Python; must not pass as a port.
        (tmp_path / 'instance.json').write_text(
            json.dumps({'port': True, 'pid': 1})
        )

        assert read_live_instance(tmp_path) is None
        assert not (tmp_path / 'instance.json').exists()

    def test_non_http_responder_is_treated_as_stale(self, tmp_path):
        # Something is listening on the port, but it doesn't speak HTTP: the
        # probe must not crash, just treat this the same as "not live".
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind((LOOPBACK, 0))
        server_socket.listen(1)
        port = server_socket.getsockname()[1]

        def respond_with_garbage():
            try:
                conn, _ = server_socket.accept()
            except OSError:
                return
            with conn:
                conn.sendall(b'not an http response\r\n\r\n')

        thread = threading.Thread(target=respond_with_garbage, daemon=True)
        thread.start()
        try:
            write_instance_file(tmp_path, port=port, pid=1)

            assert read_live_instance(tmp_path) is None
            assert not (tmp_path / 'instance.json').exists()
        finally:
            server_socket.close()
            thread.join(timeout=2)
