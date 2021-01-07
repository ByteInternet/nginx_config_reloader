import logging
from subprocess import check_output, STDOUT

from nginx_config_reloader.settings import SYNC_IGNORE_FILES

logger = logging.getLogger(__name__)


def safe_copy_files(src, dest):
    cmd = [
        # Adding a / at the end copies contents of the dir and not the dir itself
        'rsync', src + '/', dest,
        # Delete and archive without copying over permissions, aka -da but without -p (-a equals -rlptgoD)
        '-drltgoD',
        '--chown', 'root:root',
        '--copy-links',  # Follow symlinks and copy actual file
        # Dirs default to 0755 to read. Remove setuid bits. Remove executability for others
        '--chmod="D755,-s,Fo-wx"',
        *["--exclude=\"{}\"".format(pattern) for pattern in SYNC_IGNORE_FILES],
    ]
    cmd = " ".join(cmd)
    # shell=True to ensure globs are not escaped
    check_output(cmd, shell=True, stderr=STDOUT)
