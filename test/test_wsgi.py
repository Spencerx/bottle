# -*- coding: utf-8 -*-
from __future__ import with_statement
import bottle
from .tools import ServerTestBase, chdir
from bottle import tob, touni, HTTPResponse

class TestWsgi(ServerTestBase):
    ''' Tests for WSGI functionality, routing and output casting (decorators) '''

    def test_get(self):
        """ WSGI: GET routes"""
        @bottle.route('/')
        def test(): return 'test'
        self.assertStatus(404, '/not/found')
        self.assertStatus(405, '/', post="var=value")
        self.assertBody('test', '/')

    def test_post(self):
        """ WSGI: POST routes"""
        @bottle.route('/', method='POST')
        def test(): return 'test'
        self.assertStatus(404, '/not/found')
        self.assertStatus(405, '/')
        self.assertBody('test', '/', post="var=value")

    def test_headget(self):
        """ WSGI: HEAD routes and GET fallback"""
        @bottle.route('/get')
        def test(): return 'test'
        @bottle.route('/head', method='HEAD')
        def test2(): return 'test'
        # GET -> HEAD
        self.assertStatus(405, '/head')
        # HEAD -> HEAD
        self.assertStatus(200, '/head', method='HEAD')
        self.assertBody('', '/head', method='HEAD')
        # HEAD -> GET
        self.assertStatus(200, '/get', method='HEAD')
        self.assertBody('', '/get', method='HEAD')

    def test_request_attrs(self):
        """ WSGI: POST routes"""
        @bottle.route('/')
        def test():
            self.assertEqual(bottle.request.app,
                             bottle.default_app())
            self.assertEqual(bottle.request.route,
                             bottle.default_app().routes[0])
            return 'foo'
        self.assertBody('foo', '/')

    def get204(self):
        """ 204 responses must not return some entity headers """
        bad = ('content-length', 'content-type')
        for h in bad:
            bottle.response.set_header(h, 'foo')
        bottle.status = 204
        for h, v in bottle.response.headerlist:
            self.assertFalse(h.lower() in bad, "Header %s not deleted" % h)

    def get304(self):
        """ 304 responses must not return entity headers """
        bad = ('allow', 'content-encoding', 'content-language',
               'content-length', 'content-md5', 'content-range',
               'content-type', 'last-modified') # + c-location, expires?
        for h in bad:
            bottle.response.set_header(h, 'foo')
        bottle.status = 304
        for h, v in bottle.response.headerlist:
            self.assertFalse(h.lower() in bad, "Header %s not deleted" % h)

    def test_anymethod(self):
        self.assertStatus(404, '/any')
        @bottle.route('/any', method='ANY')
        def test2(): return 'test'
        self.assertStatus(200, '/any', method='HEAD')
        self.assertBody('test', '/any', method='GET')
        self.assertBody('test', '/any', method='POST')
        self.assertBody('test', '/any', method='DELETE')
        @bottle.route('/any', method='GET')
        def test2(): return 'test2'
        self.assertBody('test2', '/any', method='GET')
        @bottle.route('/any', method='POST')
        def test2(): return 'test3'
        self.assertBody('test3', '/any', method='POST')
        self.assertBody('test', '/any', method='DELETE')

    def test_500(self):
        """ WSGI: Exceptions within handler code (HTTP 500) """
        @bottle.route('/')
        def test(): return 1/0
        self.assertStatus(500, '/')

    def test_500_unicode(self):
        @bottle.route('/')
        def test(): raise Exception(touni('Unicode äöüß message.'))
        self.assertStatus(500, '/')

    def test_utf8_url(self):
        """ WSGI: UTF-8 Characters in the URL """
        @bottle.route('/my-öäü/<string>')
        def test(string): return string
        self.assertBody(tob('urf8-öäü'), '/my-öäü/urf8-öäü')

    def test_utf8_header(self):
        header = 'öäü'.encode('utf8').decode('latin1')
        @bottle.route('/test')
        def test():
            h = bottle.request.get_header('X-Test')
            self.assertEqual(h, 'öäü')
            bottle.response.set_header('X-Test', h)
        self.assertHeader('X-Test', header, '/test', env={'HTTP_X_TEST': header})

    def test_utf8_404(self):
        self.assertStatus(404, '/not-found/urf8-öäü')

    def test_401(self):
        """ WSGI: abort(401, '') (HTTP 401) """
        @bottle.route('/')
        def test(): bottle.abort(401)
        self.assertStatus(401, '/')
        @bottle.error(401)
        def err(e):
            bottle.response.status = 200
            return str(type(e))
        self.assertStatus(200, '/')
        self.assertBody("<class 'bottle.HTTPError'>",'/')

    def test_303(self):
        """ WSGI: redirect (HTTP 303) """
        @bottle.route('/')
        def test(): bottle.redirect('/yes')
        @bottle.route('/one')
        def test2(): bottle.redirect('/yes',305)
        env = {'SERVER_PROTOCOL':'HTTP/1.1'}
        self.assertStatus(303, '/', env=env)
        self.assertHeader('Location', 'http://127.0.0.1/yes', '/', env=env)
        env = {'SERVER_PROTOCOL':'HTTP/1.0'}
        self.assertStatus(302, '/', env=env)
        self.assertHeader('Location', 'http://127.0.0.1/yes', '/', env=env)
        self.assertStatus(305, '/one', env=env)
        self.assertHeader('Location', 'http://127.0.0.1/yes', '/one', env=env)

    def test_generator_callback(self):
        @bottle.route('/yield')
        def test():
            bottle.response.headers['Test-Header'] = 'test'
            yield 'foo'
        @bottle.route('/yield_nothing')
        def test2():
            yield
            bottle.response.headers['Test-Header'] = 'test'
        self.assertBody('foo', '/yield')
        self.assertHeader('Test-Header', 'test', '/yield')
        self.assertBody('', '/yield_nothing')
        self.assertHeader('Test-Header', 'test', '/yield_nothing')

    def test_cookie(self):
        """ WSGI: Cookies """
        @bottle.route('/cookie')
        def test():
            bottle.response.set_cookie('b', 'b')
            bottle.response.set_cookie('c', 'c', path='/')
            return 'hello'
        try:
            c = self.urlopen('/cookie')['header'].get_all('Set-Cookie', '')
        except:
            c = self.urlopen('/cookie')['header'].get('Set-Cookie', '').split(',')
            c = [x.strip() for x in c]
        self.assertTrue('b=b' in c)
        self.assertTrue('c=c; Path=/' in c)


