# grevillea

**THIS PROJECT IS CURRENTLY UNMAINTAINED**

Google Cloud Functions support for ASGI.

## Requirements

Python 3.7

## Installation

```shell
pip3 install grevillea
```

## Example

```python3
from grevillea import Grevillea

async def app(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/plain; charset=utf-8"]],
        }
    )
    await send({"type": "http.response.body", "body": b"Hello, world!"})


handler = Grevillea(app)
```
