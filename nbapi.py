# pylint: disable=logging-fstring-interpolation, line-too-long, too-many-nested-blocks, too-many-locals, too-many-branches, too-many-statements, too-many-instance-attributes, import-error, fixme

"""Module containing code to get NBAPI payloads and parse them into Topology objects.
"""

from typing import List, Dict
from time import sleep
import threading
import re
import logging
import requests

from controller_ctx import ControllerConnectionCtx
from topology import Topology
from easymesh import Agent, Interface, Neighbor, Station, UnassociatedStation, Radio, BSS, ORIENTATION
from nbapi_persistent import handle_station_has_moved, station_has_undergone_move, add_new_signal_strength_measurement, register_station_to_radio, clear_all_signal_strength_measurements

logger = logging.getLogger(__name__)

def marshall_nbapi_blob(nbapi_json) -> Topology:
    """Parse a list of NBAPI json entries

    Args:
        nbapi_json (json): NBAPI json response.

    Returns:
        Topology: Topological representation of the parsed data.

    Note:
        This is pretty fragile, and depends on the NBAPI<->HTTP proxy interface not changing.
    """
    # For a topology demo, we really only care about Devices that hold active BSSs (aka Agents)
    # and their connected stations.
    if not isinstance(nbapi_json, list):
        return Topology({}, {})

    agent_dict: Dict[str, Agent] = {}
    iface_dict: Dict[str, Interface] = {}

    for entry in nbapi_json:
        path = entry['path']
        params = entry['parameters']
        # 0. Find the controller in the network.
        if re.search(r'\.Network\.$', path):
            controller_id = params['ControllerID']

        # 1. Build the agent list.
        if re.search(r"\.Device\.\d{1,10}\.$", path):
            agent_dict[path] = Agent(path, params)


        # 2. Get Interfaces of each Agent
        if re.search(r"\.Interface\.\d{1,10}\.$", path):
            for agent in agent_dict.values():
                if path.startswith(agent.path):
                    iface = Interface(path, params)
                    iface.set_parent_agent(agent)
                    agent.add_interface(iface)
                    iface_dict[path] = iface

        # 3. Get Neighbors of each Interface
        controller_backhaul_interface = {}
        controller_agent = {}
        if re.search(r"\.Neighbor\.\d{1,10}\.$", path):
            for agent in agent_dict.values():
                for interface in agent.get_interfaces():
                    if path.startswith(interface.path):
                        interface.add_neighbor(Neighbor(path, params))

                        # Mark the backhaul interface of the controller: should be Ethernet type and have at least 1 neighbor
                        if (agent.get_id() == controller_id) and (interface.params['MediaType']<=1):
                            controller_backhaul_interface = interface
                            controller_backhaul_interface.orientation = ORIENTATION.DOWN
                            controller_agent = agent

        # Controller has no neighbours yet, mark first ethernet interface as backhaul
        if not controller_backhaul_interface:
            for agent in agent_dict.values():
                if agent.get_id() == controller_id:
                    controller_agent = agent
                    for iface in agent.get_interfaces():
                        if iface.params['MediaType']<=1:
                            controller_backhaul_interface = iface
                            controller_backhaul_interface.orientation = ORIENTATION.DOWN
                            break


        # 4. Link interfaces to parents
        if re.search(r"\.MultiAPDevice\.Backhaul\.$", path):
            if params['LinkType'] == "None":
                continue

            # Ethernet backhaul connections must always link to the controller
            if params['LinkType'] == "Ethernet":
                # Search for backhaul interface on the device that is getting processed
                for iface in iface_dict.values():
                    # TODO PPM-2043: HACK: prplMesh doesn't report Parent/Child Relation of Agent with Wired Connection
                    # Instead, assume wired backhaul from agent(s) to controller on firt ethernet interface of agent.
                    if iface.get_interface_number() == "1":
                        if not controller_backhaul_interface:
                            continue
                        if iface.get_mac() == controller_backhaul_interface.get_mac():
                            continue
                        if not controller_backhaul_interface.has_child_iface(iface.get_mac()):
                            controller_backhaul_interface.add_child(iface)
                            iface.orientation = ORIENTATION.UP
                            controller_agent.add_child(iface.get_parent_agent())


            elif params['LinkType'] == "Wi-Fi":
                for child_iface in iface_dict.values():
                    if child_iface.params['MACAddress'] == params['MACAddress']: # interface on device that is getting processed
                        for parent_iface in iface_dict.values():
                            if parent_iface.params['MACAddress'] == params['BackhaulMACAddress']: # interface on parent device
                                parent_iface.add_child(child_iface)
                                parent_iface.orientation = ORIENTATION.DOWN
                                child_iface.orientation = ORIENTATION.UP
                                parent_iface.get_parent_agent().add_child(child_iface.get_parent_agent())
                                break

        # 5. Get Radios, add them to Agents
        if re.search(r"\.Radio\.\d{1,10}\.$", path):
            for agent in agent_dict.values():
                if path.startswith(agent.path):
                    agent.add_radio(Radio(path, params))

        # 6. Collect BSSs and map them back to radios and interfaces
        if re.search(r"\.BSS\.\d{1,10}\.$", path):
            for agent in agent_dict.values():
                for radio in agent.get_radios():
                    if path.startswith(radio.path):
                        bss = BSS(path, params)
                        radio.add_bss(bss)
                        for iface in iface_dict.values():
                            if radio.params['ID'] == iface.params['MACAddress']:
                                bss.interface = iface
                                break

        # 7. Map Stations to the BSS they're connected to.
        station_list: List[Station] = []
        if re.search(r"\.STA\.\d{1,10}\.$", path):
            for agent in agent_dict.values():
                for radio in agent.get_radios():
                    for bss in radio.get_bsses():
                        if path.startswith(bss.path):
                            sta = Station(path, params)
                            station_list.append(sta)
                            bss.add_connected_station(sta)
                            if station_has_undergone_move(sta.get_mac(), radio.get_ruid()):
                                handle_station_has_moved(sta.get_mac(), radio.get_ruid())
                            register_station_to_radio(sta.get_mac(), radio.get_ruid())
                            bss.interface.orientation = ORIENTATION.DOWN
                            # Exclude stations that are actually agents
                            if not bss.interface.get_parent_agent().is_child(sta.get_mac()):
                                bss.interface.add_connected_station(sta)
                            # Append RSSI measurements.
                            add_new_signal_strength_measurement(sta.get_mac(), radio.get_ruid(), sta.get_rssi())

        # 8. Check and set stations steering history
        if re.search(r"\.SteerEvent\.\d{1,10}\.$", path):
            for station in station_list:
                if station.params["MACAddress"] == params["DeviceId"] and params["Result"] == "Success":
                    station.set_steered(True)

        if re.search(r"\.UnassociatedSTA\.\d{1,10}\.$", path):
            for agent in agent_dict.values():
                for radio in agent.get_radios():
                    if path.startswith(radio.path):
                        unassoc_sta = UnassociatedStation(path, params)
                        unassoc_sta.set_parent_radio(radio)
                        add_new_signal_strength_measurement(unassoc_sta.get_mac(), radio.get_ruid(), params['SignalStrength'])

    return Topology(list(agent_dict.values()), controller_id)



