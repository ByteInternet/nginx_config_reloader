import json
import os
import subprocess


def apply_chmod(path, mode, preexec_fn=None):
    if isinstance(mode, int):
        chmod_mode = oct(mode)[2:]
        stat_mode = mode
    else:
        chmod_mode = str(mode)
        stat_mode = int(chmod_mode, 8)

    try:
        if os.stat(path).st_mode & 0o777 == stat_mode:
            return
    except OSError:
        pass

    subprocess.check_call(
        ["chmod", chmod_mode, path],
        preexec_fn=preexec_fn,
    )


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
