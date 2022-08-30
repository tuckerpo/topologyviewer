from pprint import pformat
from tkinter import N
from typing import List, Tuple
from easymesh import Agent
from easymesh import Radio
from easymesh import BSS
from easymesh import Station

class Topology():
    def __init__(self, agents) -> None:
        self.agents = agents
    def __repr__(self) -> str:
        return f"Topology<{id(self)}> agents {pformat(self.agents)}"
    def get_agents(self) -> List[Agent]:
        return self.agents
    def get_connections(self) -> List[Tuple]:
        """Return the connections in the network topology

        Returns:
            list of connection 2-tuples ("bssid" : "station_mac")
            where station_mac is associated with and connected to bssid
        """
        connections = list()
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
        stations = list()
        for agent in self.agents:
            for radio in agent.get_radios():
                for bss in radio.get_bsses():
                    for sta in bss.get_connected_stations():
                        stations.append(sta)
        return stations

    def get_bsses(self) -> List[BSS]:
        bss_list = list()
        for agent in self.agents:
            for radio in agent.get_radios():
                for bss in radio.get_bsses():
                    bss_list.append(bss)
        return bss_list

    def get_agent_id_from_bssid(self, bssid) -> str:
        """Return the Agent ID that holds bssid, if any.

        Args:
            bssid (string): bssid of interest
        """
        for agent in self.agents:
            for radio in agent.get_radios():
                for bss in radio.get_bsses():
                    if bss.get_bssid() == bssid:
                        return agent.get_id()
        return ""