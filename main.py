import json
import logging
import re
import threading
from enum import Enum
from pprint import pformat, pprint
from textwrap import dedent as d
from time import sleep
from typing import List

import networkx as nx
from networkx.drawing.nx_pydot import graphviz_layout
import plotly.graph_objs as go
import requests
from dash import Dash, Input, Output, State, dcc, html

from easymesh import BSS, Agent, Radio, Station, Interface, Neighbor, ORIENTATION
from topology import Topology

app = Dash(__name__)
app.title = 'CableLabs EasyMesh Network Monitor'

class NodeType(Enum):
    UNKNOWN = 0
    STATION = 1
    AGENT = 2
    CONTROLLER = 3


#point_number_to_obj = {}
#point = 0
marker_references = [] # Used in the click callback to find the node clicked on

def gen_node_text(topology: Topology, node_id: str, node_type: NodeType):
    # TODO: This will need some massaging for VBSS.
    station_fmt = "Station: MAC: {} ConnectedTo: {}"
    agent_fmt = "Agent: Model: {} NumRadios: {}"
    if node_type == NodeType.STATION:
        station_obj = topology.get_station_from_hash(node_id)
        if not station_obj:
            return "Station"
        return station_fmt.format(station_obj.get_mac(), topology.get_bssid_connection_for_sta(station_obj.get_mac()))
    elif node_type == NodeType.AGENT or node_type == NodeType.CONTROLLER:
        agent_obj = topology.get_agent_from_hash(node_id)
        if not agent_obj:
            return "Agent"
        return agent_fmt.format(agent_obj.get_manufacturer(), agent_obj.num_radios())
    else:
        return "Unknown! This shouldn't happen."

def add_children_to_graph_recursive(agent: Agent, graph):
    global point
    for child in agent.get_children():
        marker_references.append(child.get_hash_id())
        graph.add_node(child.get_hash_id())
        graph.nodes()[child.get_hash_id()]['type'] = NodeType.AGENT
        #graph.nodes()[child.get_hash_id()]['params'] = child.params
        add_children_to_graph_recursive(child, graph)
    
    for sta in agent.get_connected_stations():
        marker_references.append(sta.get_hash_mac())
        graph.add_node(sta.get_hash_mac())
        graph.nodes()[sta.get_hash_mac()]['type'] = NodeType.STATION
        #graph.nodes()[sta.get_hash_mac()]['params'] = sta.params


def get_iface_markers(agent: Agent):
    x_distance = 10 # Distance between two interface markers
    y_distance = 7
    x_min = 18      # Distance between the agent marker and the interface marker
    y_min = 8

    node_x = []
    node_y = []
    node_labels = []
    node_hover_text = []
    node_colors = []
    node_sizes = []
    node_symbols = []

    interfaces = agent.get_interfaces_by_orientation(ORIENTATION.UP)
    x0 = agent.x - (len(interfaces)/2)*x_distance
    y0 = agent.y + y_min
    if (len(interfaces)%2) != 0:
        x0 = x0 + x_distance/2
    for i in interfaces:
        i.x = x0
        i.y = y0
        x0 = x0 + x_distance

    interfaces = agent.get_interfaces_by_orientation(ORIENTATION.RIGHT)
    x0 = agent.x + x_min
    y0 = agent.y - (len(interfaces)/2)*y_distance
    if (len(interfaces)%2) != 0:
        y0 = y0 + y_distance/2
    else:
        y0 = y0 + y_distance/2
    for i in interfaces:
        i.x = x0
        i.y = y0
        y0 = y0 + y_distance

    interfaces = agent.get_interfaces_by_orientation(ORIENTATION.DOWN)
    x0 = agent.x - (len(interfaces)/2)*x_distance
    y0 = agent.y - y_min
    if (len(interfaces)%2) != 0:
        x0 = x0 + x_distance/2
    for i in interfaces:
        i.x = x0
        i.y = y0
        x0 = x0 + x_distance

    for i in agent.get_interfaces():
        node_x.append(i.x)
        node_y.append(i.y)
        node_labels.append("")
        node_hover_text.append(f'Interface {i.get_interface_number()} with MAC: {i.params["MACAddress"]} and type: {i.params["MediaTypeString"]}')
        node_sizes.append(14)
        node_symbols.append("diamond")
        if i.params["wired"]:
            node_colors.append("red")
        else:
            node_colors.append("blue")

    return {'x': node_x, 'y': node_y, 'node_labels': node_labels, 'node_hover_text': node_hover_text, 'node_colors': node_colors, 'node_sizes': node_sizes, 'node_symbols': node_symbols}