class TestErrorHandling(ServerTestBase):
    def test_error_routing(self):

        @bottle.route("/<code:int>")
        def throw_error(code):
            bottle.abort(code)

        # Decorator syntax
        @bottle.error(500)
        def catch_500(err):
            return err.status_line

        # Decorator syntax (unusual/custom error codes)
        @bottle.error(999)
        def catch_999(err):
            return err.status_line

        # Callback argument syntax
        def catch_404(err):
            return err.status_line
        bottle.error(404, callback=catch_404)

        self.assertBody("404 Not Found", '/not_found')
        self.assertBody("500 Internal Server Error", '/500')
        self.assertBody("999 Unknown", '/999')


class CloseableBody:

    def __init__(self, body):
        self.body = body
        self.close_events = []

    def __iter__(self):
        return iter(self.body)

    def close(self):
        self.close_events.append(True)


class TestCloseable(ServerTestBase):
    """ Test that close-able return types are actually closed """

    def setUp(self):
        super().setUp()

    def closeable(self, body=["OK"]):
        self.closeable = CloseableBody(body)

    def assertClosed(self, body, open_args=None):
        closeable = CloseableBody(body)
        self.app.route("/close")(lambda: closeable)
        try:
            self.urlopen("/close", **(open_args or {}))
        finally:
            self.assertTrue(len(closeable.close_events) > 0, "Response object was not closed")

    def test_direct(self):
        self.assertClosed(["OK"])
        self.assertClosed([b"OK"])
        self.assertClosed("OK")
        self.assertClosed(b"OK")
        self.assertClosed(["OK" for ok in range(10)])
        self.assertClosed([b"OK" for ok in range(10)])
        self.assertClosed(["OK" for ok in range(0)])
        self.assertClosed(5) # Internal server error in Bottle._cast
        try:
            self.assertClosed(["CRASH"], open_args={'crash': 'start_response'})
        except RuntimeError:
            pass


