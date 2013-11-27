from __future__ import with_statement
import os
import sys
import pkgutil
import md5
import json
from random import choice
from tornado.options import define, options
from tornado.util import exec_in

def set_default_option(name, default=None, **kwargs):
    if name in options:
        return
    define(name, default, **kwargs)


def reset_option(name, default=None, **kwargs):
    if name in options:
        options._options[name].set(default)
        return
    define(name, default, **kwargs)


def parse_config_file(path):
    config = {}
    with open(path) as f:
        exec_in(f.read(), config, config)
    for name in config:
        if name in options._options:
            options._options[name].set(config[name])
        else:
            define(name, config[name])

def create_token(length=16):
    chars = ('0123456789'
             'abcdefghijklmnopqrstuvwxyz'
             'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    salt = ''.join([choice(chars) for i in range(length)])
    return salt

class ObjectDict(dict):
    def __getattr__(self, key):
        if key in self:
            return self[key]
        return None

    def __setattr__(self, key, value):
        self[key] = value


def import_object(name, arg=None):
    """tornado.util.import_object replacement for july project

    .. attention:: you should not use this function
    """

    if '.' not in name:
        return __import__(name)
    parts = name.split('.')
    #try:
    obj = __import__('.'.join(parts[:-1]), None, None, [parts[-1]], 0)
    #except ImportError:
    #    obj = None
    return getattr(obj, parts[-1], arg)


def get_root_path(import_name):
    """Returns the path to a package or cwd if that cannot be found.  This
    returns the path of a package or the folder that contains a module.

    Not to be confused with the package path returned by :func:`find_package`.
    """
    loader = pkgutil.get_loader(import_name)
    if loader is None or import_name == '__main__':
        # import name is not found, or interactive/main module
        return os.getcwd()
    # For .egg, zipimporter does not have get_filename until Python 2.7.
    if hasattr(loader, 'get_filename'):
        filepath = loader.get_filename(import_name)
    else:
        # Fall back to imports.
        __import__(import_name)
        filepath = sys.modules[import_name].__file__
    # filepath is import_name.py for a module, or __init__.py for a package.
    return os.path.dirname(os.path.abspath(filepath))


def to_md5(url):
    m = md5.new()
    m.update(url)
    url_md5 = m.hexdigest()
    return url_md5 


def json_loads(res):
    if res:
        return json.loads(res)
    else:
        return dict()

def json_dumps(res):
    return json.dumps(res)
