"""
Module for input validation. Contains functions to validate IP addresses, ports, and user input.
"""

import re
from typing import Tuple

from topology import Topology


def validate_ipv4(ip_addr: str):
    """Validate that an IPV4 address string is of the form 111.222.333.444

    Args:
        ip_addr (str): The IPV4 address.

    Returns:
        bool: True if the address is a valid IPV4 address, false otherwise.
    """
    return re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_addr)

def validate_port(port: str):
    """Validate that a port is a positive integer less than INT16_MAX

    Args:
        port (str): The port of interest

    Returns:
        bool: True if the port is valid, false otherwise.
    """
    return re.match(r'^\d{1,5}$', port) and int(port) > 0 and int(port) < 65535

def validate_mac(mac: str) -> bool:
    """Validate that a string is a valid MAC address of the form aa:bb:cc:dd:ee:ff

    Args:
        mac (str): The MAC address to validate

    Returns:
        bool: True if the MAC address is valid, false otherwise
    """
    return re.match("[0-9a-f]{2}([-:]?)[0-9a-f]{2}(\\1[0-9a-f]{2}){4}$", mac.lower())

def validate_vbss_client_mac(client_mac: str, topo: Topology) -> Tuple[bool, str]:
    """Ensure that a client MAC is not malformed and exists somewhere on the network.

    Args:
        client_mac (str): The client MAC of interest.
        topo (Topology): The network topology.

    Returns:
        Tuple[bool, str]: True if the client MAC is valid, false otherwise with an error message
    """
    is_valid = validate_mac(client_mac)
    if not is_valid:
        return False, f"Client MAC '{client_mac}' is malformed."
    for sta in topo.get_stations():
        if sta.get_mac() == client_mac:
            return True, ""
    return False, f"STA with MAC '{client_mac}' not known on the network"

def validate_vbss_vbssid(vbssid: str, topo: Topology) -> Tuple[bool, str]:
    """Check that a VBSSID is formatted correctly, and that it is unique in the network.

    Args:
        vbssid (str): The VBSSID to validate.
        topo (Topology): The network topology.

    Returns:
        Tuple[bool, str]: True if the VBSSID is OK, false and error message otherwise.
    """
    if not validate_mac(vbssid):
        return False, f"VBSSID '{vbssid}' is malformed."
    bss_list = topo.get_bsses()
    for bss in bss_list:
        if bss.get_bssid() == vbssid:
            return False, f"VBSSID '{vbssid}' is already in use in this network."
    return True, ""


def validate_vbss_password_for_creation(password: str) -> Tuple[bool, str]:
    """The server has a check that the password length is at least 8 chars.
    More restrictions may come with time.

    Args:
        password (str): the password
    Return:
        Tuple[bool, str]: True if the password is valid, false and the reason why otherwise.
    """
    if len(password) < 8:
        return (False, "Password must be at least 8 characters long.")
    return True, ""
