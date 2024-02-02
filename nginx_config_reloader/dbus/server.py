from dasbus.server.interface import dbus_interface, dbus_signal
from dasbus.server.property import emits_properties_changed
from dasbus.server.template import InterfaceTemplate

from nginx_config_reloader.dbus.common import NGINX_CONFIG_RELOADER


@dbus_interface(NGINX_CONFIG_RELOADER.interface_name)
class NginxConfigReloaderInterface(InterfaceTemplate):
    def connect_signals(self):
        self.implementation.reloaded.connect(self.ConfigReloaded)

    @dbus_signal
    def ConfigReloaded(self):
        """Signal that the config was reloaded"""

    @emits_properties_changed
    def Reload(self):
        """Mark the last reload at current time."""
        # send_signal=False because we don't want to emit the signal
        self.implementation.reload(send_signal=False)
