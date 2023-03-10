from pynats import NATSClient


def initialize_nats(url: str) -> NATSClient:
    nc = NATSClient(url)
    nc.connect()
    nc.ping()
    return nc