class TestRouteDecorator(ServerTestBase):
    def test_decorators(self):
        def foo(): return bottle.request.method
        bottle.get('/')(foo)
        bottle.post('/')(foo)
        bottle.put('/')(foo)
        bottle.delete('/')(foo)
        for verb in 'GET POST PUT DELETE'.split():
            self.assertBody(verb, '/', method=verb)

    def test_single_path(self):
        @bottle.route('/a')
        def test(): return 'ok'
        self.assertBody('ok', '/a')
        self.assertStatus(404, '/b')

    def test_path_list(self):
        @bottle.route(['/a','/b'])
        def test(): return 'ok'
        self.assertBody('ok', '/a')
        self.assertBody('ok', '/b')
        self.assertStatus(404, '/c')

    def test_no_path(self):
        @bottle.route()
        def test(x=5): return str(x)
        self.assertBody('5', '/test')
        self.assertBody('6', '/test/6')

    def test_no_params_at_all(self):
        @bottle.route
        def test(x=5): return str(x)
        self.assertBody('5', '/test')
        self.assertBody('6', '/test/6')

    def test_method(self):
        @bottle.route(method='gEt')
        def test(): return 'ok'
        self.assertBody('ok', '/test', method='GET')
        self.assertStatus(200, '/test', method='HEAD')
        self.assertStatus(405, '/test', method='PUT')

    def test_method_list(self):
        @bottle.route(method=['GET','post'])
        def test(): return 'ok'
        self.assertBody('ok', '/test', method='GET')
        self.assertBody('ok', '/test', method='POST')
        self.assertStatus(405, '/test', method='PUT')

    def test_apply(self):
        def revdec(func):
            def wrapper(*a, **ka):
                return reversed(func(*a, **ka))
            return wrapper

        @bottle.route('/nodec')
        @bottle.route('/dec', apply=revdec)
        def test(): return '1', '2'
        self.assertBody('21', '/dec')
        self.assertBody('12', '/nodec')

    def test_apply_list(self):
        def revdec(func):
            def wrapper(*a, **ka):
                return reversed(func(*a, **ka))
            return wrapper
        def titledec(func):
            def wrapper(*a, **ka):
                return ''.join(func(*a, **ka)).title()
            return wrapper

        @bottle.route('/revtitle', apply=[revdec, titledec])
        @bottle.route('/titlerev', apply=[titledec, revdec])
        def test(): return 'a', 'b', 'c'
        self.assertBody('cbA', '/revtitle')
        self.assertBody('Cba', '/titlerev')

    def test_hooks(self):
        @bottle.route()
        def test():
            return bottle.request.environ.get('hooktest','nohooks')
        @bottle.hook('before_request')
        def hook():
            bottle.request.environ['hooktest'] = 'before'
        @bottle.hook('after_request')
        def hook(*args, **kwargs):
            bottle.response.headers['X-Hook'] = 'after'
        self.assertBody('before', '/test')
        self.assertHeader('X-Hook', 'after', '/test')

    def test_after_request_sees_HTTPError_response(self):
        """ Issue #671  """
        called = []

        @bottle.hook('after_request')
        def after_request():
            called.append('after')
            self.assertEqual(400, bottle.response.status_code)

        @bottle.get('/')
        def _get():
            called.append("route")
            bottle.abort(400, 'test')

        self.urlopen("/")
        self.assertEqual(["route", "after"], called)

    def test_after_request_hooks_run_after_exception(self):
        """ Issue #671  """
        called = []

        @bottle.hook('before_request')
        def before_request():
            called.append('before')

        @bottle.hook('after_request')
        def after_request():
            called.append('after')

        @bottle.get('/')
        def _get():
            called.append("route")
            1/0

        self.urlopen("/")
        self.assertEqual(["before", "route", "after"], called)

    def test_after_request_hooks_run_after_exception_in_before_hook(self):
        """ Issue #671  """
        called = []

        @bottle.hook('before_request')
        def before_request():
            called.append('before')
            1 / 0

        @bottle.hook('after_request')
        def after_request():
            called.append('after')

        @bottle.get('/')
        def _get():
            called.append("route")

        self.urlopen("/")
        self.assertEqual(["before", "after"], called)

    def test_after_request_hooks_may_rise_response_exception(self):
        """ Issue #671  """
        called = []

        @bottle.hook('after_request')
        def after_request():
            called.append('after')
            bottle.abort(400, "hook_content")

        @bottle.get('/')
        def _get():
            called.append("route")
            return "XXX"

        self.assertInBody("hook_content", "/")
        self.assertEqual(["route", "after"], called)

    def test_after_response_hook_can_set_headers(self):
        """ Issue #1125  """

        @bottle.route()
        def test1():
            return "test"
        @bottle.route()
        def test2():
            return HTTPResponse("test", 200)
        @bottle.route()
        def test3():
            raise HTTPResponse("test", 200)

        @bottle.hook('after_request')
        def hook():
            bottle.response.headers["X-Hook"] = 'works'

        for route in ("/test1", "/test2", "/test3"):
            self.assertBody('test', route)
            self.assertHeader('X-Hook', 'works', route)

    def test_template(self):
        @bottle.route(template='test {{a}} {{b}}')
        def test(): return dict(a=5, b=6)
        self.assertBody('test 5 6', '/test')

    def test_template_opts(self):
        @bottle.route(template=('test {{a}} {{b}}', {'b': 6}))
        def test(): return dict(a=5)
        self.assertBody('test 5 6', '/test')

    def test_name(self):
        @bottle.route(name='foo')
        def test(x=5): return 'ok'
        self.assertEqual('/test/6', bottle.url('foo', x=6))

    def test_callback(self):
        def test(x=5): return str(x)
        rv = bottle.route(callback=test)
        self.assertBody('5', '/test')
        self.assertBody('6', '/test/6')
        self.assertEqual(rv, test)




