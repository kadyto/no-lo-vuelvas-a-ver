"""Synthetic Requests transport: real request preparation, no sockets or external network."""

from email.message import Message
from types import SimpleNamespace

import httpx
import requests
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict


class ResponseStream:
    def __init__(self, response):
        self.response = response
        message = Message()
        for name, value in response.headers.multi_items():
            message[name] = value
        self._original_response = SimpleNamespace(msg=message)

    def stream(self, amount, decode_content=True):
        yield from self.response.iter_bytes(chunk_size=amount)

    def close(self):
        self.response.close()

    def release_conn(self):
        pass


class RequestsTransport(BaseAdapter):
    def __init__(self, handler):
        self.handler = handler

    def send(self, request, **kwargs):
        assert kwargs["stream"] is True
        assert kwargs["verify"] is True or (isinstance(kwargs["verify"], str) and kwargs["verify"])
        assert kwargs["timeout"] == (4, 8)
        incoming = httpx.Request(request.method, request.url, headers=request.headers)
        response = self.handler(incoming)
        result = requests.Response()
        result.request = request
        result.url = request.url
        result.status_code = response.status_code
        result.headers = CaseInsensitiveDict(response.headers)
        result.raw = ResponseStream(response)
        return result

    def close(self):
        pass
