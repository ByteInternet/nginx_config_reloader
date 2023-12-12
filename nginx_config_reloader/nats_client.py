import argparse
import logging
import ssl
from typing import Optional

import nats
from nats.aio.client import Client

logger = logging.getLogger(__name__)


def get_default_nats_ssl_context() -> dict:
    # NATS SSL context is defined in /etc/defaults/nginx_config_reloader
    try:
        ssl_context = {}
        with open("/etc/default/nginx_config_reloader") as f:
            for line in f.readlines():
                if line.startswith("NATS_CERT="):
                    ssl_context["crt"] = line.split("=")[1].strip()
                elif line.startswith("NATS_KEY="):
                    ssl_context["key"] = line.split("=")[1].strip()
                elif line.startswith("NATS_CA="):
                    ssl_context["ca"] = line.split("=")[1].strip()
        return ssl_context
    except FileNotFoundError:
        pass
    logger.warning(f"Couldn't find NATS_SSL_CONTEXT, assuming no SSL")
    return {}


def get_ssl_context(args: Optional[argparse.Namespace] = None):
    if args and args.nats_cert and args.nats_key and args.nats_ca:
        return {"crt": args.nats_cert, "key": args.nats_key, "ca": args.nats_ca}
    return get_default_nats_ssl_context()


async def error_cb(e):
    logger.warning(f"Error: {e}")


async def reconnected_cb():
    logger.info("Got reconnected to NATS...")


async def get_nats_client(server) -> Client:
    logger.debug(f"Connecting to NATS server on {server}")
    options = {
        "servers": [server],
        "error_cb": error_cb,
        "reconnected_cb": reconnected_cb,
        "drain_timeout": 3,
        "max_reconnect_attempts": 5,  # 3 tries in total
        "connect_timeout": 1,
        "reconnect_time_wait": 1,
    }

    ssl_context = get_ssl_context()
    if ssl_context:
        ssl_ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        ssl_ctx.load_verify_locations(ssl_context.get("ca"))
        ssl_ctx.load_cert_chain(
            certfile=ssl_context.get("crt"), keyfile=ssl_context.get("key")
        )
        options["tls"] = ssl_ctx

    nc = await nats.connect(**options)
    return nc
