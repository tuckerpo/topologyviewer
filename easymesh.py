from typing import List
from enum import Enum
import hashlib

# mediaType_to_str = dict([
#     (0x0, 'IEEE_802_3U_FAST_ETHERNET'),
#     (0x1, 'IEEE_802_3AB_GIGABIT_ETHERNET'),
#     (0x100, 'IEEE_802_11B_2_4_GHZ'),
#     (0x101, 'IEEE_802_11G_2_4_GHZ'),
#     (0x102, 'IEEE_802_11A_5_GHZ'),
#     (0x103, 'IEEE_802_11N_2_4_GHZ'),
#     (0x104, 'IEEE_802_11N_5_GHZ'),
#     (0x105, 'IEEE_802_11AC_5_GHZ'),
#     (0x106, 'IEEE_802_11AD_60_GHZ'),
#     (0x107, 'IEEE_802_11AF'),
#     (0x108, 'IEEE_802_11AX'),
#     (0x200, 'IEEE_1901_WAVELET'),
#     (0x201, 'IEEE_1901_FFT'),
#     (0x300, 'MOCA_V1_1'),
#     (0xffff, 'UNKNOWN_MEDIA')])

mediaType_to_str = dict([
    (0x0, 'Fast Ethernet'),
    (0x1, 'Gigabit Ethernet'),
    (0x100, 'B 2.4GHz'),
    (0x101, 'G 2.4GHz'),
    (0x102, 'A 5 GHz'),
    (0x103, 'N 2.4 GHz'),
    (0x104, 'N 5 GHz'),
    (0x105, 'AC 5 GHz'),
    (0x106, 'AD 60 GHz'),
    (0x107, 'AF'),
    (0x108, 'AX'),
    (0x200, 'IEEE_1901_WAVELET'),
    (0x201, 'IEEE_1901_FFT'),
    (0x300, 'MOCA_V1_1'),
    (0xffff, 'UNKNOWN_MEDIA')])

class ORIENTATION(Enum):
    RIGHT = 0
    UP = 1
    DOWN = 2

class Station():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.x = 0
        self.y = 0
    def get_mac(self) -> str:
        if 'MACAddress' in self.params:
            return self.params['MACAddress']
        return ''
    def get_hash_mac(self) -> str:
        return hashlib.md5(self.get_mac().encode()).hexdigest()

class BSS():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.interface = {}
        self.connected_stations: List[Station] = []
        self.connected_sta_key = 'STA(s)'
        self.params[self.connected_sta_key] = []
    def add_connected_station(self, station) -> None:
        self.connected_stations.append(station)
        self.params[self.connected_sta_key].append(station.params)
    def get_num_connected_stations(self) -> int:
        return len(self.connected_stations)
    def get_connected_stations(self) -> List[Station]:
        return self.connected_stations
    def get_bssid(self) -> str:
        if 'BSSID' in self.params:
            return self.params['BSSID']
        return ''

class Radio():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.bsses: List[BSS] = []
        self.bss_key = 'BSS'
        self.params[self.bss_key] = []
    def add_bss(self, bss) -> None:
        self.bsses.append(bss)
        self.params[self.bss_key].append(bss.params)
    def get_ruid(self) -> str:
        if 'ID' in self.params:
            return self.params['ID']
        return ''
    def get_bsses(self) -> List[BSS]:
        return self.bsses

class Neighbor():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params

class Interface():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.neighbors: List[Neighbor] = []
        self.neighbors_key = 'neighbors'
        self.params[self.neighbors_key] = []
        self.children: List[Interface] = []
        self.parentAgent: Agent = {}
        self.children_key = 'children'
        self.params[self.children_key] = []
        self.connected_stations: List[Station] = []
        self.connected_sta_key = 'STA(s)'
        self.params[self.connected_sta_key] = []
        self.params["MediaTypeString"] = mediaType_to_str[self.params["MediaType"]]
        self.params["wired"] = self.params["MediaType"]==0x0 or self.params["MediaType"]==0x1
        self.params["wireless"] = self.params["MediaType"]>0x1 and self.params["MediaType"]<0x200
        self.x = 0
        self.y = 0
        self.orientation = ORIENTATION.RIGHT
    def add_connected_station(self, station) -> None:
        self.parentAgent.add_connected_station(station)
        self.connected_stations.append(station)
        self.params[self.connected_sta_key].append(station.params)
    def get_connected_stations(self) -> List[Station]:
        return self.connected_stations
    def add_neighbor(self, neighbor) -> None:
        self.neighbors.append(neighbor)
        self.params[self.neighbors_key].append(neighbor.params)
        # Sort neighbors by ID
        self.neighbors.sort(key=lambda n: n.params["ID"])
        self.params[self.neighbors_key].sort(key=lambda n: n["ID"])
    def get_neighbors(self) -> List[Neighbor]:
        return self.neighbors
    def add_child(self, interface) -> None:
        self.children.append(interface)
        self.params[self.children_key].append(interface.params)
        # Sort children by ID
        self.children.sort(key=lambda n: n.params["MACAddress"])
        self.params[self.children_key].sort(key=lambda n: n["MACAddress"])
    def get_children(self):
        return self.children
    def set_parent_agent(self, agent) -> None:
        self.parentAgent = agent
    def get_parent_agent(self):
        return self.parentAgent
    def get_interface_number(self):
        return self.path[-2::][0]

class Agent():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.isController = False
        self.radios: List[Radio] = []
        self.radios_key = 'Radios'
        self.params[self.radios_key] = []
        self.interfaces: List[Interface] = []
        self.interfaces_key = 'Interfaces'
        self.params[self.interfaces_key] = []
        self.children: List[Agent] = []
        self.connected_stations: List[Station] = []
        self.connected_sta_key = 'STA(s)'
        self.x = 0
        self.y = 0
    def add_child(self, agent) -> None:
        self.children.append(agent)
        # Sort children by ID
        self.children.sort(key=lambda n: n.get_id())
    def get_children(self):
        return self.children
    def num_children(self):
        return len(self.get_interfaces()) + len(self.get_connected_stations())
    def add_radio(self, radio) -> None:
        self.radios.append(radio)
        self.params[self.radios_key].append(radio.params)
    def add_interface(self, interface) -> None:
        self.interfaces.append(interface)
        self.params[self.interfaces_key].append(interface.params)
        self.interfaces.sort(key=lambda n: n.params["wired"])
    def sort_interfaces(self) -> None:
        def compare_interface_horizontal_coordinates(interface):
            return #interface
        #self.interfaces.sort(key=compare_interface_horizontal_coordinates)
    def add_connected_station(self, station) -> None:
        self.connected_stations.append(station)
    def get_connected_stations(self) -> List[Station]:
        return self.connected_stations
    def get_id(self) -> str:
        if 'ID' in self.params:
            return self.params['ID']
        return ''
    def get_hash_id(self) -> str:
        return hashlib.md5(self.get_id().encode()).hexdigest()
    def get_radios(self) -> List[Radio]:
        return self.radios
    def get_interfaces(self) -> List[Interface]:
        return self.interfaces
    def num_radios(self) -> int:
        return len(self.radios)
    def get_manufacturer(self) -> str:
        if 'ManufacturerModel' in self.params:
            return self.params['ManufacturerModel']
        return ''
    def get_interfaces_by_orientation(self, orientation: ORIENTATION) -> List[Interface]:
        interfaces = []
        for i in self.interfaces:
            if i.orientation == orientation:
                interfaces.append(i)
        return interfaces