# nginx config reloader

Utility to check user-supplied nginx config files, install them, and reload
nginx configuration if they work.

Config files are taken from `/data/web/nginx` and moved to `/etc/nginx/app`.
Nginx is used to test if the config is valid. If it is, the nginx config will
be reloaded. If not, the original configuration files will be restored, and
the error message from nginx will be placed in `/data/web/nginx/nginx_error_output`

## Installation

```bash
python setup.py install
```

or

```bash
pip install -e git+https://github.com/ByteInternet/nginx_config_reloader#egg=nginx_config_reloader
```

## Usage

`nginx_config_reloader` to check/copy config files and reload nginx

`nginx_config_reloader --daemon` to fork to background and monitor changes

`nginx_config_reloader --monitor` to stay in foreground and monitor changes


## Running tests

```bash
pip install -r requirements.txt
tox
```

## Building debian packages

To create a package from "master" branch (for production) run the "build.sh" script

```bash
./build.sh
```

This would create a release tag as well.

If you'd like to create a Debian package of a development branch (without tagging, etc.)
you can use "_build_local.sh" script

```bash
./_build_local.sh
```
