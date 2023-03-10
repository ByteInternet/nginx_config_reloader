import logging

from pynats import NATSClient

from nginx_config_reloader.settings import NATS_RELOAD_BODY, NATS_SUBJECT

logger = logging.getLogger(__name__)


def initialize_nats(url: str) -> NATSClient:
    logger.debug(f"Initializing NATS connection to {url}")

    nc = NATSClient(url)
    nc.connect()
    nc.ping()
    return nc


def client_to_url(nc: NATSClient) -> str:
    url = f"{nc._conn_options.scheme}://{nc._conn_options.hostname}:{nc._conn_options.port}"
    logger.debug(f"Converting NATS client to URL: {url}")
    return url


def publish_nats_message(nc: NATSClient) -> NATSClient:
    logger.debug(f"Publishing to NATS: {NATS_SUBJECT} {NATS_RELOAD_BODY!r}")
    try:
        nc.publish(subject=NATS_SUBJECT, payload=NATS_RELOAD_BODY)
    except Exception as e:
        logger.exception(f"NATS publish failed, recreating connection: {e}")
        return initialize_nats(client_to_url(nc))
    return nc
