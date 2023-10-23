# pylint: disable=line-too-long, invalid-name, too-many-instance-attributes, too-few-public-methods, too-many-arguments

"""
This module defines a set of classes to represent WiFi networks, devices and measurements.

Classes:
- Station: Represents a client or an access point connected to a WiFi network.
- BSS: Represents a Basic Service Set (BSS), which is a set of stations controlled by a single access point.
- UnassociatedStation: Represents a WiFi client that is not connected to any access point.
- UnassociatedStationRSSIMeasurement: Represents a measurement of signal strength from an unassociated station.
- Radio: Represents a WiFi radio that is capable of transmitting and receiving WiFi signals.

Enums:
- ORIENTATION: Represents the orientation of an object in 2D space.

Constants:
- mediaType_to_str: A dictionary that maps WiFi media types to their string representations.

Functions:
None

Note: The module requires Python 3.7 or higher.
"""

from typing import List
from enum import Enum
import hashlib

mediaType_to_str = dict([
    (0x0, 'Fast Ethernet'),
    ("IEEE_802_3AB_GIGABIT_ETHERNET", 'Gigabit Ethernet'),
    (0x100, 'B 2.4GHz'),
    (0x101, 'G 2.4GHz'),
    (0x102, 'A 5 GHz'),
    ("IEEE_802_11N_2_4_GHZ", 'N 2.4 GHz'),
    (0x104, 'N 5 GHz'),
    ("IEEE_802_11AX", 'AC 5 GHz'),
    (0x106, 'AD 60 GHz'),
    (0x107, 'AF'),
    (0x108, 'AX'),
    (0x200, 'IEEE_1901_WAVELET'),
    (0x201, 'IEEE_1901_FFT'),
    (0x300, 'MOCA_V1_1'),
    (0xffff, 'UNKNOWN_MEDIA')])

# mediaType_to_str = dict([
#     (0x0, 'Fast Ethernet'),
#     (0x1, 'Gigabit Ethernet'),
#     (0x100, 'B 2.4GHz'),
#     (0x101, 'G 2.4GHz'),
#     (0x102, 'A 5 GHz'),
#     (0x103, 'N 2.4 GHz'),
#     (0x104, 'N 5 GHz'),
#     (0x105, 'AC 5 GHz'),
#     (0x106, 'AD 60 GHz'),
#     (0x107, 'AF'),
#     (0x108, 'AX'),
#     (0x200, 'IEEE_1901_WAVELET'),
#     (0x201, 'IEEE_1901_FFT'),
#     (0x300, 'MOCA_V1_1'),
#     (0xffff, 'UNKNOWN_MEDIA')])

class ORIENTATION(Enum):
    """Orientation of a given EasyMesh node in cartesian space.
    """
    RIGHT = 0
    UP = 1
    DOWN = 2

class Station():
    """Class representing a Wi-Fi EasyMesh station.
    """
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.x = 0
        self.y = 0
        self.is_steered = False

    def get_mac(self) -> str:
        """Get this station's MAC address

        Returns:
            str: The MAC address of this station.
        """
        if 'MACAddress' in self.params:
            return self.params['MACAddress']
        return ''

    def get_hash_mac(self) -> str:
        """Get the MD5 hash of this station's MAC address

        Returns:
            str: The MD5 hash of this station's MAC address.
        """
        return hashlib.md5(self.get_mac().encode()).hexdigest()

    def get_steered(self) -> bool:
        """Has this station been steered?

        Returns:
            bool: True if steered, False otherwise.
        """
        return self.is_steered

    def set_steered(self, steered: bool) -> None:
        """Set whether or not this station has been steered.

        Args:
            steered (bool): True if steered, False if not.
        """
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
        if 'SignalStrength' in self.params:
            return self.params['SignalStrength']
        if 'RCPI' in self.params:
            return self.params['RCPI']
        # Return -INT8_MAX, assuming dBm
        return -127

