import urllib
import tornado.ioloop
import tornado.web
import tornado.auth
import tornado.httpclient
import tornado.escape
import tornado.httputil
import logging
 
 
class GithubMixin(tornado.auth.OAuth2Mixin):
    """ Github OAuth Mixin, based on FacebookGraphMixin
    """
 
    _OAUTH_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
    _OAUTH_ACCESS_TOKEN_URL = 'https://github.com/login/oauth/access_token'
    _API_URL = 'https://api.github.com'
 
    def get_authenticated_user(self, redirect_uri, client_id, client_secret,
                              code, callback, extra_fields=None):
        """ Handles the login for Github, queries /user and returns a user object
        """
        logging.debug('gau ' + redirect_uri)
        http = tornado.httpclient.AsyncHTTPClient()
        args = {
          "redirect_uri": redirect_uri,
          "code": code,
          "client_id": client_id,
          "client_secret": client_secret,
        }
        
        fields = set(['id', 'name', 'first_name', 'last_name',
              'locale', 'picture', 'link'])
        if extra_fields:
            fields.update(extra_fields)

 
        http.fetch(self._oauth_request_token_url(**args),
            self.async_callback(self._on_access_token, redirect_uri, client_id,
                                client_secret, callback, fields))
 
    def _on_access_token(self, redirect_uri, client_id, client_secret,
                        callback, fields, response):
        """ callback for authentication url, if successful get the user details """
        if response.error:
            logging.warning('Github auth error: %s' % str(response))
            callback(None)
            return
 
        args = tornado.escape.parse_qs_bytes(
                tornado.escape.native_str(response.body))
 
        if 'error' in args:
            logging.error('oauth error ' + args['error'][-1])
            raise Exception(args['error'][-1])
 
        session = {
            "access_token": args["access_token"][-1],
        }
 
        self.github_request(
            path="/user",
            callback=self.async_callback(
                self._on_get_user_info, callback, session),
            access_token=session["access_token"],
            )
 
    def _on_get_user_info(self, callback, session, user):
        """ callback for github request /user to create a user """
        logging.debug('user data from github ' + str(user))
        if user is None:
            callback(None)
            return
        callback({
            "id": user["id"],
            "login": user["login"],
            # "name": user["name"],
            "email": user["email"],
            "access_token": session["access_token"],
        })
 
    def github_request(self, path, callback, access_token=None,
                method='GET', body=None, **args):
        """ Makes a github API request, hands callback the parsed data """
        args["access_token"] = access_token
        url = tornado.httputil.url_concat(self._API_URL + path, args)
        logging.debug('request to ' + url)
        http = tornado.httpclient.AsyncHTTPClient()
        if body is not None:
            body = tornado.escape.json_encode(body)
            logging.debug('body is' +  body)
        headers = {}
        headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36'
            
        http.fetch(url, callback=self.async_callback(
                self._parse_response, callback), method=method, body=body, headers=headers)
 
    def _parse_response(self, callback, response):
        """ Parse the JSON from the API """
        if response.error:
            logging.warning("HTTP error from Github: %s", response.error)
            callback(None)
            return
        try:
            json = tornado.escape.json_decode(response.body)
        except Exception:
            logging.warning("Invalid JSON from Github: %r", response.body)
            callback(None)
            return
        if isinstance(json, dict) and json.get("error_code"):
            logging.warning("Facebook error: %d: %r", json["error_code"],
                            json.get("error_msg"))
            callback(None)
            return
        callback(json)











# # Licensed under the Apache License, Version 2.0 (the "License"); you may
# # not use this file except in compliance with the License. You may obtain
# # a copy of the License at
# #
# #     http://www.apache.org/licenses/LICENSE-2.0
# #
# # Unless required by applicable law or agreed to in writing, software
# # distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# # WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# # License for the specific language governing permissions and limitations
# # under the License.

# import logging
# import urllib

# from tornado import escape
# from tornado import httpclient
# import tornado.auth
# from tornado.options import options


# class GithubMixin(tornado.auth.OAuth2Mixin):

#     _OAUTH_ACCESS_TOKEN_URL = "http://github.com/login/oauth/access_token"
#     _OAUTH_AUTHORIZE_URL = "http://github.com/login/oauth/authorize"
#     _OAUTH_NO_CALLBACKS = False

#     def get_authenticated_user(self, redirect_uri, client_id,
#                                client_secret, code, callback):
#         http = httpclient.AsyncHTTPClient()
#         args = {
#             "redirect_uri": redirect_uri,
#             "code": code,
#             "client_id": client_id,
#             "client_secret": client_secret,
#         }

#         fields = set(['login'])

#         http.fetch(self._oauth_request_token_url(**args),
#           self.async_callback(self._on_access_token, redirect_uri, client_id,
#                               client_secret, callback, fields))

#     def _on_access_token(self, redirect_uri, client_id, client_secret,
#                          callback, fields, response):
#         if response.error:
#             logging.warning('Github auth error: %s' % str(response))
#             callback(None)
#             return

#         print response.body
#         args = escape.parse_qs_bytes(escape.native_str(response.body))
#         print args
#         session = {
#             "access_token": args["access_token"][-1],
#         }

#         self.github_request(
#             path="/user",
#             callback=self.async_callback(
#                 self._on_get_user_info, callback, session, fields),
#             access_token=session["access_token"],
#             fields=",".join(fields)
#         )

#     def _on_get_user_info(self, callback, session, fields, user):
#         if user is None:
#             callback(None)
#             return

#         fieldmap = {}
#         for field in fields:
#             fieldmap[field] = user.get(field)

#         fieldmap.update({"access_token": session["access_token"]})
#         callback(fieldmap)

#     def github_request(self, path, callback, access_token=None,
#                            post_args=None, **args):
#         url = "https://api.github.com" + path
#         all_args = {}
#         if access_token:
#             all_args["access_token"] = access_token
#             all_args.update(args)
#             all_args.update(post_args or {})
#         if all_args:
#             url += "?" + urllib.urlencode(all_args)
#         callback = self.async_callback(self._on_github_request, callback)
#         http = httpclient.AsyncHTTPClient()
#         if post_args is not None:
#             http.fetch(url, method="POST", body=urllib.urlencode(post_args),
#                        callback=callback)
#         else:
#             headers = {}
#             headers['User-Agent'] = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36'
#             http.fetch(url, callback=callback, headers=headers)

#     def _on_github_request(self, callback, response):
#         if response.error:
#             logging.warning("Error response %s fetching %s", response.error,
#                             response.request.url)
#             print response.body
#             callback(None)
#             return
#         callback(escape.json_decode(response.body))
        
        
        
        
