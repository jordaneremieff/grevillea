import asyncio
import enum
import typing
from dataclasses import dataclass


from grevillea.types import ASGIApp, Scope, Message


class ASGICycleState(enum.Enum):
    REQUEST = enum.auto()
    RESPONSE = enum.auto()
    COMPLETE = enum.auto()


@dataclass
class ASGICycle:
    scope: Scope
    loop: asyncio.AbstractEventLoop
    body: bytes = b""
    status_code: int = 200
    state: ASGICycleState = ASGICycleState.REQUEST

    def __post_init__(self) -> None:
        self.app_queue: asyncio.Queue = asyncio.Queue(loop=self.loop)

    def __call__(self, app) -> str:
        asgi_instance = self.run(app)
        asgi_task = self.loop.create_task(asgi_instance)
        self.loop.run_until_complete(asgi_task)
        return self.body.decode(), self.status_code

    def put_message(self, message: Message) -> None:
        self.app_queue.put_nowait(message)

    async def run(self, app: ASGIApp) -> None:
        try:
            await app(self.scope, self.receive, self.send)
        except BaseException as exc:
            msg = "Exception in ASGI application\n"
            self.logger.error(msg, exc_info=exc)
            if self.state is ASGICycleState.REQUEST:
                await self.send(
                    {
                        "type": "http.response.start",
                        "status": 500,
                        "headers": [(b"content-type", b"text/plain; charset=utf-8")],
                    }
                )
                await self.send(
                    {"type": "http.response.body", "body": b"Internal Server Error"}
                )
                self.state = ASGICycleState.COMPLETE

            elif self.state is not ASGICycleState.COMPLETE:
                self.body = b"Internal Server Error"
                self.status_code = 500

    async def receive(self) -> Message:
        message = await self.app_queue.get()
        return message

    async def send(self, message: Message) -> None:
        message_type = message["type"]

        if self.state is ASGICycleState.REQUEST:
            if message_type != "http.response.start":
                raise RuntimeError(
                    f"Expected 'http.response.start', received: {message_type}"
                )

            self.state = ASGICycleState.RESPONSE

        elif self.state is ASGICycleState.RESPONSE:
            if message_type != "http.response.body":
                raise RuntimeError(
                    f"Expected 'http.response.body', received: {message_type}"
                )

            content = message.get("body", b"")
            more_body = message.get("more_body", False)

            self.body += content

            if not more_body:
                self.put_message({"type": "http.disconnect"})
                self.state = ASGICycleState.COMPLETE


@dataclass
class Grevillea:

    app: ASGIApp

    def __call__(self, request) -> typing.Tuple[str, int]:
        try:
            response = self.asgi(request)
        except BaseException as exc:
            raise exc
        else:
            return response

    def asgi(self, request) -> typing.Tuple[str, int]:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        environ = request.environ
        scope = {
            "type": "http",
            "server": (environ["SERVER_NAME"], environ["SERVER_PORT"]),
            "client": environ["REMOTE_ADDR"],
            "method": request.method,
            "path": request.path,
            "scheme": request.scheme,
            "http_version": "1.1",
            "root_path": environ["RAW_URI"] or None,
            "query_string": request.query_string,
            "headers": [[k.encode(), v.encode()] for k, v in request.headers],
        }
        body = request.get_data() or b""
        asgi_cycle = ASGICycle(scope, loop=loop)
        asgi_cycle.put_message(
            {"type": "http.request", "body": body, "more_body": False}
        )
        response = asgi_cycle(self.app)
        return response
