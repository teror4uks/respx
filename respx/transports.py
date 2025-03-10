from types import TracebackType
from typing import (
    TYPE_CHECKING,
    Any,
    Awaitable,
    Callable,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)
from warnings import warn

import httpx
from httpx import AsyncBaseTransport, BaseTransport

from .models import PassThrough
from .types import URL, Headers

if TYPE_CHECKING:
    from .router import Router  # pragma: nocover

RequestHandler = Callable[[httpx.Request], httpx.Response]
AsyncRequestHandler = Callable[[httpx.Request], Awaitable[httpx.Response]]


class MockTransport(httpx.MockTransport):
    _router: Optional["Router"]

    def __init__(
        self,
        *,
        handler: Optional[RequestHandler] = None,
        async_handler: Optional[AsyncRequestHandler] = None,
        router: Optional["Router"] = None,
    ):
        if router:
            super().__init__(router.handler)
            self._router = router
        elif handler:
            super().__init__(handler)
            self._router = None
        elif async_handler:
            super().__init__(async_handler)
            self._router = None
        else:
            raise RuntimeError(
                "Missing a MockTransport required handler or router argument"
            )
        warn(
            "MockTransport is deprecated. "
            "Please use `httpx.MockTransport(respx_router.handler)`.",
            category=DeprecationWarning,
        )

    def __exit__(
        self,
        exc_type: Type[BaseException] = None,
        exc_value: BaseException = None,
        traceback: TracebackType = None,
    ) -> None:
        if not exc_type and self._router and self._router._assert_all_called:
            self._router.assert_all_called()

    async def __aexit__(self, *args: Any) -> None:
        self.__exit__(*args)


class TryTransport(BaseTransport, AsyncBaseTransport):
    def __init__(
        self, transports: List[Union[BaseTransport, AsyncBaseTransport]]
    ) -> None:
        self.transports = transports

    def handle_request(
        self,
        method: bytes,
        url: URL,
        headers: Headers,
        stream: httpx.SyncByteStream,
        extensions: dict,
    ) -> Tuple[int, Headers, httpx.SyncByteStream, dict]:
        for transport in self.transports:
            try:
                transport = cast(BaseTransport, transport)
                return transport.handle_request(
                    method, url, headers, stream, extensions
                )
            except PassThrough as pass_through:
                stream = pass_through.request.stream  # type: ignore

        raise RuntimeError()  # pragma: nocover

    async def handle_async_request(
        self,
        method: bytes,
        url: URL,
        headers: Headers,
        stream: httpx.AsyncByteStream,
        extensions: dict,
    ) -> Tuple[int, Headers, httpx.AsyncByteStream, dict]:
        for transport in self.transports:
            try:
                transport = cast(AsyncBaseTransport, transport)
                return await transport.handle_async_request(
                    method, url, headers, stream, extensions
                )
            except PassThrough as pass_through:
                stream = pass_through.request.stream  # type: ignore

        raise RuntimeError()  # pragma: nocover
