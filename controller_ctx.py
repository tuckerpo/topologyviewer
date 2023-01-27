"""
Module that represents a HTTP connection to a topology's Controller.
"""

class ControllerConnectionCtx():
    """Class to hold the connect to a EasyMesh topology's Controller.
    """
    def __init__(self, ip: str, port: str, auth: HTTPBasicAuthParams) -> None:
        if not auth:
            raise ValueError("Passed a None auth object.")
        self.ip = ip
        self.port = port
        self.auth = auth
