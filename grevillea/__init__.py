import asyncio
import enum
from typing import Any
from io import BytesIO
from dataclasses import dataclass, field


class ASGICycleState(enum.Enum):
    REQUEST = enum.auto()
    RESPONSE = enum.auto()


@dataclass
class ASGICycle:
    scope: dict
    body: BytesIO = BytesIO()
    state: ASGICycleState = ASGICycleState.REQUEST
    response: dict = field(default_factory=dict)

    def __call__(self, app: Any, body: bytes) -> dict:
        loop = asyncio.new_event_loop()
        self.app_queue: asyncio.Queue = asyncio.Queue(loop=loop)
        self.put_message({"type": "http.request", "body": body, "more_body": False})
        asgi_instance = app(self.scope, self.receive, self.send)
        asgi_task = loop.create_task(asgi_instance)
        loop.run_until_complete(asgi_task)
        return self.response

    def put_message(self, message: dict) -> None:
        self.app_queue.put_nowait(message)

    async def receive(self) -> dict:
        message = await self.app_queue.get()
        return message

    async def send(self, message: dict) -> None:
        message_type = message["type"]

        if self.state is ASGICycleState.REQUEST:
            if message_type != "http.response.start":
                raise RuntimeError(
                    f"Expected 'http.response.start', received: {message_type}"
                )

            status_code = message["status"]
            headers = {k: v for k, v in message.get("headers", [])}

            self.response["status_code"] = status_code
            self.response["headers"] = {
                k.decode(): v.decode() for k, v in headers.items()
            }

            self.state = ASGICycleState.RESPONSE

        elif self.state is ASGICycleState.RESPONSE:
            if message_type != "http.response.body":
                raise RuntimeError(
                    f"Expected 'http.response.body', received: {message_type}"
                )

            content = message.get("body", b"")
            more_body = message.get("more_body", False)

            self.body.write(content)

            if not more_body:
                self.response["body"] = self.body.getvalue().decode()
                self.put_message({"type": "http.disconnect"})


@dataclass
class Grevillea:

    app: Any

    def __call__(self, request) -> str:
        try:
            response = self.asgi(request)
        except BaseException as exc:
            raise exc
        else:
            return response

    def asgi(self, request) -> str:
        environ = request.environ
        scope = {
            "type": "http",
            "server": (environ["SERVER_NAME"], environ["SERVER_PORT"]),
            "client": environ["REMOTE_ADDR"],
            "method": request.method,
            "path": request.path,
            "scheme": request.scheme,
            "http_version": "1.1",
            "root_path": "",
            "query_string": request.query_string,
            "headers": [[k.encode(), v.encode()] for k, v in request.headers],
        }
        body = request.get_data() or b""
        response = ASGICycle(scope)(self.app, body=body)
        return response["body"]
