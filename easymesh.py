from typing import List

class Station():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
    def get_mac(self) -> str:
        if 'MACAddress' in self.params:
            return self.params['MACAddress']
        return ''

class BSS():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.connected_stations: List[Station] = []
    def add_connected_station(self, station) -> None:
        self.connected_stations.append(station)
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
    def add_bss(self, bss) -> None:
        self.bsses.append(bss)
    def get_ruid(self) -> str:
        if 'ID' in self.params:
            return self.params['ID']
        return ''
    def get_bsses(self) -> List[BSS]:
        return self.bsses

class Agent():
    def __init__(self, path, params) -> None:
        self.path = path
        self.params = params
        self.radios: List[Radio] = []
    def add_radio(self, radio) -> None:
        self.radios.append(radio)
    def get_id(self) -> str:
        if 'ID' in self.params:
            return self.params['ID']
        return ''
    def get_radios(self) -> List[Radio]:
        return self.radios
    def num_radios(self) -> int:
        return len(self.radios)