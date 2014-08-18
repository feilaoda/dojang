import re

import oauth 
from sqlalchemy.exc import SQLAlchemyError
from tornado import locale
from tornado import web, escape
from tornado.options import options

from .useragent import search_ua_strings
from .util import set_default_option


#: initialize options
__all__ = ["DojangHandler", "ApiHandler", "init_options", "run_server"]

def ignore_user_agent(user_agent):
        print user_agent
        if user_agent:
            for ua in options.mobile_ua_ignores:
                if ua and ua.lower() in user_agent.lower():
                    return True
        return False
    



class DojangHandler(web.RequestHandler):
    messages = []

    def messages(self):
        return self.flash_message()

    def redirect(self, url, domain=None):
        if domain:
            url = "%s://%s%s" % ("http", options.default_domain, url)
        super(DojangHandler, self).redirect(url)

    def flash_errors(self, form):
        for key in form.form_errors.keys():
            value = form.form_errors.get(key)
            msg = self.locale.translate(key) + ": " + self.locale.translate(value.msg) #+self.locale.translate(value)
            self.flash_message(msg, 'error')

    def flash_message(self, msg=None, category=None):
        from .cache import simple_cache
        """flash_message provide an easy way to communicate with users.

        create message in your handler::

            class HomeHandler(JulyHandler):
                def get(self):
                    self.flash_message('thanks')
                    self.render('home.html')

        and get messages in ``home.html``::

            <ul>
                {% for category, message in flash_message() $}
                <li>{{category}}: {{message}}</li>
                {% end %}
            </ul>
        """
        def get_category_message(messages, category):
            for cat, msg in messages:
                if cat == category:
                    yield (cat, msg)

        #: use xsrf token or not ?
        key = '%s_flash_message' % self.xsrf_token
        if msg is None:
            messages = simple_cache.get(key)
            if messages is None:
                return []
            if category is not None:
                return get_category_message(messages, category)

            #: clear flash message
            simple_cache.delete(key)
            return messages
        message = (category, msg)
        messages = simple_cache.get(key)
        if isinstance(messages, list):
            messages.append(message)
        else:
            messages = [message]
        simple_cache.set(key, messages, 600)
        return message


    def get_user_locale(self):
        return locale.get('zh_CN')


    def is_mobile(self):
        if 'User-Agent' in self.request.headers:
            user_agent = self.request.headers['User-Agent']
            user_agent = user_agent.lower()
            for ua in search_ua_strings:
                if ua in user_agent:
                    # check if we are ignoring this user agent: (IPad)
                    if not ignore_user_agent(user_agent):
                        return True

        return False

        #     if (re.search('iPod|iPhone|Android|Opera Mini|BlackBerry|webOS|UCWEB|Blazer|PSP', user_agent)):
        #         return True
        #     else:
        #         return False
        # else:
        #     return False

    def reverse_redirect(self, name, *args):
        self.redirect(self.reverse_url(name, *args))

    def render_string(self, template_name, **kwargs):
        #: add application filters
        if '__dojang_filters__' in self.settings:
            kwargs.update(self.settings['__dojang_filters__'])

        #: add application global variables
        if '__dojang_global__' in self.settings:
            assert "site" not in kwargs, "g is a reserved keyword."
            kwargs["g"] = self.settings['__dojang_global__']
            kwargs["site"] = self.settings['__dojang_global__']
            
        kwargs['is_mobile'] = self.is_mobile()
        #: flash message support
        kwargs['messages'] = self.messages
        kwargs['settings'] = options
        return super(DojangHandler, self).render_string(template_name, **kwargs)

    def render_json(self, chunk):
        # if isinstance(chunk, list):
        #     chunk = {'array': chunk}
            
        if isinstance(chunk, (dict, list)):
            chunk = escape.json_encode(chunk)
            self.set_header("Content-Type", "application/json; charset=UTF-8")
            # callback = self.get_argument('callback', None)
            # if callback:
            #     chunk = "%s(%s)" % (callback, escape.to_unicode(chunk))
            #     self.set_header("Content-Type",
            #                     "application/javascript; charset=UTF-8")
        # print chunk, type(chunk)
        super(DojangHandler, self).write(chunk)
        
    def render_error(self, err):
        self.send_error(err)

        
    def _handle_request_exception(self, e):
        if isinstance(e, SQLAlchemyError):
            from database import db
            try:
                db.session.rollback()
            except Exception, e:
                raise
            else:
                pass
            finally:
                pass
        super(DojangHandler, self)._handle_request_exception(e)

