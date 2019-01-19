#
# Parts of this code come from cpp-ethereum

# cpp-ethereum is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# cpp-ethereum is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# See <http://www.gnu.org/licenses/> for a copy of the licence.

#!/usr/bin/env python3

"""
JSON-RPC Proxy
This Python script provides HTTP proxy to Unix Socket based JSON-RPC servers.
Check out --help option for more information.
Build with cython:
cython rpcproxy.py --embed
gcc -O3 -I /usr/include/python3.5m -o rpcproxy rpcproxy.c \
-Wl,-Bstatic -lpython3.5m -lz -lexpat -lutil -Wl,-Bdynamic -lpthread -ldl -lm
"""

import asyncio
import websockets
import errno
import socket
import sys
import time
import json

from urllib.parse import urlparse

try:
    from json import JSONDecodeError
except ImportError:
    JSONDecodeError = ValueError

from eth_utils import (
    to_bytes,
    to_text,
)

from os import path

if sys.platform == 'win32':
    import win32file
    import pywintypes



VERSION = '0.2'
BUFSIZE = 4096
DELIMITER = ord('}')
BACKEND_CONNECTION_TIMEOUT=5
INFO = """JSON-RPC Proxy
Version:  {version}
Proxy:    {proxy_url}
Backend:  {backend_url} (connected: {connected})
"""


class BackendError(Exception):
    pass

class UnixSocketConnector(object):
    """Unix Domain Socket connector. Connects to socket lazily."""

    def __init__(self, socket_path):
        self._socket_path = socket_path
        self._socket = None

    @staticmethod
    def _get_error_message(os_error_number):
        if os_error_number == errno.ENOENT:
            return "Unix Domain Socket '{}' does not exist"
        if os_error_number == errno.ECONNREFUSED:
            return "Connection to '{}' refused"
        return "Unknown error when connecting to '{}'"

    def socket(self):
        """Returns connected socket."""
        if self._socket is None:
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(self._socket_path)
                s.settimeout(1)
                # Assign last, to keep it None in case of exception.
                self._socket = s
            except OSError as ex:
                msg = self._get_error_message(ex.errno)
                err = BackendError(msg.format(self._socket_path))
                raise err from ex
        return self._socket

    def close(self):
        if self._socket is not None:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            self._socket = None

    def is_connected(self):
        return self._socket is not None

    def check_connection(self, timeout):
        SLEEPTIME = 0.1
        wait_time = 0.0
        last_exception = None
        while True:
            try:
                if self.socket():
                    break
            except BackendError as ex:
                last_exception = ex  # Ignore backed errors for some time.

            time.sleep(SLEEPTIME)
            wait_time += SLEEPTIME
            if wait_time > timeout:
                raise last_exception if last_exception else TimeoutError

    def recv(self, max_length):
        return self.socket().recv(max_length)

    def sendall(self, data):
        try:
            return self.socket().sendall(data)
        except OSError as ex:
            if ex.errno == errno.EPIPE:
                # The connection was terminated by the backend. Try reconnect.
                self.close()
                return self.socket().sendall(data)
            else:
                raise


class NamedPipeConnector(object):
    """Windows named pipe simulating socket."""

    def __init__(self, ipc_path):
        try:
            self.handle = win32file.CreateFile(
                ipc_path, win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0, None, win32file.OPEN_EXISTING, 0, None)
        except pywintypes.error as err:
            raise IOError(err)

    def is_connected(self):
        return True

    def check_connection(self, timeout):
        pass

    def recv(self, max_length):
        (err, data) = win32file.ReadFile(self.handle, max_length)
        if err:
            raise IOError(err)
        return data

    def sendall(self, data):
        return win32file.WriteFile(self.handle, data)

    def close(self):
        self.handle.close()


def get_ipc_connector(ipc_path):
    if sys.platform == 'win32':
        return NamedPipeConnector(ipc_path)
    return UnixSocketConnector(ipc_path)



class Proxy:

    def __init__(self, websocket_url, backend_path):
        self.websocket_url = websocket_url

        url = urlparse(websocket_url)
        assert url.scheme == 'ws'
        self.hostname, self.port = url.hostname, url.port

        self.backend_address = path.expanduser(backend_path)

        self.keepalive_timeout = 60

    def process(self, request):
        self.conn.sendall(request)

        response = b''
        while True:
            r = self.conn.recv(BUFSIZE)

            response += r
            try:
                json.loads(to_text(response))
            except JSONDecodeError:
                continue
            else:
                return response

        return response




    async def interface(self, websocket, path):
        while websocket.open:
            try:
                request = await asyncio.wait_for(websocket.recv(), timeout = self.keepalive_timeout)
            except websockets.exceptions.ConnectionClosed:
                break
            except asyncio.TimeoutError:
                break

            print("request: {}".format(request))
            response = self.process(request.encode('utf-8'))
            print("response: {}".format(response))
            await websocket.send(response.decode('utf-8'))

    def run(self):
        self.conn = get_ipc_connector(self.backend_address)
        self.conn.check_connection(timeout=BACKEND_CONNECTION_TIMEOUT)

        start_server = websockets.serve(self.interface, self.hostname, self.port)

        print("JSON-RPC Websocket Proxy: {} -> {}".format(
            self.backend_address, self.websocket_url), file=sys.stderr, flush=True)

        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()


if __name__ == '__main__':
    print('starting')
    backend_path = '/home/tommy/.local/share/helios/mainnet/jsonrpc.ipc'
    websocket_url = 'ws://0.0.0.0:30304'
    proxy = Proxy(websocket_url, backend_path)
    proxy.run()
    print('finished')

