# pylint: disable=logging-fstring-interpolation

"""Module for holding persistent data coming from the NBAPI.
Any given HTTP request to the NBAPI HTTP proxy will yield an instantaneous view of the network.

There are some features that require a history of the network, such as stations moving and signal
strength plotting.
"""
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

# List of stations that have undergone a move (radio to radio, or BSS to BSS)
g_StationsThatHaveMoved: List[str] = []

# Map of station MAC address to it's currently connected radio UID
g_StationsToRadio: Dict[str, str] = {}

# Maps Radio UID to dict key'd by station MACs, value = list of RSSI measurements made on RUID
# RUID -> STA MAC -> [RSSI Measurements]
g_RSSI_Measurements: Dict[str, Dict[str, List[int]]] = {}

def handle_station_has_moved(sta_mac: str, ruid: str) -> None:
    """Handler for a station move event.

    Args:
        sta (Station): The station that has moved.
    """
    logging.debug(f"Station {sta_mac} has moved to {ruid}")
    g_StationsThatHaveMoved.append(sta_mac)
    if sta_mac in g_StationsToRadio:
        del g_StationsToRadio[sta_mac]

def get_stations_that_have_moved() -> List[str]:
    """Get the list of all stations that have moved.

    Returns:
        List[str]: The station MACs that have moved
    """
    # Make a copy so caller cannot manipulate the global data.
    stations_that_have_moved: List[str] = g_StationsThatHaveMoved
    return stations_that_have_moved

def get_did_station_move(sta_mac: str) -> bool:
    """Whether or not a station has moved.

    Args:
        sta_mac (str): The station of interest.

    Returns:
        bool: True if `sta_mac` has moved, false otherwise.
    """
    did_station_move: bool = False
    if sta_mac in get_stations_that_have_moved():
        did_station_move = True
        g_StationsThatHaveMoved.remove(sta_mac)
    return did_station_move

def station_has_undergone_move(sta_mac: str, ruid: str) -> bool:
    """Determines whether a given station has undergone a move or not.

    Args:
        sta (Station): The station of interest.

    Returns:
        bool: True if `sta` has moved, false otherwise.
    """
    return sta_mac in g_StationsToRadio and g_StationsToRadio[sta_mac] != ruid

def register_station_to_radio(sta_mac: str, ruid: str) -> None:
    """Register that a station is associated to a given radio, for tracking moves.

    Args:
        sta_mac (str): The station.
        ruid (str): The radio `sta_mac` is connected to.
    """
    g_StationsToRadio[sta_mac] = ruid

def add_new_signal_strength_measurement(sta_mac: str, ruid: str, rssi: int) -> None:
    """Adds a new RSSI measurement for a given station `sta_mac` made on radio `ruid`

    Args:
        sta_mac (str): The station that the measurement was made for.
        ruid (str): The radio the measurement was made on
        rssi (int): The RSSI of the measurement.
    """
    if ruid not in g_RSSI_Measurements:
        g_RSSI_Measurements[ruid] = {}
    if sta_mac not in g_RSSI_Measurements[ruid]:
        g_RSSI_Measurements[ruid][sta_mac] = []
    g_RSSI_Measurements[ruid][sta_mac].append(rssi)

def clear_all_signal_strength_measurements() -> None:
    """Remove all signal strength measurement history.
    Useful for changing connection contexts.
    """
    g_RSSI_Measurements.clear()

def get_rssi_measurements() -> Dict[str, Dict[str, List[int]]]:
    """Get all of the RSSI measurements made in the topology.

    Returns:
        Dict[str, Dict[str, List[int]]]: RUID -> STA_MAC -> [RSSI Measurements]
    """
    # Return a copy so caller can't mutate data.
    measurements_copy: Dict[str, Dict[str, List[int]]] = g_RSSI_Measurements
    return measurements_copy