class BSS():
    """Represents a Wi-Fi EasyMesh Basic Service Set
    """
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.interface = {}
        self.connected_stations: List[Station] = []
        self.connected_sta_key = 'STA(s)'
        self.params[self.connected_sta_key] = []

    def add_connected_station(self, station) -> None:
        """Adds a station to this BSS's list of connected stations.

        Args:
            station (Station): The station.
        """
        self.connected_stations.append(station)
        self.params[self.connected_sta_key].append(station.params)

    def get_num_connected_stations(self) -> int:
        """Returns the number of stations connected to this BSS.

        Returns:
            int: The number of stations connected to this BSS.
        """
        return len(self.connected_stations)

    def get_connected_stations(self) -> List[Station]:
        """Return the list of connected stations.

        Returns:
            List[Station]: The list of stations connected to this BSS.
        """
        return self.connected_stations

    def get_bssid(self) -> str:
        """Get this BSS's BSSID.

        Returns:
            str: The BSSID.
        """
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
    """Represents a Wi-Fi EasyMesh Unassociated STA Link Metrics Response payload.
    """
    def __init__(self, station: str, signal_strength: int, channel_number: int, timestamp: int, ruid: str):
        self.station = station
        self.signal_strength = signal_strength
        self.channel_number = channel_number
        self.timestamp = timestamp
        self.ruid = ruid

    def get_signal_strength(self) -> int:
        """Get the signal strength of this unassociated station RSSI measurement.

        Returns:
            int: The signal strength, in dBm
        """
        return self.signal_strength

    def get_channel_number(self) -> int:
        """Get the channel number this measurement was made on.
        """
        return self.channel_number

    def get_parent_ruid(self) -> str:
        """The ruid of the Radio that saw this measurement.


        Returns:
            str: The RUID
        """
        return self.ruid

    def get_timestamp(self) -> int:
        """Get the timestamp of this measurement. The timestamp is defined in the EasyMesh spec
        as the time delta between the Agent requesting link metrics of a radio, and the radio
        responding.

        Returns:
            int: The timestamp of this measurement.
        """
        return self.timestamp

class UnassociatedStation():
    """Represents a Wi-Fi EasyMesh unassociated station.
    """
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.rssi_measurements: List[UnassociatedStationRSSIMeasurement] = []
        self.parent_radio = None

    def get_mac(self) -> str:
        """Get this unassociated station's MAC address.

        Returns:
            str: The MAC address of this unassociated station.
        """
        if 'MACAddress' in self.params:
            return self.params['MACAddress']
        return ''

    def set_parent_radio(self, radio) -> None:
        """Set the parent radio of this unassociated station. A parent radio is one which can
        hear this station even though it is unassociated.

        Args:
            radio (Radio): The parent radio of this unassociated station.
        """
        self.parent_radio = radio

    def add_rssi_measurement(self, params) -> None:
        """Adds a link metrics measurement to this unassociated station object.

        Args:
            params (Dict[str]): The link metrics payload.
        """
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
        """Get the list of this unassociated stations link metrics measurements.

        Returns:
            List[UnassociatedStationRSSIMeasurement]: The list of link metrics measurements made for this station by it's parent radio.
        """
        return self.rssi_measurements

    def get_parent_radio(self):
        """Get the radio making unassociated link metrics measurements for this unassociated station.

        Returns:
            Radio: The parent Radio.
        """
        return self.parent_radio

class Radio():
    """Represents a Wi-Fi EasyMesh radio.
    """
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.bsses: List[BSS] = []
        self.bss_key = 'BSS'
        self.params[self.bss_key] = []
        self.unassociated_stations: List[UnassociatedStation] = []

    def add_bss(self, bss) -> None:
        """Add a BSS to this radio's BSS list.

        Args:
            bss (BSS): The BSS to add.
        """
        self.bsses.append(bss)
        self.params[self.bss_key].append(bss.params)

    def get_ruid(self) -> str:
        """Get the RUID of this radio.

        Returns:
            str: The RUID.
        """
        if 'ID' in self.params:
            return self.params['ID']
        return ''

    def get_bsses(self) -> List[BSS]:
        """Returns all BSSes on this radio.

        Returns:
            List[BSS]: A list of BSS objects.
        """
        return self.bsses

    def get_unassociated_stations(self) -> List[UnassociatedStation]:
        """Returns all unassociated stations this radio is listening to.

        Returns:
            List[UnassociatedStation]: A list of unassociated station objects.
        """
        return self.unassociated_stations

    def add_unassociated_station(self, station: UnassociatedStation) -> None:
        """Adds an unassociated station to this radio's list.

        Args:
            station (UnassociatedStation): The unassociated station to add.
        """
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
            raise ValueError(f"Unknown station: {sta.get_mac()}")
        return station.get_rssi()

    def update_unassociated_sta(self, unassoc_sta: UnassociatedStation, params) -> None:
        """Updates an unassociated station's list of link metrics measurements.

        Args:
            unassoc_sta (UnassociatedStation): The unassociated station to update.
            params (Dict[str]): The link metrics payload.
        """
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
    """Represents a Wi-Fi EasyMesh neighbor.
    """
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params

