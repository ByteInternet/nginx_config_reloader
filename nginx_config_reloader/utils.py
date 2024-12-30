import json
import subprocess
import os

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
