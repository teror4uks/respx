# User Guide

RESPX is a mock router, [capturing](#mock-httpx) requests sent by `HTTPX`, [mocking](#mocking-responses) their responses.

Inspired by the flexible query API of the [Django](https://www.djangoproject.com/) ORM, requests are filtered and matched against routes and their request [patterns](api.md#patterns) and [lookups](api.md#lookups).

Request [patterns](api.md#patterns) are *bits* of the request, like `host` `method` `path` etc, 
with given [lookup](api.md#lookups) values, combined using *bitwise* [operators](api.md#operators) to form a `Route`,
i.e. `respx.route(path__regex=...)`

A captured request, [matching](#routing-requests) a `Route`, resolves to a [mocked](#mock-a-response) `httpx.Response`, or triggers a given [side effect](#mock-with-a-side-effect).
To skip mocking a specific request, a route can be marked to [pass through](#pass-through).

## Mock HTTPX

To patch `HTTPX`, and activate the router, use the `respx.mock` decorator *or* context manager.

### Using the Decorator

``` python
import httpx
import respx


@respx.mock
def test_decorator():
    my_route = respx.get("https://example.org/")
    response = httpx.get("https://example.org/")
    assert my_route.called
    assert response.status_code == 200
```


### Using the Context Manager

``` python
import httpx
import respx


def test_ctx_manager():
    with respx.mock:
        my_route = respx.get("https://example.org/")
        response = httpx.get("https://example.org/")
        assert my_route.called
        assert response.status_code == 200
```

### Router Settings

The RESPX router can be configured with built-in assertion checks and an *optional* [base URL](#base-url).

By configuring, a nested router is created, and the settings are *locally* bound to the routes added.

When decorating a test case with a configured router, the test function will receive the router instance as a `respx_mock` argument.

``` python
@respx.mock(assert_all_mocked=False)
def test_something(respx_mock):
    ...
```

> See router [configuration](api.md#configuration) reference for more details.


Settings Examples:

``` python
@respx.mock(assert_all_called=False)
def test_something(respx_mock):
    respx_mock.get("https://example.org/")
    respx_mock.get("https://some.url/")  # Not called, yet not asserted

    response = httpx.get("https://example.org/")
    assert response.status_code == 200
```
``` python
with respx.mock(assert_all_mocked=False) as respx_mock:
    response = httpx.get("https://example.org/")  # Not mocked, yet not asserted
    assert response.status_code == 200
```

#### Base URL

When adding a lot of routes, sharing the same domain/prefix, you can configure the router with a `base_url` to be used for added routes.

``` python
import httpx
import respx

from httpx import Response


@respx.mock(base_url="https://example.org/api/")
async def test_something(respx_mock):
    async with httpx.AsyncClient(base_url="https://example.org/api/") as client:
        respx_mock.get("/baz/").mock(return_value=Response(200, text="Baz"))
        response = await client.get("/baz/")
        assert response.text == "Baz"
```

---

## Routing Requests

The easiest way to add routes is to use the [HTTP Method](#http-method-helpers) helpers.

For full control over the request pattern matching, use the [route](#route-api) API.

### HTTP Method Helpers

Each HTTP method has a helper function (`get`, `options`, `head`, `post`, `put`, `patch`, `delete`), *shortcutting* the [route](#route-api) API.

``` python
my_route = respx.get("https://example.org/", params={"foo": "bar"})
response = httpx.get("https://example.org/", params={"foo": "bar"})
assert my_route.called
assert response.status_code == 200
```
> See [.get(), .post(), ...](api.md#get-post) helpers reference for more details.

### Route API

#### Patterns

With the `route` API, you define a combined pattern to match, capturing a sent request.

``` python
my_route = respx.route(method="GET", host="example.org", path="/foobar/")
response = httpx.get("https://example.org/foobar/")
assert my_route.called
assert response.status_code == 200
```
> See [.route()](api.md#route) reference for more details.

#### Lookups
Each [pattern](api.md#patterns) has a *default* lookup. To specify what [lookup](api.md#lookups) to use, add a `__<lookup>` suffix.

``` python
respx.route(method__in=["PUT", "PATCH"])
```

#### Combining Patterns

For even more flexability, you can define combined patterns using the [M()](api.md#m) *object*, together with bitwise [operators](api.md#operators) (`&`, `|,` `~`), creating a reusable pattern.

``` python
hosts_pattern = M(host="example.org") | M(host="example.com")
my_route = respx.route(hosts_pattern, method="GET", path="/foo/")

response = httpx.get("http://example.org/foo/")
assert response.status_code == 200
assert my_route.called

response = httpx.get("https://example.com/foo/")
assert response.status_code == 200
assert my_route.call_count == 2
```

!!! note "NOTE"
    ``M(url="//example.org/foobar/")`` is **equal** to ``M(host="example.org") & M(path="/foobar/")``

### Named Routes

Routes can be *named* when added, and later accessed through the `respx.routes` mapping.

This is useful when a route is added *outside* the test case, *e.g.* access or assert route calls.

``` python
import httpx
import respx

# Added somewhere else
respx.get("https://example.org/", name="home")


@respx.mock
def test_route_call():
    httpx.get("https://example.org/")
    assert respx.routes["home"].called
    assert respx.routes["home"].call_count == 1

    last_home_response = respx.routes["home"].calls.last.response
    assert last_home_response.status_code == 200
```

### Nested Routers

As described under [settings](#router-settings), a nested router is created when calling `respx.mock(...)`.

Nested routers are useful when mocking multiple remote APIs, allowing grouped routes per API, and to be mocked individually and reused across tests.

Use the nested router as decorator or context manager to patch `HTTPX` and activate the routes.

``` python
import httpx
import respx

from httpx import Response


api_mock = respx.mock(assert_all_called=False)
api_mock.route(
    url="https://api.foo.bar/baz/",
    name="baz",
).mock(
    return_value=Response(200, json={"name": "baz"}),
)
...


@api_mock
def test_decorator():
    response = httpx.get("https://api.foo.bar/baz/")
    assert response.status_code == 200
    assert response.json() == {"name": "baz"}
    assert api_mock["baz"].called


def test_ctx_manager():
    with api_mock:
        ...
```

!!! note "NOTE"
    Named routes in a *nested router* can be directly accessed via `my_mock_router[<route name>]`


---

## Mocking Responses

To mock a [route](#routing-requests) response, use `<route>.mock(...)` to either...

* set the `httpx.Response` to be [returned](#mock-a-response).
* set a [side effect](#mock-with-a-side-effect) to be triggered.


### Mock a Response

Create a mocked `HTTPX` [Response](api.md#response) object and pass it as `return_value`.

``` python
respx.get("https://example.org/").mock(return_value=Response(204))
```
> See [.mock()](api.md#mock) reference for more details.

You can also use the `<route>.return_value` *setter*.

``` python
route = respx.get("https://example.org/")
route.return_value = Response(200, json={"foo": "bar"})
```

### Mock with a Side Effect

RESPX *side effects* works just like the python `Mock` side effects.

It can either be a [function](#functions) to call,
an [exception](#exceptions) to raise, or an [iterable](#iterable) of responses/exceptions to respond with in order, for repeated requests.

``` python
respx.get("https://example.org/").mock(side_effect=...)
```

You can also use the `<route>.side_effect` *setter*.

``` python
route = respx.get("https://example.org/")
route.side_effect = ...
```

#### Functions

Function *side effects* will be called with the *captured* request argument, and should either...

* return a mocked [Response](api.md#response).
* raise an `Exception` to simulate a request error.
* return `None` to treat the route as a *non-match*, continuing testing further routes.
* return the input `Request` to [pass through](#pass-through).

``` python
import httpx
import respx


def my_side_effect(request):
    return httpx.Response(201)


@respx.mock
def test_side_effect():
    respx.post("https://example.org/").mock(side_effect=my_side_effect)

    response = httpx.post("https://example.org/")
    assert response.status_code == 201
```

If any of the route patterns are using a [regex lookup](api.md#regex), containing *named groups*, the regex groups will be passed as *kwargs* to the *side effect*.

``` python
import httpx
import respx


def my_side_effect(request, slug):
    return httpx.Response(200, json={"slug": slug})


@respx.mock
def test_side_effect_kwargs():
    route = respx.route(url__regex=r"https://example.org/(?P<slug>\w+)/")
    route.side_effect = my_side_effect

    response = httpx.get("https://example.org/foobar/")
    assert response.status_code == 200
    assert response.json() == {"slug": "foobar"}
```

A route can even *decorate* the function to be used as *side effect*.

``` python
import httpx
import rexpx


@respx.route(url__regex=r"https://example.org/(?P<user>\w+)/", name="user")
def user_api(request, user):
    return httpx.Response(200, json={"user": user})


@respx.mock
def test_user_api():
    response = httpx.get("https://example.org/lundberg/")
    assert response.status_code == 200
    assert response.json() == {"user": "lundberg"}
    assert respx.routes["user"].called
```

#### Exceptions

To simulate a request error, pass a [httpx.HTTPError](https://www.python-httpx.org/exceptions/#the-exception-hierarchy) *subclass*, or any `Exception`  as *side effect*.

``` python
import httpx
import respx


@respx.mock
def test_connection_error():
    respx.get("https://example.org/").mock(side_effect=httpx.ConnectError)

    with pytest.raises(httpx.ConnectError):
        httpx.get("https://example.org/")
```

#### Iterable

If the side effect is an *iterable*, each repeated request will get the *next* [Response](api.md#response) returned, or [exception](#exceptions) raised, from the iterable.

``` python
import httpx
import respx


@respx.mock
def test_stacked_responses():
    route = respx.get("https://example.org/")
    route.side_effect = [
        httpx.Response(404),
        httpx.Response(200),
    ]

    response1 = httpx.get("https://example.org/")
    response2 = httpx.get("https://example.org/")

    assert response1.status_code == 404
    assert response2.status_code == 200
    assert route.call_count == 2
```

### Modulo Shortcut

For simple mocking, a quick way is to use the python modulo (`%`) operator to mock the response.

The *right-hand* modulo argument can either be ...

An `int` representing the `status_code` to mock:
``` python
respx.get("https://example.org/") % 204

response = httpx.get("https://example.org/")
assert response.status_code == 204
```

A `dict` used as *kwargs* to create a mocked `HTTPX` [Response](api.md#response), with status code `200` by default:
``` python
respx.get("https://example.org/") % dict(json={"foo": "bar"})

response = httpx.get("https://example.org/")
assert response.status_code == 200
assert response.json() == {"foo": "bar"}
```

A `HTTPX` [Response](api.md#response) object:
``` python
respx.get("https://example.org/") % Response(418)

response = httpx.get("https://example.org/")
assert response.status_code == httpx.codes.IM_A_TEAPOT
```

## Rollback

When exiting a [decorated](#using-the-decorator) test case, or [context manager](#using-the-context-manager), the routes and their mocked values, *i.e.* `return_value` and `side_effect`, will be *rolled back* and restored to their initial state.

This means that you can safely modify existing routes, or add new ones, *within* a test case, without affecting other tests.

``` python
import httpx
import respx

# Initial routes
mock_router = respx.mock(base_url="https://example.org")
mock_router.get(path__regex="/user/(?P<pk>\d+)/", name="user") % 404
...


@mock_router
def test_user_exists():
    # This change will be rolled back after this test case
    mock_router["user"].return_value = httpx.Response(200)

    response = httpx.get("https://example.org/user/123/")
    assert response.status_code == 200


@mock_router
def test_user_not_found():
    response = httpx.get("https://example.org/user/123/")
    assert response.status_code == 404
```

---

## Pass Through

If you want a route to *not* capture and mock a request response, use `.pass_through()`.

``` python
import httpx
import respx


@respx.mock
def test_remote_response():
    respx.route(host="localhost").pass_through()
    response = httpx.get("http://localhost:8000/")  # respose from server
```

> See [.pass_through()](api.md#pass_through) reference for more details.

---

## Mock without patching HTTPX

The RESPX implements the [HTTP Core](https://www.encode.io/httpcore/) transport interface. 

If you don't *need* to patch `HTTPX`, pass a `MockTransport` as `transport`, when instantiating your `HTTPX` client, or alike.

``` python
import httpx
import respx
from respx.transports import MockTransport


router = respx.Router()
router.post("https://example.org/") % 404


def test_client():
    mock_transport = MockTransport(router=router)
    with httpx.Client(transport=mock_transport) as client:
        response = client.post("https://example.org/")
        assert response.status_code == 404
```

!!! Hint
    You can use `RESPX` not only to mock out `HTTPX`, but actually mock any library using `HTTP Core` transports.

---

## Call History

The `respx` API includes a `.calls` object, containing captured (`request`, `response`) named tuples and MagicMock's *bells and whistles*, i.e. `call_count`, `assert_called` etc.

### Asserting calls
``` python
assert respx.calls.called
assert respx.calls.call_count == 1

respx.calls.assert_called()
respx.calls.assert_not_called()
respx.calls.assert_called_once()
```

### Retreiving mocked calls

A matched and mocked `Call` can be retrived from call history, by either unpacking...

``` python
request, response = respx.calls.last
request, response = respx.calls[-2]  # by call order
```

...or by accessing `request` or `response` directly...

``` python
last_request = respx.calls.last.request
assert respx.calls.last.response.status_code == 200
```

### Local route calls

Each `Route` object has its own `.calls`, along with `.called` and `.call_count ` shortcuts.

``` python
import httpx
import respx


@respx.mock
def test_route_call_stats():
    route = respx.post("https://example.org/baz/") % 201
    httpx.post("https://example.org/baz/")

    assert route.calls.last.request.url.path == "/baz/"
    assert route.calls.last.response.status_code == 201

    assert route.called
    assert route.call_count == 1

    route.calls.assert_called_once()
```

### Reset History

The call history will automatically *reset* when exiting mocked context, i.e. leaving a [decorated](#using-the-decorator) test case, or [context manager](#using-the-context-manager) scope.

To manually *reset* call stats during a test case, use `respx.reset()` or `<your_router>.reset()`.

``` python
import httpx
import respx


@respx.mock
def test_reset():
    respx.post("https://foo.bar/baz/")
    httpx.post("https://foo.bar/baz/")

    assert respx.calls.call_count == 1
    respx.calls.assert_called_once()

    respx.reset()

    assert len(respx.calls) == 0
    assert respx.calls.call_count == 0
    respx.calls.assert_not_called()
```