class NBAPITask(threading.Thread):
    """
    A class for a worker thread that periodically retrieves the network topology using NBAPI.

    Attributes:
        connection_ctx (ControllerConnectionCtx): The controller connection context object.
        cadence_ms (int): The cadence in milliseconds between topology retrievals.

    Raises:
        ValueError: If a None connection context is passed to the constructor.

    Methods:
        run(self) -> None:
            The method that will be executed when the thread is started.
            It periodically retrieves the network topology using NBAPI.
        __repr__(self) -> str:
            Returns a string representation of the NBAPI_Task object.
        quit(self) -> None:
            Sets the quitting flag to True, signaling the thread to exit gracefully.
    """
    def __init__(self, connection_ctx: ControllerConnectionCtx, cadence_ms: int = 1000):
        if not connection_ctx:
            raise ValueError("Passed a None connection context.")
        super().__init__()
        self.connection_ctx = connection_ctx
        self.cadence_ms = cadence_ms
        self.quitting = False
        self.heartbeat_count = 0
        self.connection_timeout_seconds = 3
        self.read_timeout_seconds = 10
        self.topology: Topology = None
        # Default value if unchanged in prplos config
        self.root_dm_path: str = "Device.WiFi.DataElements."
        if not connection_ctx.auth:
            self.auth=('admin', 'admin')
        else:
            self.auth=(connection_ctx.auth.user, connection_ctx.auth.password)

    def resolve_root_data_model_path(self) -> None:
        """
        Sends an HTTP GET to the NBAPI endpoint that exposes the root data model path.
        In olden times, the root controller data model path was always "Device.WiFi.DataElements"
        This is now configurable via prplos.
        We initially assume it's still "Device.WiFi.DataElements", but if that fails to resolve,
        this method should be called to update the self.root_dm_path member.
        """
        url = f"http://{self.connection_ctx.ip_addr}:{self.connection_ctx.port}/serviceElements/root_dm_path"
        logging.debug(f"Checking root DM path at {url}")
        response = requests.get(url=url, auth=self.auth, timeout=(self.connection_timeout_seconds, self.read_timeout_seconds))
        if not response.ok:
            logging.error(f"{url} response code {response.status_code} '{response.reason}': cannot resolve root DM path")
        else:
            response_json = response.json()
            logging.debug(f"Root DM path is {response_json}")
            if self.root_dm_path != response_json['path']:
                self.root_dm_path = response_json['path']

    # Override threading.Thread.run(self)->None
    def run(self):
        """
        The method that will be executed when the thread is started.
        It periodically retrieves the network topology using NBAPI.
        """
        clear_all_signal_strength_measurements()
        while not self.quitting:
            url = f"http://{self.connection_ctx.ip_addr}:{self.connection_ctx.port}/serviceElements/{self.root_dm_path}"
            logging.debug(f"Ping -> {self.connection_ctx.ip_addr}:{self.connection_ctx.port} #{self.heartbeat_count}")
            nbapi_root_request_response = requests.get(url=url, auth=self.auth, timeout=(self.connection_timeout_seconds, self.read_timeout_seconds))
            if not nbapi_root_request_response.ok:
                logging.error(f"{self.connection_ctx.ip_addr}:{self.connection_ctx.port} HTTP response code {nbapi_root_request_response.status_code} '{nbapi_root_request_response.reason}'")
            else:
                logging.debug(f"Pong <- {self.connection_ctx.ip_addr}:{self.connection_ctx.port} #{self.heartbeat_count}")
                self.heartbeat_count = self.heartbeat_count + 1
                nbapi_root_json_blob = nbapi_root_request_response.json()
                self.topology = marshall_nbapi_blob(nbapi_root_json_blob)
                # If the Controller could not be resolved by parsing the NBAPI blob, perhaps we have the wrong data model root.
                if self.topology.get_controller() is None:
                    logging.debug("Could not marshall NBAPI blob -- fetching the data model root in case it must be refreshed.")
                    self.resolve_root_data_model_path()
                sleep(self.cadence_ms // 1000)

    def get_controller_id(self) -> str:
        """Get the controller ID for this task's current connection context.

        Returns:
            str: The MAC address of the controller
        """
        return self.topology.get_controller().get_id()

    def get_topology(self) -> Topology:
        """Get the most recently parsed topological representation of the network.

        Returns:
            Topology: The current network topology.
        """
        return self.topology

    def __repr__(self):
        return f"NBAPI_Task: ip: {self.connection_ctx.ip_addr}, port: {self.connection_ctx.port}, cadence (ms): {self.cadence_ms}"
    def quit(self):
        """
        Sets the quitting flag to True, signaling the thread to exit gracefully.
        """
        logging.debug("Hey folks! NBAPI thread here. Time to die!")
        self.quitting = True
