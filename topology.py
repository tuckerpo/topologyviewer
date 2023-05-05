# pylint: disable=too-many-public-methods

"""
The `topology` module provides a `Topology` class for representing the topology of an entire
    easymesh network, as seen by the controller of the network.

Classes:
    `Topology`: Represents the topology of an entire easymesh network,
    as seen by the controller of the network.

Attributes:
    No public module level attributes.

Functions:
    No public module level functions.

Usage:
```
    from topology import Topology
    topo = Topology(agents, controller_id)
    agents = topo.get_agents()
    interface = topo.get_interface_from_hash(hash_id)
    agent = topo.get_agent_from_id(agent_mac_addr)
    station = topo.get_station_from_hash(hash_id)
    connections = topo.get_connections()
    num_connections = topo.get_num_connections_total()
    station_by_mac = topo.get_sta_by_mac(mac)
    num_stations = topo.get_num_stations_total()
    stations = topo.get_stations()
    bsses = topo.get_bsses()
    radios = topo.get_radios()
    agent_id = topo.get_agent_id_from_bssid(bssid)
```
"""

from pprint import pformat
from typing import List, Tuple
from easymesh import Agent
from easymesh import Radio
from easymesh import BSS
from easymesh import Station
from easymesh import Interface

class Topology():
    """Represents the topology of an entire easymesh network, as seen by the controller of the
    network.
    """
    def __init__(self, agents: List[Agent], controller_id: str) -> None:
        self.agents = agents
        self.controller_id = controller_id
        self.controller = {}

        # Mark the controller
        for agent in agents:
            if agent.get_id() == controller_id:
                agent.isController = True
                self.controller = agent

    def __repr__(self) -> str:
        return f"Topology<{id(self)}> agents {pformat(self.agents)}"

    def get_agents(self) -> List[Agent]:
        """Get all known agent on the network.

        Returns:
            List[Agent]: All known agents on the network, inclusive of the controller.
        """
        return self.agents

    def get_interface_from_hash(self, hash_id: str) -> Interface:
        """Gets an interface with the given hash id

        Args:
            hash_id (str): The hash ID of the node.

        Returns:
            Interface: The interface object with hash_id if found, None otherwise
        """
        for agent in self.agents:
            for interface in agent.get_interfaces():
                if interface.get_hash_id() == hash_id:
                    return interface
        return None

    def get_agent_from_hash(self, hash_id: str) -> Agent:
        """Gets an agent with given hashed ID

        Args:
            hash_id (str): The hash ID of the node.

        Returns:
            Agent: The agent with hashed ID
        """
        for agent in self.agents:
            if agent.get_hash_id() == hash_id:
                return agent
        return None

    def get_station_from_hash(self, hash_id: str) -> Station:
        """Gets a station with given hashed MAC

        Args:
            hash_id (str): The hash ID of the node.

        Returns:
            Station: The station with hashed MAC, or None if not found
        """
        for agent in self.agents:
            for sta in agent.get_connected_stations():
                if sta.get_hash_mac() == hash_id:
                    return sta
        return None

    def get_connections(self) -> List[Tuple]:
        """Return the connections in the network topology

        Returns:
            list of connection 2-tuples ("bssid" : "station_mac")
            where station_mac is associated with and connected to bssid
        """
        connections: List[Tuple] = []
        for agent in self.agents:
            for radio in agent.get_radios():
                for bss in radio.get_bsses():
                    for sta in bss.get_connected_stations():
                        connections.append((bss.get_bssid(), sta.get_mac()))
        return connections

    def get_num_connections_total(self) -> int:
        """Get the total number of connections (stations to agents) in the network topology.

        Returns:
            int: number of edges in the topology graph.
        """
        return len(self.get_connections())

    def get_sta_by_mac(self, mac: str) -> Station:
        """
        Returns the Station object with the specified MAC address.

        Args:
            mac (str): the MAC address of the Station to retrieve

        Returns:
            Station: the Station object with the specified MAC address, or None if not found
        """
        stations = self.get_stations()
        for station in stations:
            if station.get_mac() == mac:
                return station
        return None

    def get_num_stations_total(self) -> int:
        """Total number of connected, associated stations in the network topology.
        TODO: this should eventually account for unassociated stations as well.

        Returns:
            int: number of connected, associated stations in the network.
        """
        num_stations = 0
        for agent in self.agents:
            for radio in agent.get_radios():
                for bss in radio.get_bsses():
                    num_stations = num_stations + bss.get_num_connected_stations()
        return num_stations

    def get_stations(self) -> List[Station]:
        """Get all known (connection, associated) stations on the network.

        Returns:
            List[Station]: All known stations connected to some BSS on the network.
        """
        stations: List[Station] = []
        for agent in self.agents:
            for radio in agent.get_radios():
                for bss in radio.get_bsses():
                    for sta in bss.get_connected_stations():
                        stations.append(sta)
        return stations

    def get_bsses(self) -> List[BSS]:
        """Get all known BSSes on the network.

        Returns:
            List[BSS]: Every known BSS across all radios on all agents.
        """
        bss_list: List[BSS] = []
        for agent in self.agents:
            for radio in agent.get_radios():
                for bss in radio.get_bsses():
                    bss_list.append(bss)
        return bss_list

    def get_radios(self) -> List[Radio]:
        """Get all known radios on the network.

        Returns:
            List[Radio]: Every known radio across all agents.
        """
        radio_list: List[Radio] = []
        for agent in self.agents:
            radio_list = radio_list + agent.get_radios()
        return radio_list

    def get_agent_id_from_bssid(self, bssid: str) -> str:
        """Return the Agent ID that holds bssid, if any.

        Args:
            bssid (string): bssid of interest

        Returns:
            The Agent ID that holds BSSID, or empty string if not found.
        """
        for agent in self.agents:
            for radio in agent.get_radios():
                for bss in radio.get_bsses():
                    if bss.get_bssid() == bssid:
                        return agent.get_id()
        return ""

    def get_ruid_from_sta(self, sta: str) -> str:
        """Return the RUID that the STA is connected to, if any.

        Args:
            sta (str): station mac of interest

        Returns:
            str: RUID that STA is connected to (either VBSS or normal BSS)
                Empty string if STA is not associated with any RUID
        """
        for agent in self.agents:
            for radio in agent.get_radios():
                for bss in radio.get_bsses():
                    for station in bss.get_connected_stations():
                        if station.get_mac() == sta:
                            return radio.get_ruid()
        return ""

    def validate_vbss_move_request(self, station_mac: str, target_ruid: str) -> bool:
        """Validates that 'station_mac' is not already associated with 'target_ruid'
        to avoid useless work.

        Args:
            station_mac (str): The MAC of the STA we want to move.
            target_ruid (str): The target radio ID to move the VBSS to.

        Returns:
            bool: True if station_mac is not already living on target_ruid, false otherwise.
        """
        return not self.get_ruid_from_sta(station_mac) == target_ruid

    def get_bssid_connection_for_sta(self, sta_mac: str) -> str:
        """Get the BSSID that the STA is connected to, if any.

        Args:
            sta_mac (str): MAC address of the STA

        Returns:
            str: BSSID that STA is connected to, or empty string.
        """
        for connection in self.get_connections():
            if connection[1] == sta_mac:
                return connection[0]
        return ""

    def get_agent_by_id(self, agent_id: str) -> Agent:
        """Get an Agent by it's ID MAC address

        Args:
            agent_id (str): The ID MAC of the Agent to fetch.

        Returns:
            Agent: The Agent if found, None otherwise.
        """
        for agent in self.agents:
            if agent.get_id() == agent_id:
                return agent
        return None

    def get_controller(self) -> Agent:
        """Get the Controller in the topology.

        Returns:
            Agent: The Controller (which is an Agent) of the topology, None otherwise.
        """
        if self.controller:
            return self.controller
        return None

    def get_ssid(self) -> str:
        """Get the SSID of the network being advertised by the controller's 2.4 GHz radio

        Returns:
            str: The SSID if found, error message otherwise.
        """
        if self.controller:
            return self.controller.get_radios()[0].get_bsses()[0].params["SSID"]
        return "No SSID found"

    def get_radio_by_ruid(self, ruid: str) -> Radio:
        """Look up a Radio object by Radio UID

        Args:
            ruid (str): The RUID

        Returns:
            Radio: The Radio object corresponding to ruid if found, None otherwise
        """
        for radio in self.get_radios():
            if radio.get_ruid() == ruid:
                return radio
        return None

    def get_bss_by_bssid(self, bssid: str):
        """Get a BSS object via it's BSSID

        Returns: BSS object with bssid 'bssid', or None if not found
        """
        for radio in self.get_radios():
            for bss in radio.get_bsses():
                if bss.get_bssid() == bssid:
                    return bss
        return None

    def get_agent_by_ruid(self, ruid: str) -> Agent:
        """Get an Agent by RUID

        Args:
            ruid (str): The RUID

        Returns:
            Agent: the Agent if found, None otherwise
        """
        for agent in self.agents:
            for radio in agent.get_radios():
                if radio.get_ruid() == ruid:
                    return agent
        return None
