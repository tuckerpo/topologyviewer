# pylint: disable=too-few-public-methods

"""
Module that represents a HTTP connection to a topology's Controller.
"""
from http_auth import HTTPBasicAuthParams

class ControllerConnectionCtx():
    """Class to hold the connect to a EasyMesh topology's Controller.
    """
    def __init__(self, ip_addr: str, port: str, auth: HTTPBasicAuthParams) -> None:
        if not auth:
            raise ValueError("Passed a None auth object.")
        self.ip_addr = ip_addr
        self.port = port
        self.auth = auth
