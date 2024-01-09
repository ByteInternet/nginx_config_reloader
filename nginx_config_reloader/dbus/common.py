from dasbus.connection import SystemMessageBus
from dasbus.identifier import DBusServiceIdentifier

SYSTEM_BUS = SystemMessageBus()

NGINX_CONFIG_RELOADER = DBusServiceIdentifier(
    namespace=("com", "hypernode", "NginxConfigReloader"),
    message_bus=SYSTEM_BUS,
)
