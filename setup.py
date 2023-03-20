from setuptools import find_packages, setup

setup(
    name="nginx_config_reloader",
    version="20230209.104230",
    packages=find_packages(exclude=["test*"]),
    url="https://github.com/ByteInternet/nginx_config_reloader",
    license="",
    author="Willem de Groot",
    author_email="willem@byte.nl",
    description="nginx config file monitor and reloader",
    entry_points={
        "console_scripts": ["nginx_config_reloader = nginx_config_reloader:main"]
    },
    install_requires=["pyinotify>=0.9.2", "nats-python==0.8.0"],
    test_suite="tests",
)
