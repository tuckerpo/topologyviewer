import unittest
import json
from main import marshall_nbapi_blob

class TopologyParsingTests(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(TopologyParsingTests, self).__init__(*args, **kwargs)
    def test_output_from_parsing(self):
        """Test that we create sane topology objects from NBAPI json blobs.
        """
        with open('files/two_stations.json', 'r') as file:
            nbapi_two_stations_json = json.load(file)
        topology = marshall_nbapi_blob(nbapi_two_stations_json)
        self.assertEqual(len(topology.stations.keys()), 2, "Should have found two stations.")
        self.assertEqual(len(topology.get_connections()), 2, "Should have found two connections between the stations and the agent.")
        self.assertEqual(len(topology.agents), 1, "Should have found an agent.")

    def test_garbage_input_to_parser(self):
        """Ensure we don't create good topologies out of thin air.
        """
        topology = marshall_nbapi_blob("this isnt even json, bozo!")
        self.assertEqual(len(topology.get_connections()), 0, "Somehow built connections from garbage input.")

if __name__ == '__main__':
    unittest.main()