class Interface():
    """Represents a Wi-Fi EasyMesh interface object (PHY layer)
    """
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
        #self.params["MediaTypeString"] = "Unk" #mediaType_to_str[self.params["MediaType"]]
        self.x = 0
        self.y = 0
        self.orientation = ORIENTATION.RIGHT

        if self.params["MediaType"] in mediaType_to_str:
            self.params["MediaTypeString"] = mediaType_to_str[self.params["MediaType"]]
        else:
            self.params["MediaTypeString"] = "Unknown"

        if self.params["MediaType"] in ["IEEE_802_11N_2_4_GHZ", "IEEE_802_11AX"]:
            self.params["wired"] = 0 #self.params["MediaType"]==0x0 or self.params["MediaType"]==0x1
            self.params["wireless"] = 1 #self.params["MediaType"]>0x1 and self.params["MediaType"]<0x200
        else:
            self.params["wired"] = 1
            self.params["wireless"] = 0


    def add_connected_station(self, station) -> None:
        """Adds a station to this interface's list of connected stations.

        Args:
            station (Station): The station to add.
        """
        self.parentAgent.add_connected_station(station)
        self.connected_stations.append(station)
        self.params[self.connected_sta_key].append(station.params)

    def get_connected_stations(self) -> List[Station]:
        """Get the list of stations connected to this interface.

        Returns:
            List[Station]: List of station objects.
        """
        return self.connected_stations

    def add_neighbor(self, neighbor) -> None:
        """Adds a neighbor interface to this interface object.

        Args:
            neighbor (Interface): The neighbor interface to add.
        """
        self.neighbors.append(neighbor)
        self.params[self.neighbors_key].append(neighbor.params)
        # Sort neighbors by ID
        self.neighbors.sort(key=lambda n: n.params["ID"])
        self.params[self.neighbors_key].sort(key=lambda n: n["ID"])

    def get_neighbors(self) -> List[Neighbor]:
        """Get all neighbors of this interface.

        Returns:
            List[Neighbor]: A list of interface objects.
        """
        return self.neighbors

    def add_child(self, interface) -> None:
        """Add a child interface to this interface object.

        Args:
            interface (Interface): The child interface of this interface object.
        """
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
        """Get all child interfaces of this interface.

        Returns:
            List[Interface]: A list of interface objects.
        """
        return self.children

    def is_child(self, macAddress) -> bool:
        """Check if a given interface is a child of this interface, by MAC address.

        Args:
            macAddress (str): The MAC address of the interface to check child-ness for.

        Returns:
            bool: True if the interface key'd by macAddress is a child of this interface, False otherwise.
        """
        for iface in self.children:
            if iface.params["MACAddress"] == macAddress:
                return True
        return False

    def set_parent_agent(self, agent) -> None:
        """Sets the parent Agent of this interface object.

        Args:
            agent (Agent): The parent Agent that this interface belongs to.
        """
        self.parentAgent = agent

    def get_parent_agent(self):
        """Get this interface's owning parent Agent

        Returns:
            Agent: The parent Agent of this interface.
        """
        return self.parentAgent

    def get_interface_number(self):
        """Gets this interface's interface number. 0...n for n many interfaces on any Agent.

        Returns:
            str: The interface number.
        """
        return self.path[-2::][0]

    def get_hash_id(self) -> str:
        """Get the MD5 hash of this interface object. Hashes it's path member.

        Returns:
            str: The MD5 hash of this interface object.
        """
        return hashlib.md5(self.path.encode()).hexdigest()

    def get_mac(self) -> str:
        """Get this interface's MAC address

        Returns:
            str: The MAC address of this interface.
        """
        return self.params['MACAddress']

    def has_child_iface(self, mac: str) -> bool:
        """Walk this interface's children looking for a child interface key'd by `mac`

        Args:
            mac (str): The MAC address to check.

        Returns:
            bool: True if any interface with MAC address `mac` is a child of this interface, False otherwise.
        """
        for child_iface in self.children:
            if child_iface.get_mac() == mac:
                return True
        return False


