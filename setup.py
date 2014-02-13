from setuptools import setup, find_packages

setup(
    name='nginx_config_reloader',
    version='0.1',
    packages=find_packages(exclude=['test*']),
    url='',
    license='',
    author='maarten',
    author_email='maarten@byte.nl',
    description='nginx config file monitor and reloader',
    entry_points={
        'console_scripts': [
            'nginx_config_reloader = nginx_config_reloader:main'
        ]
    },
    install_requires=['pyinotify>0.9.2'],
)
