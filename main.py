import logging
import queue
import re
import threading
from datetime import datetime
from pprint import pformat, pprint
from textwrap import dedent as d
from time import sleep
import networkx as nx
import plotly.graph_objs as go
import requests
from dash import Dash, Input, Output, State, dcc, html
from topology import Topology

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = Dash(__name__, external_stylesheets=external_stylesheets)
app.title = 'CableLabs EasyMesh Network Monitor'

# Create topology graph of known easymesh entities.
# Nodes indexed via MAC, since that's effectively a uuid, or a unique  graph key.
def network_graph(topology: Topology):
    agents = topology.agents
    stations = topology.stations
    G = nx.Graph()
    for sta in stations:
        G.add_node(sta)
        G.nodes()[sta]['params'] = stations[sta]
    for agent in agents:
        G.add_node(agent)
        G.nodes()[agent]['params'] = agents[agent]
        G.nodes()[agent]['IsController'] = agents[agent]['IsController']
    for connection in topology.get_connections():
        G.add_edge(connection[0], connection[1])
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
    for node in G.nodes():
        x, y = G.nodes[node]['pos']
        node_x.append(x)
        node_y.append(y)

    node_trace = go.Scatter(
        x=node_x, y=node_y,
        mode='markers',
        hoverinfo='text',
        marker=dict(
            colorscale='Electric',
            reversescale=True,
            color=[],
            size=10,
            line_width=2))

    node_text = []
    for node in G.nodes():
        if 'MACAddress' in G.nodes()[node]['params']:
            node_text.append({"Station": {"MAC": G.nodes()[node]['params']['MACAddress']}})
        elif 'IsController' in G.nodes()[node]:
            node_text.append({"Controller": {"Type": G.nodes()[node]['params']['ManufacturerModel'], 'MAC': G.nodes()[node]['params']['ID']}})
        else:
            node_text.append(G.nodes()[node]['params'])
    node_trace.marker.color = ['green' if 'IsController' in G.nodes()[node] and G.nodes()[node]['IsController'] else 'red' for node in G.nodes()]
    # Make Controller node slightly larger, as it's likely going to have the highest adjacency degree in actual networks.
    node_trace.marker.size = [35 if 'IsController' in G.nodes()[node] and G.nodes()[node]['IsController'] else 20 for node in G.nodes()]
    node_trace.text = node_text
    fig = go.Figure(data=[edge_trace, node_trace],
                layout=go.Layout(
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
g_Topology = Topology({}, {})

g_controller_id = ""

radios = {}

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
                            dcc.Dropdown(options=[], id='transition_agent', placeholder='Select an agent.'),
                            dcc.RadioItems(options=['VBSS', 'Client Steering'], id="transition-type-selection", value='VBSS', inline=True),
                            dcc.Interval(id='transition-interval', interval=300, n_intervals=0),
                            html.Button('Transition', id='transition-submit', n_clicks=0),
                            html.Div(id="transition-output", children='Press Transition to begin station transition.')
                        ],
                        style={'height': '400px'}),
                ]
            )
        ]
    )
])

def marshall_nbapi_blob(nbapi_json) -> Topology:
    # For a topology demo, we really only care about Devices that hold active BSSs (aka Agents)
    # and their connected stations.

    agents, stations = {}, {}
    # Don't try to be too clever, here - just do a bunch of linear passes over the json entries until we're doing figuring things out.

    # 0. Find the controller in the network.
    for e in nbapi_json:
        if re.search(r'\.Network\.$', e['path']):
            global g_controller_id
            g_controller_id = e['parameters']['ControllerID']

    # 1. Build device path list, so we know which BSSs belong to which Agents
    device_paths = []
    for e in nbapi_json:
        if re.search(r"\.Device\.\d\.$", e['path']):
            logging.debug(f"Found a Device path {e['path']}, putting it in the list.")
            device_paths.append(e['path'])
            agent_id = e['parameters']['ID']
            agents[agent_id] = e['parameters']
            agents[agent_id]['path'] = e['path']

    # 2. Find station entries and map them back to Devices via 'path'
    for e in nbapi_json:
        if re.search(r"\.STA\.\d\.$", e['path']):
            logging.debug(f"Found a station at {e['path']}")
            sta_mac = e['parameters']['MACAddress']
            stations[sta_mac] = e['parameters']
            for device in agents:
                if e['path'].startswith(agents[device]['path']):
                    logging.debug(f"Station at {e['path']} is connected to a BSS advertised by some radio on device {device}")
                    stations[sta_mac]['ConnectedTo'] = device

    # 3. Walk agents and tag whether or not they're the controller.
    for agent in agents:
        if agent == g_controller_id:
            agents[agent]['IsController'] = True
        else:
            agents[agent]['IsController'] = False

    return Topology(agents, stations)

