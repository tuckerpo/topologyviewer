# pylint: disable=too-few-public-methods

"""
Module that represents a HTTP connection to a topology's Controller.
"""
from http_auth import HTTPBasicAuthParams
import logging
import requests
import logging

class ControllerConnectionCtx():
    """Class to hold the connect to a EasyMesh topology's Controller.
    """
    def __init__(self, ip_addr: str, port: str, auth: HTTPBasicAuthParams) -> None:
        if not auth:
            raise ValueError("Passed a None auth object.")
        self.ip_addr = ip_addr
        self.port = port
        self.auth = auth
        self.sessionToken = ""
        self.authHeader = ""
        self.authType = "basic"
        self.connection_timeout_seconds = 2
        self.read_timeout_seconds = 2

    def setAuthHeader(self, token: str):
        self.authHeader = {'Authorization': "bearer {}".format(token)}

    def renewSession(self):
        self.authType="session"
        userPass = {"username": self.auth.user, "password": self.auth.password}
        url = f"http://{self.ip_addr}:{self.port}/session"
        logging.debug(f"Renewing session token")
        sessionID_response = requests.post(url=url, json=userPass, timeout=(self.connection_timeout_seconds, self.read_timeout_seconds))

        if not sessionID_response.ok:
            logging.error(f"Something went wrong in getting the session token!")
        else:
            self.sessionToken = sessionID_response.json()["sessionID"]
            self.setAuthHeader(self.sessionToken)
            logging.debug(f"Session token successfully set to: <- {self.sessionToken}")
