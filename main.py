import json
import logging
import queue
import re
import threading
from enum import Enum
from pprint import pformat, pprint
from textwrap import dedent as d
from time import sleep
from typing import List

import networkx as nx
import plotly.graph_objs as go
import requests
from dash import Dash, Input, Output, State, dcc, html

from easymesh import BSS, Agent, Radio, Station
from topology import Topology

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = Dash(__name__, external_stylesheets=external_stylesheets)
app.title = 'CableLabs EasyMesh Network Monitor'

class NodeType(Enum):
    UNKNOWN = 0
    STATION = 1
    AGENT = 2


point_number_to_obj = {}

def gen_node_text(topology: Topology, node_id: str, node_type: NodeType):
    # TODO: This will need some massaging for VBSS.
    station_fmt = "Station: MAC: {} ConnectedTo: {}"
    agent_fmt = "Agent: Model: {} NumRadios: {}"
    if node_type == NodeType.STATION:
        station_obj = topology.get_sta_by_mac(node_id)
        if not station_obj:
            return "Station"
        return station_fmt.format(station_obj.get_mac(), topology.get_bssid_connection_for_sta(station_obj.get_mac()))
    elif node_type == NodeType.AGENT:
        agent_obj = topology.get_agent_by_id(node_id)
        if not agent_obj:
            return "Agent"
        return agent_fmt.format(agent_obj.get_manufacturer(), agent_obj.num_radios())
    else:
        return "Unknown! This shouldn't happen."

# Create topology graph of known easymesh entities.
# Nodes indexed via MAC, since that's effectively a uuid, or a unique  graph key.
def network_graph(topology: Topology):
    point = 0
    G = nx.Graph()
    for sta in topology.get_stations():
        sta_mac = sta.get_mac()
        logging.debug(f"Adding STA node with MAC {sta_mac}")
        point_number_to_obj[point] = sta
        point = point + 1
        G.add_node(sta_mac)
        G.nodes()[sta_mac]['params'] = sta.params
        G.nodes()[sta_mac]['type'] = NodeType.STATION
    for agent in topology.get_agents():
        a_id = agent.get_id()
        point_number_to_obj[point] = agent
        point = point + 1
        logging.debug(f"Adding Agent node with id {a_id}")
        G.add_node(a_id)
        G.nodes()[a_id]['params'] = agent.params
        G.nodes[a_id]['IsController'] = (a_id == g_controller_id)
        G.nodes()[a_id]['type'] = NodeType.AGENT
    for connection in topology.get_connections():
        bssid, station_mac = connection
        logging.debug(f"Adding a graph edge between STA {station_mac} and BSSID {bssid}")
        agent_from_bssid = topology.get_agent_id_from_bssid(bssid)
        G.add_edge(agent_from_bssid, station_mac)
    pos = nx.drawing.layout.spring_layout(G)
    for node in G.nodes:
        G.nodes[node]['pos'] = list(pos[node])
    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = G.nodes[edge[0]]['pos']
        x1, y1 = G.nodes[edge[1]]['pos']
        edge_x.append(x0)
        edge_x.append(x1)
        edge_x.append(None)
        edge_y.append(y0)
        edge_y.append(y1)
        edge_y.append(None)

    edge_trace = go.Scatter(
        x=edge_x, y=edge_y,
        line=dict(width=0.9, color='#888'),
        hoverinfo='none',
        mode='lines')

    node_x = []
    node_y = []
    node_labels = []
    node_hover_text = []
    node_colors = []
    node_sizes = []
    # Add visual node metadata
    for node in G.nodes():
        x, y = G.nodes[node]['pos']
        node_x.append(x)
        node_y.append(y)
        node_labels.append(node)
        node_hover_text.append(gen_node_text(g_Topology, node, G.nodes()[node]['type']))
        if G.nodes()[node]['type'] == NodeType.AGENT:
            node_colors.append('green')
            if G.nodes()[node]['IsController']:
                node_sizes.append(35)
            else:
                node_sizes.append(30)
        else:
            node_colors.append('red')
            node_sizes.append(20)

    node_trace = go.Scatter(
        x=node_x, y=node_y, text=node_labels,
        hovertext=node_hover_text,
        mode='markers+text',
        hoverinfo='text',
        marker=dict(
            colorscale='Electric',
            reversescale=True,
            color=node_colors,
            size=node_sizes,
            line_width=2))

    fig = go.Figure(data=[edge_trace, node_trace],
                layout=go.Layout(
                    # TODO: height (and width) should probably come from viewport calculation.
                    height=800,
                    titlefont_size=16,
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20,l=5,r=5,t=40),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))
                    )
    return fig