def add_edge_between_interfaces(iface1: Interface, iface_or_station, edge_interfaces_x, edge_interfaces_y):
    edge_interfaces_x.append(iface1.x)
    edge_interfaces_x.append(iface_or_station.x)
    edge_interfaces_x.append(None)
    edge_interfaces_y.append(iface1.y)
    edge_interfaces_y.append(iface_or_station.y)
    edge_interfaces_y.append(None)

# Create topology graph of known easymesh entities.
# Nodes indexed via MAC, since that's effectively a uuid, or a unique  graph key.
def network_graph(topology: Topology):

    layout=go.Layout(
                    # TODO: height (and width) should probably come from viewport calculation.
                    height=800,
                    titlefont_size=16,
                    showlegend=False,
                    hovermode='closest',
                    margin=dict(b=20,l=5,r=5,t=40),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False))


    # Only build graph if controller is found/JSON is marshalled
    if not topology.get_controller():
        return go.Figure(data=[],layout=layout)


    point = 1
    G = nx.Graph()

    marker_references.append(topology.controller.get_hash_id())
    G.add_node(topology.controller.get_hash_id())
    G.nodes()[topology.controller.get_hash_id()]['type'] = NodeType.CONTROLLER
    #G.nodes()[topology.controller.get_hash_id()]['params'] = topology.controller.params
    add_children_to_graph_recursive(topology.controller, G)

    # Get edges/connections of graph
    for agent in topology.agents:
        for ifc in agent.get_interfaces():
            for child in ifc.get_children():
                if not child.get_children():
                    G.add_edge(child.get_parent_agent().get_hash_id(), ifc.get_parent_agent().get_hash_id())
            
            if ifc.get_connected_stations():
                for sta in ifc.get_connected_stations():
                    G.add_edge(sta.get_hash_mac(), ifc.get_parent_agent().get_hash_id())

    pos = graphviz_layout(G, prog="dot")

    for node in G.nodes:
        G.nodes[node]['pos'] = list(pos[node])
        x, y = G.nodes[node]['pos']
        agent = g_Topology.get_agent_from_hash(node)
        if agent:
            agent.x = x
            agent.y = y
        else:
            station = g_Topology.get_station_from_hash(node)
            if station:
                station.x = x
                station.y = y
            
    node_x = []
    node_y = []
    node_labels = []
    node_hover_text = []
    node_colors = []
    node_sizes = []
    node_symbols = []

    # Add visual node metadata
    for node in G.nodes():
        x, y = G.nodes[node]['pos']
        node_x.append(x)
        node_y.append(y)
        node_hover_text.append(gen_node_text(g_Topology, node, G.nodes[node]['type']))
        if G.nodes[node]['type'] == NodeType.CONTROLLER:
            node_sizes.append(52)
            node_symbols.append('circle')
            node_colors.append('#AA29C5')
            node_labels.append("C: " + topology.get_agent_from_hash(node).params["Manufacturer"])
        if G.nodes[node]['type'] == NodeType.AGENT:
            node_sizes.append(45)
            node_symbols.append('circle')
            node_colors.append('green')
            node_labels.append("A: " + topology.get_agent_from_hash(node).params["Manufacturer"])
        if G.nodes[node]['type'] == NodeType.STATION:
            node_sizes.append(35)
            node_symbols.append('circle-open')
            node_colors.append('red')
            node_labels.append(f'STA: {topology.get_station_from_hash(node).params["MACAddress"][-2::]}')# + topology.get_station_from_hash(node).params["mac"])

    node_trace = go.Scatter(
        x=node_x, y=node_y, text=node_labels,
        hovertext=node_hover_text,
        customdata=marker_references,
        mode='markers+text',
        marker_symbol=node_symbols,
        hoverinfo='text',
        marker=dict(
            colorscale='Electric',
            reversescale=True,
            color=node_colors,
            size=node_sizes,
            line_width=2))

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
        line=dict(width=0.05, color='#111'),
        hoverinfo='none',
        mode='lines')

    # Create interface markers
    node_x = []
    node_y = []
    node_labels = []
    node_hover_text = []
    node_colors = []
    node_sizes = []
    node_symbols = []

    # First run generates general coordinates for the interface markers
    for a in g_Topology.get_agents():
        o = get_iface_markers(a)

    # Second run sorts the interfaces horizontally so traces don't cross
    for a in g_Topology.get_agents():
        #a.sort_interfaces()
        o = get_iface_markers(a)
        if not o['x']:
            continue
        node_x.extend(o['x'])
        node_y.extend(o['y'])
        node_labels.extend(o['node_labels'])
        node_hover_text.extend(o['node_hover_text'])
        node_colors.extend(o['node_colors'])
        node_sizes.extend(o['node_sizes'])
        node_symbols.extend(o['node_symbols'])
    
    node_ifaces = go.Scatter(
        x=node_x, y=node_y, text=node_labels,
        hovertext=node_hover_text,
        mode='markers+text',
        marker_symbol=node_symbols,
        hoverinfo='text',
        marker=dict(
            colorscale='Electric',
            reversescale=True,
            color=node_colors,
            size=node_sizes,
            line_width=2))


    edge_interfaces_x = []
    edge_interfaces_y = []

    # Generate edges between interfaces; based on calculated agent coordinates
    for agent in topology.agents:
        for ifc in agent.get_interfaces():
            for child in ifc.get_children():
                if not child.get_children():
                    add_edge_between_interfaces(child, ifc, edge_interfaces_x, edge_interfaces_y)
            
            if ifc.get_connected_stations():
                for sta in ifc.get_connected_stations():
                    add_edge_between_interfaces(ifc, sta, edge_interfaces_x, edge_interfaces_y)

    edge_trace_interfaces = go.Scatter(
        x=edge_interfaces_x, y=edge_interfaces_y,
        line=dict(width=2, color='#111'),
        hoverinfo='none',
        mode='lines')

    fig = go.Figure(data=[edge_trace, node_trace, node_ifaces, edge_trace_interfaces], layout=layout)
    fig.update_traces(textposition='top center', textfont_size=16) # , marker_symbol="diamond")
    fig.update()
    return fig

