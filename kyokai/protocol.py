"""
This class handles the protocol side of Kyoukai.
"""
import asyncio
import logging

from kyokai.exc import HTTPException
from kyokai.request import Request
from kyokai.response import Response


class KyokaiProtocol(asyncio.Protocol):
    """
    The Kyoukai protocol.
    """
    def __init__(self, app, parent_context, context_cls):
        self.app = app
        self._transport = None
        self.ip = None
        self.client_port = None

        self.logger = logging.getLogger("Kyokai")

        self.loop = asyncio.get_event_loop()

        # Asphalt contexts
        self.parent_context = parent_context

        self.context_cls = context_cls

        self.buffer = b""

    def connection_made(self, transport: asyncio.Transport):
        """
        Set the appropriate self vals.
        """
        self.ip, self.client_port = transport.get_extra_info("peername")
        self._transport = transport

        self.logger.debug("Recieved connection from {}:{}".format(*transport.get_extra_info("peername")))

    def handle_resp(self, res: Response):
        """
        Handle a response.

        Sends the Response to the client.
        """
        data = res.to_bytes()
        self._transport.write(data)

    def data_received(self, data: bytes):
        """
        Create a new Request, and delegate Kyokai to process it.
        """
        self.logger.debug("Recieved {} bytes of data from client {}:{}, feeding."
                     .format(len(data), *self._transport.get_extra_info("peername"))
                     )

        # Delegate as response.
        self.logger.debug("Delegating response for client {}:{}.".format(*self._transport.get_extra_info("peername")))
        # Create a request
        self.buffer += data
        try:
            req = Request.from_data(self.buffer, self.ip)
        except HTTPException as e:
            # Delegate the HTTP exception, probably a 400.
            self.app._exception_handler(self, None, 400)
        else:
            if req.fully_parsed:
                # Reset buffer.
                self.logger.debug("Request for `{}` fully parsed, passing.".format(req.path))
                self.buffer = b""
                ctx = self.context_cls(req, self.parent_context)
                self.loop.create_task(self.app.delegate_request(self, ctx))
            else:
                # Continue.
                return

    def close(self):
        self._transport.close()