import logging

from pynats import NATSClient

logger = logging.getLogger(__name__)


def initialize_nats(url: str) -> NATSClient:
    logger.debug(f"Initializing NATS connection to {url}")

    nc = NATSClient(url)
    nc.connect()
    nc.ping()
    return nc