class TestDecorators(ServerTestBase):
    ''' Tests Decorators '''

    def test_view(self):
        """ WSGI: Test view-decorator (should override autojson) """
        with chdir(__file__):
            @bottle.route('/tpl')
            @bottle.view('stpl_t2main')
            def test():
                return dict(content='1234')
            result = '+base+\n+main+\n!1234!\n+include+\n-main-\n+include+\n-base-\n'
            self.assertHeader('Content-Type', 'text/html; charset=UTF-8', '/tpl')
            self.assertBody(result, '/tpl')

    def test_view_error(self):
        """ WSGI: Test if view-decorator reacts on non-dict return values correctly."""
        @bottle.route('/tpl')
        @bottle.view('stpl_t2main')
        def test():
            return bottle.HTTPError(401, 'The cake is a lie!')
        self.assertInBody('The cake is a lie!', '/tpl')
        self.assertInBody('401 Unauthorized', '/tpl')
        self.assertStatus(401, '/tpl')

    def test_truncate_body(self):
        """ WSGI: Some HTTP status codes must not be used with a response-body """
        @bottle.route('/test/<code>')
        def test(code):
            bottle.response.status = int(code)
            return 'Some body content'
        self.assertBody('Some body content', '/test/200')
        self.assertBody('', '/test/100')
        self.assertBody('', '/test/101')
        self.assertBody('', '/test/204')
        self.assertBody('', '/test/304')

    def test_routebuild(self):
        """ WSGI: Test route builder """
        def foo(): pass
        bottle.route('/a/<b>/c', name='named')(foo)
        bottle.request.environ['SCRIPT_NAME'] = ''
        self.assertEqual('/a/xxx/c', bottle.url('named', b='xxx'))
        self.assertEqual('/a/xxx/c', bottle.app().get_url('named', b='xxx'))
        bottle.request.environ['SCRIPT_NAME'] = '/app'
        self.assertEqual('/app/a/xxx/c', bottle.url('named', b='xxx'))
        bottle.request.environ['SCRIPT_NAME'] = '/app/'
        self.assertEqual('/app/a/xxx/c', bottle.url('named', b='xxx'))
        bottle.request.environ['SCRIPT_NAME'] = 'app/'
        self.assertEqual('/app/a/xxx/c', bottle.url('named', b='xxx'))

    def test_autoroute(self):
        app = bottle.Bottle()
        def a(): pass
        def b(x): pass
        def c(x, y): pass
        def d(x, y=5): pass
        def e(x=5, y=6): pass
        self.assertEqual(['/a'],list(bottle.yieldroutes(a)))
        self.assertEqual(['/b/<x>'],list(bottle.yieldroutes(b)))
        self.assertEqual(['/c/<x>/<y>'],list(bottle.yieldroutes(c)))
        self.assertEqual(['/d/<x>','/d/<x>/<y>'],list(bottle.yieldroutes(d)))
        self.assertEqual(['/e','/e/<x>','/e/<x>/<y>'],list(bottle.yieldroutes(e)))



class TestAppShortcuts(ServerTestBase):
    def setUp(self):
        ServerTestBase.setUp(self)

    def testWithStatement(self):
        default = bottle.default_app()
        inner_app = bottle.Bottle()
        self.assertEqual(default, bottle.default_app())
        with inner_app:
            self.assertEqual(inner_app, bottle.default_app())
        self.assertEqual(default, bottle.default_app())

    def assertWraps(self, test, other):
        self.assertEqual(test.__doc__, other.__doc__)

    def test_module_shortcuts(self):
        for name in '''route get post put delete error mount
                       hook install uninstall'''.split():
            short = getattr(bottle, name)
            original = getattr(bottle.app(), name)
            self.assertWraps(short, original)

    def test_module_shortcuts_with_different_name(self):
        self.assertWraps(bottle.url, bottle.app().get_url)