class HTTPBasicAuthParams():
    def __init__(self, user, pw) -> None:
        self.user = user
        self.pw = pw
    def __repr__(self) -> str:
        return f"HTTPBasicAuthParams: username: {self.user}, pass: {self.pw}"

data_q = queue.Queue()

class NBAPI_Task(threading.Thread):
    def __init__(self, data_q, ip, port, cadence_ms=1000, auth_params=None):
        super().__init__()
        self.data_q = data_q
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
            # No reason to push this into a threadsafe q in this app, just process the data on this thread too.
            # data_q.put(nbapi_root_json_blob)
            global g_Topology
            g_Topology = marshall_nbapi_blob(nbapi_root_json_blob)
            sleep(self.cadence_ms // 1000)
    def __repr__(self):
        return f"NBAPI_Task: ip: {self.ip}, port: {self.port}, cadence (mS): {self.cadence_ms}, data_q elements: {len(self.data_q)}"
    def quit(self):
        logging.debug("Hey folks! NBAPI thread here. Time to die!")
        self.quitting = True

nbapi_thread = None

def validate_ipv4(ip_str):
    return re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip_str)

def validate_port(port_str):
    return re.match(r'^\d{1,5}$', port_str) and int(port_str) > 0 and int(port_str) < 65535

def send_client_steering_request(sta_mac: str, new_bssid: str):
    # ubus call Device.WiFi.DataElements.Network ClientSteering '{"station_mac":"<client_mac>", "target_bssid":"<BSSID>"}'
    json_payload = {}
    json_payload['station_mac'] = sta_mac
    json_payload['target_bssid'] = new_bssid
    request_string = "ubus call Device.WiFi.DataElements.Network ClientSteering {}".format(json_payload)
    print(f"send client steering request, request_string={request_string}")

@app.callback(
    Output('output', 'children'),
    Input('submit-val', 'n_clicks'),
    State('ip_input', 'value'),
    State('port_input', 'value'),
    State('httpauth_user', 'value'),
    State('httpauth_pass', 'value')
)
def connect_to_controller(n_clicks, ip, port, httpauth_u, httpauth_pw):
    if not n_clicks:
        return ""
    if not validate_ipv4(ip):
        return f"IP address '{ip}' seems malformed. Try again."
    if not validate_port(port):
        return f"Port '{port}' seems malformed. Try again."
    global nbapi_thread
    if nbapi_thread:
        nbapi_thread.quit()
    logging.debug(f"Starting NBAPI task at {ip}:{port}")
    nbapi_thread = NBAPI_Task(data_q, ip, port, 1000, HTTPBasicAuthParams(httpauth_u, httpauth_pw))
    nbapi_thread.start()
    return f"Connected to {ip}:{port}"

@app.callback(Output('my-graph', 'figure'),
              Input('graph-interval', 'n_intervals'))
def update_graph(unused):
    return network_graph(g_Topology)

@app.callback(Output('transition_station', 'options'),
              Output('transition_agent', 'options'),
              Input('transition-interval', 'n_intervals'))
def update_transition_dropdown_menus(unused):
    avail_stations = [sta for sta in g_Topology.stations]
    avail_agents = [a for a in g_Topology.agents]
    return (avail_stations, avail_agents)

@app.callback(
    Output('transition-output', 'children'),
    Input('transition-submit', 'n_clicks'),
    State('transition_station', 'value'),
    State('transition_agent', 'value'),
    State('transition-type-selection', 'value'),
)
def on_transition_click(n_clicks: int, station: str, new_agent: str, transition_type: str):
    if not n_clicks:
        return f"Click Transition to begin."
    if not station:
        return f"Select a station."
    if not new_agent:
        return f"Select a new agent."
    send_client_steering_request(station, new_agent)
    return f"Requesting a {transition_type} transition of STA {station} to Agent {new_agent}"

if __name__ == '__main__':
    app.run_server(debug=True)
    if nbapi_thread:
        nbapi_thread.quit()