styles = {
    'pre': {
        'border': 'thin lightgrey solid',
        'overflowX': 'scroll'
    }
}
# EasyMesh entities
g_Topology = Topology({})
g_controller_id = ""

# HTML Layout / Components
app.layout = html.Div([
    html.Div([html.H1("EasyMesh Network Topology Graph")],
             className="row",
             style={'textAlign': "center"}),
    html.Div(
        className="row",
        children=[
            html.Div(
                className="two columns",
                children=[
                    html.Div(
                        className="twelve.columns",
                        children=[
                            dcc.Markdown(d("""
                            **EashMesh Network Controller**

                            Input the IP and Port of the Controller in the EasyMesh network to visualize.
                            """)),
                            dcc.Input(id="ip_input", type="text", placeholder="192.168.1.1"),
                            dcc.Input(id="port_input", type="text", placeholder="8080"),
                            dcc.Markdown(d("""
                            **HTTP Basic Auth Params**
                            Username and password for the HTTP proxy.
                            """)),
                            dcc.Input(id='httpauth_user', type='text', placeholder='admin'),
                            dcc.Input(id='httpauth_pass', type='text', placeholder='admin'),
                            html.Button('Submit', id='submit-val', n_clicks=0),
                            html.Div(id="output", children='Press Submit to connect')
                        ],
                        style={'height': '300px'}
                    )
                ]
            ),
            html.Div(
                className="eight columns",
                children=[dcc.Graph(id="my-graph",
                                    figure=network_graph(g_Topology), animate=True),
                          dcc.Interval(id='graph-interval', interval=5000, n_intervals=0)],
                style={'height': '1000px'}
            ),
            html.Div(
                className="two columns",
                children=[
                    html.Div(
                        className='twelve columns',
                        children=[
                            dcc.Markdown(d("""
                            **Transition Station**

                            Transition station to new agent.
                            """)),
                            dcc.Dropdown(options=[], id='transition_station', placeholder='Select a station'),
                            dcc.Dropdown(options=[], id='transition_bssid', placeholder='Select a new BSSID.'),
                            dcc.RadioItems(options=['VBSS', 'Client Steering'], id="transition-type-selection", inline=True),
                            dcc.Interval(id='transition-interval', interval=300, n_intervals=0),
                            html.Button('Transition', id='transition-submit', n_clicks=0),
                            html.Div(id="transition-output", children='Press Transition to begin station transition.')
                        ],
                        style={'height': '300px'}),
                    html.Div(
                        className='twelve columns',
                        children=[
                            dcc.Markdown(d("""
                            **Node Data**

                            Click on a node for details.
                            """)),
                            html.Pre(id='node-click', style=styles['pre'])
                        ],
                        style={'height': '400px'})
                ]
            ),
        ]
    )
])

