# pylint: disable=too-few-public-methods

"""
Module that holds HTTP connection context data.
"""

class HTTPBasicAuthParams():
    """Class to hold HTTP basic authorization parameters (username, password).
    """
    def __init__(self, user: str, password: str) -> None:
        self.user = user
        self.password = password
    def __repr__(self) -> str:
        return f"HTTPBasicAuthParams: username: {self.user}, pass: {self.password}"
