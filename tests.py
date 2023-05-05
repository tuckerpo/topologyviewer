# pylint: disable=line-too-long, super-with-arguments

"""
This module contains unit tests for the `main`, `validation`, `topology`, `easymesh`, and `path_parser` modules.

The `TopologyParsingTests` class contains two unit tests:
    - `test_output_from_parsing`: Tests that we create sane topology objects from NBAPI json blobs.
    - `test_garbage_input_to_parser`: Ensures we don't create good topologies out of thin air.

The `ValidationTests` class contains six unit tests for input validation:
    - `test_good_ip_address_validation`: Tests validation of valid IPv4 addresses.
    - `test_bad_ip_address_validation`: Tests validation of invalid IPv4 addresses.
    - `test_good_port_validation`: Tests validation of valid port numbers.
    - `test_bad_port_validation`: Tests validation of invalid port numbers.
    - `test_good_mac_validation`: Tests validation of valid MAC addresses.
    - `test_bad_mac_validation`: Tests validation of invalid MAC addresses.

The `VBSSValidationTests` class contains three unit tests for VBSS input validation:
    - `test_good_vbss_client_mac`: Tests validation of valid VBSS client MAC address.
    - `test_good_vbss_password`: Tests validation of a good VBSS password.
    - `test_bad_vbss_password`: Tests validation of a bad VBSS password.

The `PathParserTests` class contains three unit tests for path_parser module:
    - `test_index_lookup`: Tests that we can parse node indices from NBAPI paths.
    - `test_index_lookup_empty_path`: Tests that we can handle bad input.
    - `test_index_lookup_empty_keyword`: Tests that we can handle bad input.

Each test case class inherits from the `unittest.TestCase` class.

This module can be run as a script to execute all unit tests using the `unittest.main()` method.
"""

import unittest
import json
from main import marshall_nbapi_blob
import validation
from topology import Topology
from easymesh import Agent, Station
from path_parser import parse_index_from_path_by_key
class TopologyParsingTests(unittest.TestCase):
    """
    Unit tests for the `marshall_nbapi_blob` function that converts JSON blobs obtained from the NBAPI into
    `Topology` objects. This class is a subclass of the `unittest.TestCase` class, and each test method defined
    in this class is run as an individual test case.

    Attributes:
        None

    Methods:
        test_output_from_parsing: Test that the `marshall_nbapi_blob` function creates sane topology objects from
            NBAPI JSON blobs. It loads a JSON blob from a file, converts it to a `Topology` object, and checks that
            the object contains the expected number of stations and connections.

        test_garbage_input_to_parser: Test that the `marshall_nbapi_blob` function does not create valid topology
            objects from invalid JSON input. It passes an invalid JSON string to the function and checks that the
            resulting `Topology` object has no connections.
    """
    def __init__(self, *args, **kwargs):
        super(TopologyParsingTests, self).__init__(*args, **kwargs)
    def test_output_from_parsing(self):
        """Test that we create sane topology objects from NBAPI json blobs.
        """
        with open('files/two_stations.json', 'r', encoding='utf-8') as file:
            nbapi_two_stations_json = json.load(file)
        topology = marshall_nbapi_blob(nbapi_two_stations_json)
        self.assertEqual(topology.get_num_stations_total(), 2, "Should have found two stations.")
        self.assertEqual(topology.get_num_connections_total(), 2, "Should have found two connections between the stations and the agent.")
        self.assertEqual(len(topology.agents), 1, "Should have found an agent.")

    def test_garbage_input_to_parser(self):
        """Ensure we don't create good topologies out of thin air.
        """
        topology = marshall_nbapi_blob("this isnt even json, bozo!")
        self.assertEqual(len(topology.get_connections()), 0, "Somehow built connections from garbage input.")