styles = {
    'pre': {
        'border': 'thin lightgrey solid',
        'overflowX': 'scroll'
    }
}
# EasyMesh entities
g_Topology = Topology({},"")
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
                            dcc.Input(id="ip_input", type="text", placeholder="192.168.1.1", value='192.168.250.171'),
                            dcc.Input(id="port_input", type="text", placeholder="8080", value='8080'),
                            dcc.Markdown(d("""
                            **HTTP Basic Auth Params**
                            Username and password for the HTTP proxy.
                            """)),
                            dcc.Input(id='httpauth_user', type='text', placeholder='admin', value='admin'),
                            dcc.Input(id='httpauth_pass', type='text', placeholder='admin', value='admin'),
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


    # 2. Get Interfaces of each Agent
    interface_list: List[Interface] = []
    for e in nbapi_json:
        if re.search(r"\.Interface\.\d{1,10}\.$", e['path']):
            for agent in agent_list:
                if e['path'].startswith(agent.path):
                    iface = Interface(e['path'], e['parameters'])
                    iface.set_parent_agent(agent)
                    agent.add_interface(iface)
                    interface_list.append(iface)

    # 3. Get Neighbors of each Interface
    controller_backhaul_interface = {}
    controller_agent = {}
    for e in nbapi_json:
        if re.search(r"\.Neighbor\.\d{1,10}\.$", e['path']):
            for agent in agent_list:
                for interface in agent.get_interfaces():
                    if e['path'].startswith(interface.path):
                        interface.add_neighbor(Neighbor(e['path'], e['parameters']))

                        # Mark the backhaul interface of the controller: should be Ethernet type and have at least 1 neighbor
                        if (agent.get_id() == g_controller_id) and (interface.params['MediaType']<=1):
                            controller_backhaul_interface = interface
                            controller_backhaul_interface.orientation = ORIENTATION.DOWN
                            controller_agent = agent

    # Controller has no neighbours yet, mark first ethernet interface as backhaul
    if not controller_backhaul_interface:
        for agent in agent_list:
            if agent.get_id() == g_controller_id:
                    controller_agent = agent
                    for iface in agent.get_interfaces():
                        if iface.params['MediaType']<=1:
                            controller_backhaul_interface = iface
                            controller_backhaul_interface.orientation = ORIENTATION.DOWN
                            break
                    

    # 4. Link interfaces to parents
    for e in nbapi_json:
        if re.search(r"\.MultiAPDevice\.Backhaul\.$", e['path']):
            if e['parameters']['LinkType'] == "None":
                continue

            # Ethernet backhaul connections must always link to the controller
            if e['parameters']['LinkType'] == "Ethernet": 
                # Search for backhaul interface on the device that is getting processed
                for iface in interface_list:
                    if iface.params['MACAddress'] == e['parameters']['MACAddress']:
                        controller_backhaul_interface.add_child(iface)
                        iface.orientation = ORIENTATION.UP
                        controller_agent.add_child(iface.get_parent_agent())


            elif e['parameters']['LinkType'] == "Wi-Fi": 
                for childIface in interface_list:
                    if childIface.params['MACAddress'] == e['parameters']['MACAddress']: # interface on device that is getting processed
                        for parentIface in interface_list:
                            if parentIface.params['MACAddress'] == e['parameters']['BackhaulMACAddress']: # interface on parent device
                                parentIface.add_child(childIface)
                                parentIface.orientation = ORIENTATION.DOWN
                                childIface.orientation = ORIENTATION.UP
                                parentIface.get_parent_agent().add_child(childIface.get_parent_agent())
                                break

    # 5. Get Radios, add them to Agents
    for e in nbapi_json:
        if re.search(r"\.Radio\.\d{1,10}\.$", e['path']):
            for agent in agent_list:
                if e['path'].startswith(agent.path):
                    agent.add_radio(Radio(e['path'], e['parameters']))

    # 6. Collect BSSs and map them back to radios and interfaces
    for e in nbapi_json:
        if re.search(r"\.BSS\.\d{1,10}\.$", e['path']):
            for agent in agent_list:
                for radio in agent.get_radios():
                    if e['path'].startswith(radio.path):
                        bss = BSS(e['path'], e['parameters'])
                        radio.add_bss(bss)
                        for iface in interface_list:
                            if e['parameters']['BSSID'] == iface.params['MACAddress']:
                               bss.interface = iface
                               break
                            
    # 7. Map Stations to the BSS they're connected to.
    for e in nbapi_json:
        if re.search(r"\.STA\.\d{1,10}\.$", e['path']):
            for agent in agent_list:
                for radio in agent.get_radios():
                    for bss in radio.get_bsses():
                        if e['path'].startswith(bss.path):
                            sta = Station(e['path'], e['parameters'])
                            bss.add_connected_station(sta)
                            bss.interface.orientation = ORIENTATION.DOWN
                            bss.interface.add_connected_station(sta)
    # DEBUG
    # for i, agent in enumerate(agent_list):
    #     print(f"Agent_{i} ID {agent.get_id()}, {agent.num_radios()} radios.")
    #     for n, radio in enumerate(agent.get_radios()):
    #         print(f"\tRadio_{n} (belonging to device {agent.get_id()} has ruid {radio.get_ruid()}")
    #         for m, bss in enumerate(radio.get_bsses()):
    #             print(f"\t\tRadio (ruid: {radio.get_ruid()}) BSS_{m}: {bss.get_bssid()}")
    #             for o, sta in enumerate(bss.get_connected_stations()):
    #                 print(f"\t\t\tBSS {bss.get_bssid()} connected station: STA_{o}: {sta.get_mac()}")

    #Connection tree debug
    # def print_conns(agt: Agent):
    #     for ifc in agt.get_interfaces():
    #         for child in ifc.get_children():
    #             if not child.get_children():
    #                 print(f'{child.path.replace("Device.WiFi.DataElements.Network.","")} has backhaul: {ifc.path.replace("Device.WiFi.DataElements.Network.","")}')
    #         if ifc.get_connected_stations():
    #             for sta in ifc.get_connected_stations():
    #                 print(f'\tSTATION: {sta.get_mac()} is connected to: {ifc.path.replace("Device.WiFi.DataElements.Network.","")}')
        
    # for a in agent_list:
    #     print_conns(a)

    # 5. Go for a walk. Go feel the sun. Maybe read a book about recursion.
    return Topology(agent_list, g_controller_id)

