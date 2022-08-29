from pprint import pformat

class Topology():
    def __init__(self, agents: dict, stations: dict):
        self.agents = agents
        self.stations = stations
        self.__is_connected_key = 'ConnectedTo'
    def __repr__(self) -> str:
        return f"Topology<{id(self)}> agents {pformat(self.agents)} stations {pformat(self.stations)}"
    def get_connections(self):
        """Return the connections in the network topology

        Returns:
            list of connection 2-tuples ("agent_mac" : "station_mac")
            where station_mac is associated with and connected to some BSS on agent_mac
        """        
        connections = list()
        for station in self.stations:
            if self.__is_connected_key in self.stations[station].keys() and self.stations[station][self.__is_connected_key] in self.agents:
                connections.append((self.stations[station][self.__is_connected_key], station))
        return connections