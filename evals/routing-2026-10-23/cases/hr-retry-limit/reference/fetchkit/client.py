"""The client: send a request, retry on transport errors."""

import time

from fetchkit.defaults import DEFAULTS
from fetchkit.errors import RetriesExhausted, TransportError
from fetchkit.settings import load_settings


class Client:
    def __init__(self, transport, settings=None, sleep=time.sleep):
        self.transport = transport
        self.settings = settings if settings is not None else load_settings()
        self.sleep = sleep
        # number of extra attempts allowed after the first one
        retries = self.settings.get("max_retries")
        self.max_retries = DEFAULTS["max_retries"] if retries is None else retries

    def fetch(self, url):
        attempts = 0
        while True:
            attempts += 1
            try:
                return self.transport.send(url, timeout=self.settings["timeout"])
            except TransportError as exc:
                if attempts > self.max_retries:
                    raise RetriesExhausted(url, attempts) from exc
                self.sleep(self.settings["backoff"] * attempts)
