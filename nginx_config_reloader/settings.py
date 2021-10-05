DIR_TO_WATCH = '/data/web/nginx'
MAIN_CONFIG_DIR = '/etc/nginx'
CUSTOM_CONFIG_DIR = MAIN_CONFIG_DIR + '/app'
BACKUP_CONFIG_DIR = MAIN_CONFIG_DIR + '/app_bak'
UNPRIVILEGED_GID = 1000  # This is the 'app' user on a Hypernode, or generally the first user on any system
UNPRIVILEGED_UID = 1000  # This is the 'app' user on a Hypernode, or generally the first user on any system
HANDLE_SLEEP = 5  # Time to wait before reloading. This is handy in case multiple files are touched.

MAGENTO_CONF = MAIN_CONFIG_DIR + '/magento.conf'
MAGENTO1_CONF = MAIN_CONFIG_DIR + '/magento1.conf'
MAGENTO2_CONF = MAIN_CONFIG_DIR + '/magento2.conf'

NGINX = '/usr/sbin/nginx'
NGINX_PID_FILE = '/var/run/nginx.pid'
ERROR_FILE = 'nginx_error_output'

WATCH_IGNORE_FILES = (
    # glob patterns
    '.*',
    '*~',
    '*.save',
    ERROR_FILE
)
SYNC_IGNORE_FILES = WATCH_IGNORE_FILES + ('*.flag',)
SYSLOG_SOCKET = '/dev/log'

# Using include or load_module is forbidden unless
# - it is in a comment
# - the include is a relative path but does not contain  ..
# - the include is absolute but in the MAIN_CONFIG_DIR
# - but not in the BACKUP_CONFIG_DIR
# - also takes into account double slashes
# Because of bash escaping problems we define quote's in octal format \042 == ' and \047 == "

# For security reasons the following nginx configuration parameters are forbidden
FORBIDDEN_CONFIG_REGEX = [
    ("client_body_temp_path", "Usage of configuration parameter client_body_temp_path is not allowed.\n"),
    ("^(?!\s*#)\s*(access|error)_log\s*"
     "(\\042|\\047)?\s*"
     "(?!(off|on|/+data/+|syslog:server=(?!unix)))(?=.*\.\.|/+(?!data)|\w)"
     "(\\042|\\047)?\s*",
     "It's not allowed store access_log or error_log outside of /data/.\n"),
    ("^(?!\s*#)\s*(include|load_module)\s*"
     "(\\042|\\047)?\s*"
     "(?=.*\.\.|/+etc/+nginx/+app_bak|/+(?!etc/+nginx))"
     "(\\042|\\047)?\s*",
     "You are not allowed to use include or load_module in the nginx config unless the path is relative "
     "or in the main nginx config directory. "
     "See the NGINX dos and don'ts in this article: "
     "https://support.hypernode.com/knowledgebase/how-to-use-nginx/\n"),
    ("init_by_lua", "Usage of Lua initialization is not allowed.\n"),
]
