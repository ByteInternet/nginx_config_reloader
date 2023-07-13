from setuptools import find_packages, setup

setup(
    name="nginx_config_reloader",
    version="20230320.095135",
    packages=find_packages(exclude=["test*"]),
    url="https://github.com/ByteInternet/nginx_config_reloader",
    license="",
    author="Willem de Groot",
    author_email="willem@byte.nl",
    description="nginx config file monitor and reloader",
    entry_points={
        "console_scripts": ["nginx_config_reloader = nginx_config_reloader:main"]
    },
    install_requires=["pyinotify>=0.9.2", "nats-python"],
    test_suite="tests",
)
