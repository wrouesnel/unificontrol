"""Functions and classess used to provide abstract representations of the API calls"""

# This metaclass renames any method of a class that currently have a
# __name__ attribute of META_RENAME to instead have a function
# introspection name to match the attribute name

from inspect import Signature, Parameter

from .exceptions import UnifiAPIError

POSITIONAL_ONLY = Parameter.POSITIONAL_ONLY
POSITIONAL_OR_KEYWORD = Parameter.POSITIONAL_OR_KEYWORD
KEYWORD_ONLY = Parameter.KEYWORD_ONLY

META_RENAME = "__TO_BE_RENAMED_LATER__"

class MetaNameFixer(type):
    "A metaclass to fix attribute introspection names"
    def __init__(cls, name, bases, dct):
        for attr_name in dct:
            attr = dct[attr_name]
            if getattr(attr, "__name__", None) == META_RENAME:
                attr.__name__ = attr_name
        super(MetaNameFixer, cls).__init__(name, bases, dct)

class UnspecifiedResponseKey:
    """Special class used to indicate no user preference for the response key"""

class NoResponseBody:
    """Special class used to indicate there is no response body expected.

    API v2 DELETE sets this automatically.
    """

# These are classes who's instances represent API calls to the Unifi controller
class _UnifiAPICall:
    # pylint: disable=too-many-instance-attributes, too-many-arguments
    # pylint: disable=too-few-public-methods, protected-access
    "A representation of a single API call in a specific site"
    def __init__(self, doc, endpoint,
                 path_arg_name=None, path_arg_optional=True,
                 path_arg_in_request_body=False,
                 json_args=None, json_body_name=None, json_fix=None,
                 rest_command=None, method=None,
                 need_login=True,
                 response_key=UnspecifiedResponseKey,
                 api_version=1):
        self._endpoint = endpoint
        self._path_arg_name = path_arg_name
        self._path_arg_in_request_body = path_arg_in_request_body
        self._json_args = json_args
        self._json_body_name = json_body_name
        self._rest = rest_command
        self._need_login = need_login
        self._response_key = response_key
        self._api_version = api_version
        if not isinstance(json_fix, (list, tuple, type(None))):
            json_fix = [json_fix]
        self._fixes = json_fix
        self.__doc__ = doc

        args = [Parameter('self', POSITIONAL_ONLY)]
        if path_arg_name:
            args.append(Parameter(path_arg_name, POSITIONAL_OR_KEYWORD,
                                  default=None if path_arg_optional else Parameter.empty))

        if json_args:
            json_args.sort(key=lambda x:isinstance(x,tuple))
            for arg_name in json_args:
                if isinstance(arg_name, tuple):
                    arg_name, default = arg_name
                else:
                    default = Parameter.empty
                args.append(Parameter(arg_name, POSITIONAL_OR_KEYWORD, default=default))
        if json_body_name:
            args.append(Parameter(json_body_name,
                                  POSITIONAL_OR_KEYWORD if path_arg_optional else POSITIONAL_OR_KEYWORD,
                                  default=None))

        self.call_sig = Signature(args)
        if method is None:
            if json_args or json_body_name or rest_command:
                method = "POST"
            else:
                method = "GET"

        self._method = method

    def _build_url(self, client, path_arg):
        if not client.site:
            raise UnifiAPIError("No site specified for site-specific call")

        path_prefix = ""
        if client.path_prefix is not None:
            path_prefix = "{path_prefix}/".format(path_prefix=client.path_prefix)

        # v1 APIs have nothing, v2 has a path prefix
        api_specification = "api"
        site_specification = "s/{site}".format(site=client.site)
        if self._api_version > 1:
            api_specification="v{api_version}/api".format(api_version=self._api_version)
            # v2 APIs use a different site specification
            site_specification = "site/{site}".format(site=client.site)
            # If not specified, the data key isn't included for a v2 API

        return "https://{host}:{port}/{path_prefix}{api_specification}/{site_specification}/{endpoint}{path}".format(
            host=client.host, port=client.port, site_specification=site_specification,
            path_prefix=path_prefix,
            api_specification=api_specification,
            endpoint=self._endpoint,
            path="/" + path_arg if path_arg else "")

    def __call__(self, *args, **kwargs):
        bound = self.call_sig.bind(*args, **kwargs)
        bound.apply_defaults()
        # The first parameter is the 'self' of the API class to which it is attached
        client = bound.arguments["self"]
        path_arg = bound.arguments[self._path_arg_name] if self._path_arg_name else None
        rest_dict = bound.arguments[self._json_body_name] if self._json_body_name else {}
        if self._path_arg_in_request_body:
            if self._path_arg_name:
                rest_dict[self._path_arg_name] = bound.arguments[self._path_arg_name]
        if self._rest:
            rest_dict["cmd"] = self._rest
        if self._json_args:
            for arg_name in self._json_args:
                if isinstance(arg_name, tuple):
                    arg_name, _ = arg_name
                if arg_name not in bound.arguments:
                    raise TypeError("Argument {} is required".format(arg_name))
                if bound.arguments[arg_name] is not None:
                    rest_dict[arg_name] = bound.arguments[arg_name]
        if self._fixes:
            for fix in self._fixes:
                rest_dict = fix(rest_dict)
        url = self._build_url(client, path_arg)

        response_key = "data"
        if self._response_key is not UnspecifiedResponseKey:
            response_key = self._response_key
        elif self._api_version > 1:
            # Version 2 APIs default to not using the data key
            response_key = None

        no_response = False
        if self._api_version > 1 and self._method.lower() == "delete" and self._response_key is UnspecifiedResponseKey:
            no_response = True

        return client._execute(url, self._method, rest_dict, need_login=self._need_login,
                               response_key=response_key, no_response=no_response)

class _UnifiAPICallNoSite(_UnifiAPICall):
    # pylint: disable=too-few-public-methods
    "A representation of a single API call common to all sites"
    def _build_url(self, client, path_arg):
        endpoint= self._endpoint if self._endpoint.startswith('/') else '/api/' + self._endpoint
        return "https://{host}:{port}{endpoint}{path}".format(
            host=client.host, port=client.port,
            endpoint=endpoint,
            path="/" + path_arg if path_arg else "")

# We want to have proper introspection and documentation for our
# methods but for some reason we you can't set a __signature__
# directly on a bound method. Instead we wrap it up and fix the
# signature on the wrapper.

def _make_wrapper(cls, *args, **kwargs):
    """Wrap a call to an instance of an obbject"""
    instance = cls(*args, **kwargs)
    def wrapper(client, *a, **kw):
        # pylint: disable=missing-docstring
        return instance(client, *a, **kw)
    wrapper.__name__ = META_RENAME
    wrapper.__doc__ = instance.__doc__
    wrapper.__signature__ = instance.call_sig
    return wrapper

def UnifiAPICall(*args, **kwargs):
    # pylint: disable=invalid-name
    """Make a site-specific API call method"""
    return _make_wrapper(_UnifiAPICall, *args, **kwargs)

def UnifiAPICallNoSite(*args, **kwargs):
    # pylint: disable=invalid-name
    """Make a controller-wide API call method"""
    return _make_wrapper(_UnifiAPICallNoSite, *args, **kwargs)