class ApiHandler(web.RequestHandler):
    xsrf_protect = False

    def check_xsrf_cookie(self):
        if not self.xsrf_protect:
            return
        return super(ApiHandler, self).check_xsrf_cookie()

    def is_ajax(self):
        return "XMLHttpRequest" == self.request.headers.get("X-Requested-With")

    
    def write(self, chunk):
        self.set_header("Content-Type", "application/json; charset=UTF-8")
        if isinstance(chunk, (dict, list)):
            chunk = escape.json_encode(chunk)
            callback = self.get_argument('callback', None)
            if callback:
                chunk = "%s(%s)" % (callback, escape.to_unicode(chunk))
                self.set_header("Content-Type",
                                "application/javascript; charset=UTF-8")
        super(ApiHandler, self).write(chunk)


class OAuthRequestHandler(web.RequestHandler):
    """Base class for all SimpleGeo request handlers."""

    def _handle_request_exception(self, e):
        status_code = getattr(e, 'status_code', 500)
        self.set_status(status_code)

        error = {
            'code' : status_code,
            'message' : str(e)
        }

        _logger.exception(e)
        self.finish(json.dumps(error, indent=4))

    def prepare(self):
        realm = options.site_realm
        header, value = oauth.build_authenticate_header(realm).items()[0]
        self.set_header(header, value)

        try:
            uri = '%s://%s%s' % (self.request.protocol, self.request.host,
                self.request.path)

            # Builder our request object.
            self.oauth_request = oauth.Request.from_request(
                self.request.method, uri, self.request.headers, None,
                self.request.query)
        except Exception, e:
            _logger.info("Could not parse request from method = %s,"
                "uri = %s, headers = %s, query = %s, exception = %s" % (
                self.request.method, uri, self.request.headers,
                self.request.query, e))
            raise NotAuthorized()

        # Fetch the token from Cassandra and build our Consumer object.
        if self.oauth_request is None or 'oauth_consumer_key' not in self.oauth_request:
            _logger.debug("Request is missing oauth_consumer_key.")

            raise NotAuthorized()

        try:
            token = oauth.Token(token=self.oauth_request['oauth_consumer_key'])
        except Exception, e:
            _logger.info("Token not found %s (%s, %s)." % (
                self.oauth_request['oauth_consumer_key'], e, self.oauth_request))
            raise NotAuthorized()

        try:
            consumer = oauth.Consumer(key=token.key, secret=token.secret)
        except Exception, e:
            _logger.info("Could not instantiate oauth.Consumer (%s)." % e)
            raise NotAuthorized()

        try:
            # Verify the two-legged request.
            oauth_server = oauth.Server()
            oauth_server.add_signature_method(oauth.SignatureMethod_HMAC_SHA1())
            oauth_server.add_signature_method(oauth.SignatureMethod_PLAINTEXT())
            oauth_server.verify_request(self.oauth_request, consumer, None)
        except Exception, e:
            _logger.info("Could not verify signature (%s)." % e)
            raise NotAuthorized()



def init_options():

    import os.path
    from tornado.options import options, parse_command_line
    from .util import parse_config_file
    parse_command_line()

    if options.settings:
        path = os.path.abspath(options.settings)
        print("Load settings from %s" % path)
        parse_config_file(path)

    return


def run_server(app):
    import logging
    import tornado.locale
    from tornado import httpserver, ioloop
    from tornado.options import options

    server = httpserver.HTTPServer(app(), xheaders=True)
    server.listen(int(options.port), options.address)

    if options.locale_path:
        tornado.locale.load_translations(options.locale_path)
        tornado.locale.set_default_locale(options.default_locale)

    logging.info('Start server at %s:%s' % (options.address, options.port))
    ioloop.IOLoop.instance().start()


set_default_option('address', default='127.0.0.1', type=str,
       help='run server at this address')
set_default_option('port', default=8000, type=int,
                   help='run server on this port')
set_default_option('settings', default='', type=str,
                   help='setting file path')

#: application settings
set_default_option('locale_path', type=str,
                   help='absolute path of locale directory')
set_default_option('default_locale', default='en_US', type=str)
