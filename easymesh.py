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
        self.is_steered = False
    def get_mac(self) -> str:
        if 'MACAddress' in self.params:
            return self.params['MACAddress']
        return ''
    def get_hash_mac(self) -> str:
        return hashlib.md5(self.get_mac().encode()).hexdigest()
    def get_steered(self) -> bool:
        return self.is_steered
    def set_steered(self, steered: bool) -> None:
        self.is_steered = steered
    def get_rssi(self) -> int:
        """
        Get this station's last signal strength measurement.
        Note: this returns the signal strength of this station relative to the Agent that it is connected to.
        Returns:
            int: The signal strength. -127 if the field is not present.
        """
        if 'RSSI' in self.params:
            return self.params['RSSI']
        elif 'SignalStrength' in self.params:
            return self.params['SignalStrength']
        elif 'RCPI' in self.params:
            return self.params['RCPI']
        else:
            # Return -INT8_MAX, assuming dBm
            return -127

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
    def is_vbss(self) -> bool:
        """Is this BSS a Virtual BSS?

        Returns:
            bool: True if this is a VBSS, false otherwise.
        """
        if 'IsVBSS' in self.params:
            return self.params['IsVBSS']
        return False



class UnassociatedStationRSSIMeasurement():
    def __init__(self, station: str, signal_strength: int, channel_number: int, timestamp: int, ruid: str):
        self.station = station
        self.signal_strength = signal_strength
        self.channel_number = channel_number
        self.timestamp = timestamp
        self.ruid = ruid
    def get_signal_strength(self) -> int:
        return self.signal_strength
    def get_channel_number(self) -> int:
        return self.channel_number
    def get_parent_ruid(self) -> str:
        """The ruid of the Radio that saw this measurement.


        Returns:
            str: The RUID
        """
        return self.ruid
    def get_timestamp(self) -> int:
        return self.timestamp

class UnassociatedStation():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.rssi_measurements: List[UnassociatedStationRSSIMeasurement] = []
        self.parent_radio = None
    def get_mac(self) -> str:
        if 'MACAddress' in self.params:
            return self.params['MACAddress']
        return ''
    def set_parent_radio(self, radio) -> None:
        self.parent_radio = radio
    def add_rssi_measurement(self, params) -> None:
        rcpi = 0
        timestamp = 0
        ch_num = 0
        if 'SignalStrength' in params:
            rcpi = params['SignalStrength']
        if 'Timestamp' in params:
            timestamp = params['Timestamp']
        if 'ChannelNumer' in params:
            ch_num = params['ChannelNumber']
        self.rssi_measurements.append(UnassociatedStationRSSIMeasurement(self.get_mac(), rcpi, ch_num, timestamp, self.parent_radio.get_ruid()))
    def get_rssi_measurements(self):
        return self.rssi_measurements
    def get_parent_radio(self):
        return self.parent_radio

class Radio():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.bsses: List[BSS] = []
        self.bss_key = 'BSS'
        self.params[self.bss_key] = []
        self.unassociated_stations: List[UnassociatedStation] = []
    def add_bss(self, bss) -> None:
        self.bsses.append(bss)
        self.params[self.bss_key].append(bss.params)
    def get_ruid(self) -> str:
        if 'ID' in self.params:
            return self.params['ID']
        return ''
    def get_bsses(self) -> List[BSS]:
        return self.bsses
    def get_unassociated_stations(self) -> List[UnassociatedStation]:
        return self.unassociated_stations
    def add_unassociated_station(self, station: UnassociatedStation) -> None:
        self.unassociated_stations.append(station)
    def get_rssi_for_sta(self, sta: Station) -> int:
        """Gets the unassociated RSSI that this Radio has heard for a Station.

        Args:
            sta (Station): The station of interest

        Raises:
            ValueError: If the station is not being sniffed by this radio.

        Returns:
            int: The RSSI of the station relative to this radio.
        """
        station = self.get_unassociated_station_by_mac(sta.get_mac())
        if not station:
            raise ValueError("Unknown station: {}".format(sta.get_mac()))
        return station.get_rssi()
    def update_unassociated_sta(self, unassoc_sta: UnassociatedStation, params) -> None:
        sta = self.get_unassociated_station_by_mac(unassoc_sta.get_mac())
        sta.add_rssi_measurement(params)
    def get_unassociated_station_by_mac(self, mac: str) -> UnassociatedStation:
        """Get the unassociated Station object whose MAC is 'mac'

        Args:
            mac (str): The unassociated STA MAC of interest

        Returns:
            UnassociatedStation: The station if found, otherwise None.
        """
        for station in self.unassociated_stations:
            if station.get_mac() == mac:
                return station
        return None

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
        # Datamodel/ GL-inet bug
        # There will be some links in the datamodel between interfaces of a different media type (Ethernet<>Wireless)
        # When this happens, mark both interfaces as the same media type.
        if self.params["wireless"] and not interface.params["wireless"]:
            interface.params["MediaTypeString"] = self.params["MediaTypeString"]
            interface.params["wired"] = self.params["wired"]
            interface.params["wireless"] = self.params["wireless"]
        elif interface.params["wireless"] and not self.params["wireless"]:
            self.params["MediaTypeString"] = interface.params["MediaTypeString"]
            self.params["wired"] = interface.params["wired"]
            self.params["wireless"] = interface.params["wireless"]
        self.children.append(interface)
        self.params[self.children_key].append(interface.params)
        # Sort children by ID
        self.children.sort(key=lambda n: n.params["MACAddress"])
        self.params[self.children_key].sort(key=lambda n: n["MACAddress"])
    def get_children(self):
        return self.children
    def is_child(self, macAddress) -> bool:
        for iface in self.children:
            if iface.params["MACAddress"] == macAddress:
                return True
        return False
    def set_parent_agent(self, agent) -> None:
        self.parentAgent = agent
    def get_parent_agent(self):
        return self.parentAgent
    def get_interface_number(self):
        return self.path[-2::][0]
    def get_hash_id(self) -> str:
        return hashlib.md5(self.path.encode()).hexdigest()


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
    def is_child(self, macAddress):
        is_child = False
        for i in self.interfaces:
            if i.is_child(macAddress):
                is_child = True
        return is_child
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
        def compare_interface_horizontal_coordinates(interface: Interface):
            x_coord = self.x
            if interface.get_children():
                x_coord = interface.get_children()[0].get_parent_agent().x
            return x_coord
        self.interfaces.sort(key=compare_interface_horizontal_coordinates)
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