class HTTPBasicAuthParams():
    def __init__(self, user: str, pw: str) -> None:
        self.user = user
        self.pw = pw
    def __repr__(self) -> str:
        return f"HTTPBasicAuthParams: username: {self.user}, pass: {self.pw}"

class ControllerConnectionCtx():
    def __init__(self, ip: str, port: str, auth: HTTPBasicAuthParams) -> None:
        if not auth:
            raise ValueError("Passed a None auth object.")
        self.ip = ip
        self.port = port
        self.auth = auth

g_ControllerConnectionCtx = None

class NBAPI_Task(threading.Thread):
    def __init__(self, connection_ctx: ControllerConnectionCtx, cadence_ms: int = 1000):
        if not connection_ctx:
            raise ValueError("Passed a None connection context.")
        super().__init__()
        self.ip = connection_ctx.ip
        self.port = connection_ctx.port
        self.cadence_ms = cadence_ms
        self.quitting = False
        if not connection_ctx.auth:
            self.auth=('admin', 'admin')
        else:
            self.auth=(connection_ctx.auth.user, connection_ctx.auth.pw)
    # Override threading.Thread.run(self)->None
    def run(self):
        while not self.quitting:
            url = "http://{}:{}/serviceElements/Device.WiFi.DataElements.".format(self.ip, self.port)
            #with open("JSONGOOD8_glinet_adapted.json", 'r') as f:
            #    nbapi_root_json_blob = json.loads(f.read())
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

