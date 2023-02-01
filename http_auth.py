"""
Module that holds HTTP connection context data.
"""

class HTTPBasicAuthParams():
    """Class to hold HTTP basic authorization parameters (username, password).
    """
    def __init__(self, user: str, pw: str) -> None:
        self.user = user
        self.pw = pw
    def __repr__(self) -> str:
        return f"HTTPBasicAuthParams: username: {self.user}, pass: {self.pw}"