class Agent():
    """Class representing a Wi-Fi EasyMesh Agent.
    """
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
        """Add a child to this Agent.

        Args:
            agent (Agent): The child of this agent.
        """
        self.children.append(agent)
        # Sort children by ID
        self.children.sort(key=lambda n: n.get_id())

    def get_children(self):
        """Get this Agent's list of child Agent's.

        Returns:
            List[Agent]: A list of child Agent objects.
        """
        return self.children

    def is_child(self, macAddress):
        """Check if there's any Agent with MAC address `macAddress` in this Agent's children list.

        Args:
            macAddress (str): The MAC address of the Agent to check child-ness for.

        Returns:
            bool: True if there's any Agent with MAC address `macAddress` in this Agent's children list, False otherwise.
        """
        is_child = False
        for i in self.interfaces:
            if i.is_child(macAddress):
                is_child = True
        return is_child

    def num_children(self):
        """Return the total number of interfaces and stations for this Agent.

        Returns:
            int: The total number of interfaces and stations for this Agent.
        """
        return len(self.get_interfaces()) + len(self.get_connected_stations())

    def add_radio(self, radio) -> None:
        """Add a radio object to this Agent.

        Args:
            radio (Radio): The radio to add.
        """
        self.radios.append(radio)
        self.params[self.radios_key].append(radio.params)

    def add_interface(self, interface) -> None:
        """Add an interface to this Agent.

        Args:
            interface (Interface): The interface to add.
        """
        self.interfaces.append(interface)
        self.params[self.interfaces_key].append(interface.params)
        self.interfaces.sort(key=lambda n: n.params["wired"])

    def sort_interfaces(self) -> None:
        """Sort interfaces by their cartesian coordinates.
        """
        def compare_interface_horizontal_coordinates(interface: Interface):
            x_coord = self.x
            if interface.get_children():
                x_coord = interface.get_children()[0].get_parent_agent().x
            return x_coord
        self.interfaces.sort(key=compare_interface_horizontal_coordinates)

    def add_connected_station(self, station) -> None:
        """Add a connected station to this Agent.

        Args:
            station (Station): The station to add.
        """
        self.connected_stations.append(station)

    def get_connected_stations(self) -> List[Station]:
        """Get all stations connected to some interface on this Agent.

        Returns:
            List[Station]: A list of station objects.
        """
        return self.connected_stations

    def get_id(self) -> str:
        """Get this Agent's ID (MAC address)

        Returns:
            str: This Agent's ID.
        """
        if 'ID' in self.params:
            return self.params['ID']
        return ''

    def get_hash_id(self) -> str:
        """Get the MD5 hash of this Agent's ID

        Returns:
            str: The MD5 hash of this Agent's ID
        """
        return hashlib.md5(self.get_id().encode()).hexdigest()

    def get_radios(self) -> List[Radio]:
        """Get all radios hosted on this Agent.

        Returns:
            List[Radio]: A list of radios.
        """
        return self.radios

    def get_interfaces(self) -> List[Interface]:
        """Get all interfaces on this Agent, regardless of PHY type.

        Returns:
            List[Interface]: A list of interface objects.
        """
        return self.interfaces

    def num_radios(self) -> int:
        """Get the number of radios hosted on this Agent.

        Returns:
            int: The number of radios hosted on this Agent.
        """
        return len(self.radios)

    def get_manufacturer(self) -> str:
        """Get the manufacturer of this Agent.

        Returns:
            str: The manufacturer name of this physical Agent.
        """
        if 'ManufacturerModel' in self.params:
            return self.params['ManufacturerModel']
        return ''

    def get_interfaces_by_orientation(self, orientation: ORIENTATION) -> List[Interface]:
        """Get a list of interfaces on this Agent by their orientation.

        Args:
            orientation (ORIENTATION): The orientation of interest.

        Returns:
            List[Interface]: A list of interfaces who have orientation `orientation`
        """
        interfaces = []
        for i in self.interfaces:
            if i.orientation == orientation:
                interfaces.append(i)
        return interfaces