def send_client_steering_request(conn_ctx: ControllerConnectionCtx, sta_mac: str, new_bssid: str):
    if not conn_ctx:
        raise ValueError("Passed a None connection context.")
    # ubus call Device.WiFi.DataElements.Network ClientSteering '{"station_mac":"<client_mac>", "target_bssid":"<BSSID>"}'
    json_payload = {"sendresp": True,
                    "commandKey": "",
                    "command": "Device.WiFi.DataElements.Network.ClientSteering",
                    "inputArgs": {"station_mac": sta_mac,
                                  "target_bssid": new_bssid}}
    url = "http://{}:{}/commands".format(conn_ctx.ip, conn_ctx.port)
    nbapi_root_request_response = requests.post(url=url, auth=(conn_ctx.auth.user, conn_ctx.auth.pw), timeout=3, json=json_payload)
    # TODO: proper error handling
    logging.info(f"Sent client steering request, cmd={str(json_payload)}")
    if not nbapi_root_request_response.ok:
        logging.error(f"Something went wrong when sending the steering request\n: {str(nbapi_root_request_response)}")

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
    global g_ControllerConnectionCtx
    g_ControllerConnectionCtx = ControllerConnectionCtx(ip, port, HTTPBasicAuthParams(httpauth_u, httpauth_pw))
    nbapi_thread = NBAPI_Task(g_ControllerConnectionCtx, cadence_ms=2000)
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
    send_client_steering_request(g_ControllerConnectionCtx, station, target_id)
    return f"Requesting a {transition_type} transition of STA {station} to {target_type} {target_id}"


@app.callback(Output('node-click', 'children'),
              Input('my-graph', 'clickData'))
def node_click(clickData):
    if not clickData:
        return ""
    agent = g_Topology.get_agent_from_hash(clickData['points'][0]['customdata'])
    if agent:
        return json.dumps(agent.params, indent=2)

    sta = g_Topology.get_station_from_hash(clickData['points'][0]['customdata'])
    if sta:
        return json.dumps(sta.params, indent=2)
    return "None found!"

if __name__ == '__main__':
    # Silence imported module logs
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, datefmt='%Y-%m-%d_%H:%M:%S')
    app.run_server(debug=True)
    if nbapi_thread:
        nbapi_thread.quit()