def marshall_nbapi_blob(nbapi_json) -> Topology:
    """Parse a list of NBAPI json entries

    Args:
        nbapi_json (json): NBAPI json response.

    Returns:
        Topology: Topological representation of the parsed data.

    Note:
        This is pretty fragile, and depends on the NBAPI<->HTTP proxy interface not changing.
    """
    # For a topology demo, we really only care about Devices that hold active BSSs (aka Agents)
    # and their connected stations.
    if type(nbapi_json) is not list:
        return Topology({})

    # Don't try to be too clever, here - just do a bunch of passes over the json entries until we're done figuring things out.

    # 0. Find the controller in the network.
    for e in nbapi_json:
        if re.search(r'\.Network\.$', e['path']):
            global g_controller_id
            g_controller_id = e['parameters']['ControllerID']

    # 1. Build the agent list.
    agent_list: List[Agent] = []
    for e in nbapi_json:
        if re.search(r"\.Device\.\d{1,10}\.$", e['path']):
            agent_list.append(Agent(e['path'], e['parameters']))

    # 2. Get Radios, add them to Agents
    for e in nbapi_json:
        if re.search(r"\.Radio\.\d{1,10}\.$", e['path']):
            for agent in agent_list:
                if e['path'].startswith(agent.path):
                    agent.add_radio(Radio(e['path'], e['parameters']))

    # 3. Collect BSSs and map them back to radios.
    for e in nbapi_json:
        if re.search(r"\.BSS\.\d{1,10}\.$", e['path']):
            for agent in agent_list:
                for radio in agent.get_radios():
                    if e['path'].startswith(radio.path):
                        radio.add_bss(BSS(e['path'], e['parameters']))

    # 4. Map Stations to the BSS they're connected to.
    for e in nbapi_json:
        if re.search(r"\.STA\.\d{1,10}\.$", e['path']):
            for agent in agent_list:
                for radio in agent.get_radios():
                    for bss in radio.get_bsses():
                        if e['path'].startswith(bss.path):
                            bss.add_connected_station(Station(e['path'], e['parameters']))
    # DEBUG
    # for i, agent in enumerate(agent_list):
    #     print(f"Agent_{i} ID {agent.get_id()}, {agent.num_radios()} radios.")
    #     for n, radio in enumerate(agent.get_radios()):
    #         print(f"\tRadio_{n} (belonging to device {agent.get_id()} has ruid {radio.get_ruid()}")
    #         for m, bss in enumerate(radio.get_bsses()):
    #             print(f"\t\tRadio (ruid: {radio.get_ruid()}) BSS_{m}: {bss.get_bssid()}")
    #             for o, sta in enumerate(bss.get_connected_stations()):
    #                 print(f"\t\t\tBSS {bss.get_bssid()} connected station: STA_{o}: {sta.get_mac()}")

    # 5. Go for a walk. Go feel the sun. Maybe read a book about recursion.
    return Topology(agent_list)

class HTTPBasicAuthParams():
    def __init__(self, user: str, pw: str) -> None:
        self.user = user
        self.pw = pw
    def __repr__(self) -> str:
        return f"HTTPBasicAuthParams: username: {self.user}, pass: {self.pw}"

data_q_unused = queue.Queue()

class NBAPI_Task(threading.Thread):
    def __init__(self, data_q_unused, ip: str, port: str, cadence_ms: int = 1000, auth_params: HTTPBasicAuthParams = None):
        super().__init__()
        self.data_q = data_q_unused
        self.ip = ip
        self.port = port
        self.cadence_ms = cadence_ms
        self.quitting = False
        if not auth_params:
            self.auth=('admin', 'admin')
        else:
            self.auth=(auth_params.user, auth_params.pw)
    # Override threading.Thread.run(self)->None
    def run(self):
        while not self.quitting:
            url = "http://{}:{}/serviceElements/Device.WiFi.DataElements.".format(self.ip, self.port)
            nbapi_root_request_response = requests.get(url=url, auth=self.auth, timeout=3)
            if not nbapi_root_request_response.ok:
                break
            nbapi_root_json_blob = nbapi_root_request_response.json()
            global g_Topology
            g_Topology = marshall_nbapi_blob(nbapi_root_json_blob)
            sleep(self.cadence_ms // 1000)
    def __repr__(self):
        return f"NBAPI_Task: ip: {self.ip}, port: {self.port}, cadence (mS): {self.cadence_ms}, data_q elements: {len(self.data_q)}"
    def quit(self):
        logging.debug("Hey folks! NBAPI thread here. Time to die!")
        self.quitting = True

nbapi_thread = None

def validate_ipv4(ip: str):
    return re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip)

def validate_port(port: str):
    return re.match(r'^\d{1,5}$', port) and int(port) > 0 and int(port) < 65535

