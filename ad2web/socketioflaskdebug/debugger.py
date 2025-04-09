# -*- coding: utf-8 -*-

from werkzeug.debug import DebuggedApplication
from types import GeneratorType
import sys


class SocketIODebugger(DebuggedApplication):

    def __init__(self, app, **kwargs):
        """
        The arguments are the same as for DebuggedApplication in werkzeug.debug, with
        the only addition being the `namespace` keyword argument -- if specified, all
        handlers of the namespace will be wrapped in try/except clauses and exceptions
        will be propagated to the app and also emitted to the client via sockets.
        """
        namespace = kwargs.pop('namespace', None)
        self.exc_info = None
        super(SocketIODebugger, self).__init__(app, **kwargs) # super() also works in Py3
        if namespace is not None:
            self.protect_namespace(namespace)
            if hasattr(self.app, 'before_request'):
                # Assuming before_request works like a decorator registration function
                self.app.before_request(self.route_debugger)
            else:
                # --- Fix 1: Python 3 print ---
                print('app.before_request() not found, please route it yourself.')

    def protect_namespace(self, namespace):
        """
        Use `exception_handler_decorator` property of socketio.namespace.BaseNamespace
        to inject exception catching into the handlers. Try to preserve the original
        traceback if possible for reraising it later.
        NOTE: This mechanism might be outdated for modern Flask-SocketIO versions.
        """
        def protect_method(ns_instance, f):
            def protected_method(*args, **kwargs):
                try:
                    return f(*args, **kwargs)
                # --- Fix 3a: Bare except ---
                except Exception:
                    try:
                        self.exc_info = sys.exc_info()
                        # Assume ns_instance has an 'emit' method
                        ns_instance.emit('exception')
                    # --- Fix 3b: Bare except ---
                    except Exception:
                        # Log error during emit?
                        pass # Ignore errors during exception reporting for now
            return protected_method
        # This relies on the older gevent-socketio/early Flask-SocketIO pattern
        namespace.exception_handler_decorator = protect_method

    def __call__(self, environ, start_response):
        """
        This function extracts the results from the generator returned by the __call__
        method of werkzeug.debug.DebuggedApplication in case of socket requests.
        NOTE: This generator handling might be outdated for modern Flask-SocketIO.
        """
        result = super().__call__(environ, start_response) # Use modern super() call
        # Check if it's a socketio request (this key might differ in modern libraries)
        if 'socketio' in environ and isinstance(result, GeneratorType):
            try:
                # Consume the generator if needed by the underlying socketio mechanism
                for _ in result:
                    pass
            finally:
                 # Ensure generator is closed if it has a close method
                 if hasattr(result, 'close'):
                      result.close()
        return result # Return the original result (or consumed generator)

    def route_debugger(self):
        """
        Before each request, see if any exceptions occured in the namespace; if so,
        throw an exception so it gets caught by Werkzeug. We try to preserve the
        original traceback so the debugger messages are more informative.
        """
        if self.exc_info is not None:
            exc_type, exc_value, exc_traceback = self.exc_info
            self.exc_info = None
            # --- Fix 2: Python 3 raise with traceback ---
            # The original exception object (exc_value) likely already has the
            # traceback associated. The cleanest re-raise in Py3 is often just 'raise'.
            # However, using with_traceback is explicit if you have the tuple.
            if hasattr(exc_value, 'with_traceback'):
                 raise exc_value.with_traceback(exc_traceback)
            else: # Fallback if it's not an Exception instance? (unlikely)
                 raise exc_value # Or raise exc_type(exc_value).with_traceback(exc_traceback)
