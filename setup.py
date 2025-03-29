from setuptools import setup, find_packages

setup(
    name='alarmdecoder-webapp',
    version='0.9.0',
    description='Modern Flask web interface for AlarmDecoder devices',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Nu Tech Software Solutions, Inc.',
    author_email='ad2usb@support.nutech.com',
    url='https://github.com/nutechsoftware/alarmdecoder-webapp',
    license='MIT',
    python_requires='>=3.11',
    packages=find_packages(include=["ad2web*"]),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        'flask',
        'flask-sqlalchemy',
        'flask-login',
        'flask-babelplus',
        'flask-wtf',
        'flask-mail',
        'flask-openid',
        'flask-testing',
        'pyserial>=3.5',
        'alarmdecoder',  # assumes installed in editable mode or from PyPI
        'netifaces',
        'psutil>=5.0.0',
        'jsonpickle',
        'sh',
        'alembic',
        'gevent-socketio',
        'sleekxmpp',
        'pyopenssl',
    ],
    extras_require={
        'dev': ['pytest', 'coverage', 'mypy', 'flake8']
    },
    classifiers=[
        'Development Status :: 4 - Beta',
        'Framework :: Flask',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3.11',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
        'Topic :: Home Automation',
        'Topic :: Security',
    ]
)