def send_client_steering_request(sta_mac: str, new_bssid: str):
    # ubus call Device.WiFi.DataElements.Network ClientSteering '{"station_mac":"<client_mac>", "target_bssid":"<BSSID>"}'
    json_payload = {"sendresp": True,
                    "commandKey": "",
                    "command": "Device.WiFi.DataElements.Network.ClientSteering",
                    "inputArgs": {"station_mac": sta_mac,
                                  "target_bssid": new_bssid}}
    # TODO: handle IP and ports properly
    url = "http://{}:{}/commands".format("127.0.0.1", "9999")
    # TODO: handle the auth properly
    auth=('admin', 'admin')
    nbapi_root_request_response = requests.post(url=url, auth=auth, timeout=3, json=json_payload)
    # TODO: proper error handling
    logging.info(f"Sent client steering request, cmd={str(json_payload)}")
    if not nbapi_root_request_response.ok:
        logging.error("Something went wrong went sending the steering request\n: {str(nbapi_root_request_response)}")

# Component callbacks
@app.callback(
    Output('output', 'children'),
    Input('submit-val', 'n_clicks'),
    State('ip_input', 'value'),
    State('port_input', 'value'),
    State('httpauth_user', 'value'),
    State('httpauth_pass', 'value')
)
def connect_to_controller(n_clicks: int, ip: str, port: str, httpauth_u: str, httpauth_pw: str):
    if not n_clicks:
        return ""
    logging.debug(f"Request to monitor controller at {ip}:{port}")
    if not validate_ipv4(ip):
        return f"IP address '{ip}' seems malformed. Try again."
    if not validate_port(port):
        return f"Port '{port}' seems malformed. Try again."
    global nbapi_thread
    if nbapi_thread:
        nbapi_thread.quit()
    logging.debug(f"Starting NBAPI task at {ip}:{port}")
    nbapi_thread = NBAPI_Task(data_q_unused, ip, port, 1000, HTTPBasicAuthParams(httpauth_u, httpauth_pw))
    nbapi_thread.start()
    return f"Connected to {ip}:{port}"

@app.callback(Output('my-graph', 'figure'),
              Input('graph-interval', 'n_intervals'))
def update_graph(unused):
    return network_graph(g_Topology)

@app.callback(Output('transition_bssid', 'value'),
              Input('transition-type-selection', 'value'))
def on_transition_type_choice_click(_type):
    return ""

@app.callback(Output('transition_station', 'options'),
              Output('transition_bssid', 'options'),
              Output('transition_bssid', 'placeholder'),
              Input('transition-interval', 'n_intervals'),
              Input('transition-type-selection', 'value'))
def update_transition_dropdown_menus(unused, _type):
    placeholder = 'Select a new BSSID'
    avail_stations = [sta.get_mac() for sta in g_Topology.get_stations()]
    if _type is None or _type == 'Client Steering':
        avail_targets = [bss.get_bssid() for bss in g_Topology.get_bsses()]
    elif _type == 'VBSS':
        avail_targets = [radio.get_ruid() for radio in g_Topology.get_radios()]
        placeholder = 'Select a new RUID'
    return (avail_stations, avail_targets, placeholder)

@app.callback(
    Output('transition-output', 'children'),
    Input('transition-submit', 'n_clicks'),
    State('transition_station', 'value'),
    State('transition_bssid', 'value'),
    State('transition-type-selection', 'value'),
)
def on_transition_click(n_clicks: int, station: str, target_id: str, transition_type: str):
    if not n_clicks:
        return f"Click Transition to begin."
    if not station:
        return f"Select a station."
    if not target_id:
        return f"Select a new target."
    if transition_type == 'VBSS':
        target_type = 'RUID'
        if not g_Topology.validate_vbss_move_request(station, target_id):
            return f"Station {station} is already connected to {target_id}"
    else:
        target_type = 'BSSID'
    logging.debug(f"Sending client steering request (type: {transition_type}) from STA {station} to {target_id}")
    send_client_steering_request(station, target_id)
    return f"Requesting a {transition_type} transition of STA {station} to {target_type} {target_id}"


@app.callback(Output('node-click', 'children'),
              Input('my-graph', 'clickData'))
def node_click(clickData):
    if not clickData:
        return ""
    return json.dumps(point_number_to_obj[clickData['points'][0]['pointNumber']].params, indent=2)

if __name__ == '__main__':
    # Silence imported module logs
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, datefmt='%Y-%m-%d_%H:%M:%S')
    app.run_server(debug=True)
    if nbapi_thread:
        nbapi_thread.quit()
