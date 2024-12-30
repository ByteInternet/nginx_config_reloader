import json
import subprocess
import os

from nginx_config_reloader.settings import MAIN_CONFIG_DIR

def directory_is_unmounted(path):
    output = subprocess.check_output(
        ["systemctl", "list-units", "-t", "mount", "--all", "-o", "json"],
        encoding="utf-8",
    )
    units = json.loads(output)
    for unit in units:
        if unit["description"] == path:
            return unit["active"] != "active" or unit["sub"] != "mounted"
    return False

def can_write_to_main_config_dir():
    return os.access(MAIN_CONFIG_DIR, os.W_OK)
