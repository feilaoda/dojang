import os.path
import re
import logging
from tornado.web import Application, URLSpec
from dojang.template import DojangLoader
from tornado.wsgi import WSGIApplication

from .util import get_root_path, import_object, ObjectDict


__all__ = ["DojangApp", "DojangApplication"]


class DojangApp(object):
    
    _first_register = True

    def __init__(self, name, import_name, version=None, template_folder=None,
                 handlers=None, ui_modules=None, **settings):
        self.name = name
        self.import_name = import_name
        self.handlers = handlers
        self.ui_modules = ui_modules
        self.settings = settings
        self.root_path = get_root_path(self.import_name)
        self.version = version

        if template_folder:
            self.template_path = os.path.join(self.root_path, template_folder)
        else:
            self.template_path = None

    def add_handler(self, handler):
        if self.handlers is None:
            self.handlers = [handler]
        else:
            self.handlers.append(handler)

    def first_register(self):
        if not self._first_register:
            return False
        print('Register: %s' % self.name)
        self._first_register = False
        return True


class DojangApplication(object):

    def __init__(self, handlers=None, default_host="", transforms=None,
                 wsgi=False, **settings):
        if not handlers:
            self.handlers = []
        else:
            self.handlers = handlers
        self.app_handlers = {}

        self.sub_handlers = []
        self.named_handlers = {}
        self.default_host = default_host
        self.transforms = transforms
        self.wsgi = wsgi

        if 'template_path' in settings:
            template_path = settings.pop('template_path')
            if isinstance(template_path, str):
                settings['template_path'] = [template_path]
        else:
            settings['template_path'] = []

        self.settings = settings

    def add_handler(self, handler):
        if not self.handlers:
            self.handlers = []

        self.handlers.append(handler)

    def add_ui_moudle(self, ui_module):
        if 'ui_modules' not in self.settings:
            self.settings['ui_modules'] = {}

        if ui_module:
            self.settings['ui_modules'].update(ui_module)

    def register_filter(self, name, func):
        if '__dojang_filters__' not in self.settings:
            self.settings['__dojang_filters__'] = {}

        self.settings['__dojang_filters__'].update({name: func})

    def register_context(self, key, value):
        """Register global variables for template::

            application = DojangApplication()
            application.register_global('key', value)

        And it will be available in template::

            {{ g.key }}

        """
        if '__dojang_global__' not in self.settings:
            self.settings['__dojang_global__'] = ObjectDict()

        self.settings['__dojang_global__'][key] = value

    def register_api(self, app, host_pattern=None):
        if host_pattern:
            if not host_pattern.endswith("$"):
                host_pattern = host_pattern + "$"
        if host_pattern is None:
            query_prefix = "api"
        else:
            query_prefix = None
        self._register_app_handlers(app, host_pattern, query_prefix)

    def register_app(self, app):
        self._register_app_handlers(app)
        
    def _register_app_handlers(self, app, host_pattern=None, query_prefix=None):
        if isinstance(app, str):
            app = import_object(app)
        if app.first_register():
            url_prefix = ""
            if app.version:
                if query_prefix:
                    url_prefix += "/%s" % (query_prefix)
                url_prefix += "/%s" % app.version
            if app.name != "":
                url_prefix += "/%s" % app.name
            self._add_handlers(host_pattern, app.handlers, url_prefix)
            self._add_ui_modules(app)
            if app.template_path:
                self.settings['template_path'].append(app.template_path)

    def _add_handlers(self, host_pattern, host_handlers, url_prefix=''):
        
        handlers = []
        for spec in host_handlers:
            if isinstance(spec, type(())):
                assert len(spec) in (2, 3)
                pattern = spec[0]
                handler = spec[1]

                if isinstance(handler, str):
                    handler = import_object(handler)

                if len(spec) == 3:
                    kwargs = spec[2]
                else:
                    kwargs = {}
                pattern = '%s%s' % (url_prefix, pattern)
                spec = URLSpec(pattern, handler, kwargs)
            elif isinstance(spec, URLSpec):
                pattern = '%s%s' % (url_prefix, spec.regex.pattern)
                spec = URLSpec(pattern, spec.handler_class,
                               spec.kwargs, spec.name)

            handlers.append(spec)
        
        if host_pattern:
            self.sub_handlers.append((host_pattern, handlers))
        else:
            for handler in handlers:
                self.add_handler(handler)


    def _add_ui_modules(self, app):
        self.add_ui_moudle(app.ui_modules)

    def __call__(self):
        kwargs = {}
        if 'autoescape' in self.settings:
            kwargs['autoescape'] = self.settings['autoescape']
        path = self.settings.pop('template_path')
        loader = DojangLoader(path, **kwargs)
        self.settings['template_loader'] = loader
        if self.wsgi:
            app = WSGIApplication(self.handlers, self.default_host,
                                  **self.settings)
            return app
        
        app = Application(
            handlers=self.handlers, default_host=self.default_host, transforms=self.transforms,
            wsgi=self.wsgi, **self.settings
        )
        for handler in self.sub_handlers:
            app.add_handlers(handler[0], handler[1])

        return app
