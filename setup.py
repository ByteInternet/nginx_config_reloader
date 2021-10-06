from setuptools import setup, find_packages

setup(
    name='nginx_config_reloader',
    version="20211006.073146",
    packages=find_packages(exclude=['test*']),
    url='https://github.com/ByteInternet/nginx_config_reloader',
    license='',
    author='Willem de Groot',
    author_email='willem@byte.nl',
    description='nginx config file monitor and reloader',
    entry_points={
        'console_scripts': [
            'nginx_config_reloader = nginx_config_reloader:main'
        ]
    },
    install_requires=['pyinotify>=0.9.2'],
    test_suite="tests",
)
