"""
Module for doing RPC to the NBAPI over HTTP
"""

# pylint: disable=line-too-long, logging-fstring-interpolation, import-error, too-many-arguments

import logging
import json
import requests
from path_parser import parse_index_from_path_by_key
from easymesh import BSS, Radio
from controller_ctx import ControllerConnectionCtx

def send_nbapi_command(conn_ctx: ControllerConnectionCtx, command_payload: json):
    """
    Sends an NBAPI command to the EasyMesh controller using the specified connection context.

    Args:
        conn_ctx (ControllerConnectionCtx): The connection context to use for the request.
        command_payload (json): The payload of the NBAPI command to send.

    Returns:
        None
    """
    url = f"http://{conn_ctx.ip_addr}:{conn_ctx.port}/commands"
    logging.debug(f"Sending NBAPI command to {url}, payload={command_payload}")
    response = requests.post(url=url, timeout=3, json=command_payload)
    if not response.ok:
        logging.error(f"Failed to send NBAPI command to f{url}: command payload: {command_payload}, HTTP code: {response.status_code}")

def send_vbss_move_request(conn_ctx: ControllerConnectionCtx, client_mac: str, dest_ruid: str, ssid: str, password: str, bss: BSS):
    """Sends a VBSS move request over the network.
    ubus call Device.WiFi.DataElements.Network.Device.1.Radio.2.BSS.2 TriggerVBSSMove "{'client_mac':'c2:f5:2b:3d:d9:7e', 'dest_ruid':'96:83:c4:16:83:b2','ssid':'iNetVBSS2', 'pass':'password'}"
    Args:
        conn_ctx (ControllerConnectionCtx): The connection to the topology's controller.
        client_mac (str): The client we're moving the VBSS for.
        dest_ruid (str): The destination radio for the VBSS move.
        ssid (str): The name of the VBSS on the destination radio.
        password (str): The password for the VBSS on the destination radio.
        bss (BSS): The NBAPI BSS node we're calling this method on.
    """
    if not conn_ctx:
        raise ValueError()
    device_idx, radio_idx, bss_idx = "", "", ""
    device_idx = parse_index_from_path_by_key(bss.path, 'Device')
    radio_idx = parse_index_from_path_by_key(bss.path, 'Radio')
    bss_idx = parse_index_from_path_by_key(bss.path, 'BSS')
    json_payload = {
        "sendresp": True,
        "commandKey": "",
        "command": f"Device.WiFi.DataElements.Network.Device.{device_idx}.Radio.{radio_idx}.BSS.{bss_idx}.TriggerVBSSMove",
        "inputArgs": {"client_mac": client_mac, "dest_ruid": dest_ruid, "ssid": ssid, "pass": password}
    }
    send_nbapi_command(conn_ctx, json_payload)

def send_vbss_creation_request(conn_ctx: ControllerConnectionCtx, vbssid: str, client_mac: str, ssid: str, password: str, radio: Radio):
    """Sends a VBSS creation request to an NBAPI Radio endpoint.

    Args:
        conn_ctx (ControllerConnectionCtx): The connection to the topology's controller
        vbssid (str): The VBSSID of the VBSS to make.
        client_mac (str): The MAC address of the client that this VBSS is for.
        ssid (str): The SSID of the VBSS.
        password (str): The password for the VBSS.
        device_idx (int): The NBAPI Device index.("Device.WiFi.DataElements.Network.Device.n")
        radio_idx (int): The NBAPI Radio index. ("Device.WiFi.DataElements.Network.Device.1.Radio.n")

    Raises:
        ValueError: Throws if not provided a valid ControllerConnectionCtx
    """
    if not conn_ctx:
        raise ValueError()
    device_idx = parse_index_from_path_by_key(radio.path, 'Device')
    radio_idx  = parse_index_from_path_by_key(radio.path, 'Radio')
    json_payload = {"sendresp": True,
                    "commandKey": "",
                    "command": f"Device.WiFi.DataElements.Network.Device.{device_idx}.Radio.{radio_idx}.TriggerVBSSCreation",
                    "inputArgs": {"vbssid": vbssid, "client_mac": client_mac, "ssid": ssid, "pass": password}}
    send_nbapi_command(conn_ctx, json_payload)

def send_vbss_destruction_request(conn_ctx: ControllerConnectionCtx, client_mac: str, should_disassociate: bool, bss: BSS):
    """Sends a VBSS destruction request to an NBAPI BSS endpoint.

    Args:
        conn_ctx (ControllerConnectionCtx): The connection to the topology's controller
        client_mac (str): The client MAC to disassociate (currently unused on the server -- all clients are disassociated if 'should_disassociate' is set.)
        should_disassociate (bool): If true, disassociate all clients prior to tearing down the BSS.
        bss (BSS): The BSS we're tearing down.
    """
    if not conn_ctx:
        raise ValueError()
    device_idx = parse_index_from_path_by_key(bss.path, 'Device')
    radio_idx = parse_index_from_path_by_key(bss.path, 'Radio')
    bss_idx = parse_index_from_path_by_key(bss.path, 'BSS')
    json_payload = {"sendresp": True,
                    "commandKey": "",
                    "command": f"Device.WiFi.DataElements.Network.Device.{device_idx}.Radio.{radio_idx}.BSS.{bss_idx}.TriggerVBSSDestruction",
                    "inputArgs": {"client_mac": client_mac, "should_disassociate": should_disassociate}}
    send_nbapi_command(conn_ctx, json_payload)


def send_client_steering_request(conn_ctx: ControllerConnectionCtx, sta_mac: str, new_bssid: str):
    """
    Sends a client steering request to the EasyMesh controller using the specified connection context.

    Args:
        conn_ctx (ControllerConnectionCtx): The connection context to use for the request.
        sta_mac (str): The MAC address of the client station to steer.
        new_bssid (str): The BSSID of the target AP to steer the client to.

    Raises:
        ValueError: If the `conn_ctx` argument is `None`.

    Returns:
        None
    """
    if not conn_ctx:
        raise ValueError("Passed a None connection context.")
    # ubus call Device.WiFi.DataElements.Network ClientSteering '{"station_mac":"<client_mac>", "target_bssid":"<BSSID>"}'
    json_payload = {"username": "admin",
                    "password": "admin",
                    "sendresp": True,
                    "commandKey": "",
                    "command": "X_PRPL-ORG_WiFiController.Network.ClientSteering",
                    "inputArgs": {"station_mac": sta_mac,
                                  "target_bssid": new_bssid}}
    send_nbapi_command(conn_ctx, json_payload)