class ValidationTests(unittest.TestCase):
    """Test suite for input validation code.
    """
    def __init__(self, *args, **kwargs):
        super(ValidationTests, self).__init__(*args, **kwargs)
    def test_good_ip_address_validation(self):
        """Tests that the IP address validation code works on a range of good IPv4 addresses.
        """
        good_ipv4_addrs = ["127.0.0.1", "123.456.789.123", "0.0.0.0", "123.4.5.6"]
        for good_ip in good_ipv4_addrs:
            self.assertTrue(validation.validate_ipv4(good_ip))
    def test_bad_ip_address_validation(self):
        """Tests that the IP address validation code correctly reports invalid IP addresses.
        """
        bad_ipv4_addrs = ["hostname", "-1", "0", "123.123.123.1234"]
        for bad_ip in bad_ipv4_addrs:
            self.assertFalse(validation.validate_ipv4(bad_ip))
    def test_good_port_validation(self):
        """Tests that the port validation code works on a range of good port numbers.
        """
        good_ports = ["8080", "1", "45"]
        for good_port in good_ports:
            self.assertTrue(validation.validate_port(good_port))
    def test_bad_port_validation(self):
        """Tests that the port validation code correctly reports invalid port numbers.
        """
        bad_ports = ["99999", "0", "-1"]
        for bad_port in bad_ports:
            self.assertFalse(validation.validate_port(bad_port))
    def test_good_mac_validation(self):
        """Tests that the MAC address validation code works for a range of good MAC addresses.
        """
        good_macs = ["aa:bb:cc:dd:ee:ff", "ab:cd:ef:ab:cd:ef", "12:12:12:12:12:12"]
        for good_mac in good_macs:
            self.assertTrue(validation.validate_mac(good_mac))
    def test_bad_mac_validation(self):
        """Tests that the validation module correctly reports invalid MAC addresses.
        """
        bad_macs = ["hi", "this_isnt_a_mac", "aab:cc:dd:ee:ff"]
        for bad_mac in bad_macs:
            self.assertFalse(validation.validate_mac(bad_mac))

class VBSSValidationTests(unittest.TestCase):
    """Unit tests for VBSS input validation
    """
    def __init__(self, *args, **kwargs):
        super(VBSSValidationTests, self).__init__(*args, **kwargs)
        self.client_mac = "123.123.123.123"
        self.agents = []
    def test_good_vbss_client_mac(self):
        """Tests that client validation on the network works.
        i.e. we correctly know which stations are connected to which agents.
        """
        agent_params = {}
        agents = []
        the_agent = Agent("path", agent_params)
        sta_params = {"MACAddress": self.client_mac}
        the_sta = Station("path", sta_params)
        the_agent.add_connected_station(the_sta)
        self.agents.append(the_agent)
        network_topology =  Topology(agents, "TestTopologyController")
        self.assertTrue(validation.validate_vbss_client_mac(self.client_mac, network_topology))
    def test_good_vbss_password(self):
        """Tests VBSS password validation for a good password for VBSS moves.
        """
        self.assertTrue(validation.validate_vbss_password_for_creation("password"))
    def test_bad_vbss_password(self):
        """Tests VBSS password validation for a bad password for VBSS moves.
        """
        error, err_string = validation.validate_vbss_password_for_creation("badpw")
        self.assertFalse(error)
        self.assertTrue(len(err_string) > 0)

class PathParserTests(unittest.TestCase):
    """Unit tests for path_parser module
    """
    def __init__(self, *args, **kwargs):
        super(PathParserTests, self).__init__(*args, **kwargs)
    def test_index_lookup(self):
        """Test that we can parse node indeces from NBAPI paths
        """
        path_prefix = "Device.WiFi.DataElements.Network."
        device_suffix = "Device.5."
        self.assertEqual(parse_index_from_path_by_key(path_prefix+device_suffix, "Device"), "5")
    def test_index_lookup_empty_path(self):
        """Test that we can handle bad input
        """
        self.assertEqual(parse_index_from_path_by_key("", "Radio"), "")
    def test_index_lookup_empty_keyword(self):
        """Test that we can handle bad input
        """
        self.assertEqual(parse_index_from_path_by_key("Device.WiFi.", ""), "")

if __name__ == '__main__':
    unittest.main()
