# pylint: disable=import-error, line-too-long, logging-fstring-interpolation, fixme, global-statement, too-many-lines, invalid-name, too-many-nested-blocks, too-many-branches, too-many-statements, too-many-locals, use-dict-literal, too-many-instance-attributes, too-many-arguments, too-many-return-statements, not-callable

"""
This module starts an HTTP client to an EasyMesh controller and begins polling for updates.
It then renders the updates on a web UI using a Dash app.

Functions:
----------
__main__():
    Starts the HTTP client and web UI, sets the logging level and runs the server in debug mode.

Attributes:
-----------
None.

Usage:
------
Run the module to start the HTTP client and web UI, and begin polling for updates.

Example:
--------
python my_easy_mesh_app.py
"""

import json
import logging
from enum import Enum
from textwrap import dedent as d
import configparser
import networkx as nx
import plotly.graph_objs as go
from dash import Dash, Input, Output, State, dcc, html
import dash_daq as daq
from networkx.drawing.nx_pydot import graphviz_layout
from PIL import Image

import validation
from easymesh import (ORIENTATION, Agent, Interface,
                      Station)
from topology import Topology
from nbapi_rpc import (send_client_steering_request, send_vbss_move_request,
                    send_vbss_creation_request, send_vbss_destruction_request)
from controller_ctx import ControllerConnectionCtx
from http_auth import HTTPBasicAuthParams
from colors import ColorSync
from render_state import AgentRenderState, EnumAgentRenderState
from nbapi import NBAPITask
from nbapi_persistent import get_did_station_move, get_rssi_measurements

app = Dash(__name__)

g_StationsToRadio = {}
nbapi_thread: NBAPITask = None
class NodeType(Enum):
    """Enum representation of different node types in an EasyMesh network.
    """
    UNKNOWN = 0
    STATION = 1
    AGENT = 2
    CONTROLLER = 3

marker_references = [] # Used in the click callback to find the node clicked on

def gen_node_text(topology: Topology, node_id: str, node_type: NodeType):
    """
    Generate text representation for a given node based on its type and ID.

    Parameters:
    -----------
    topology : Topology
        The topology object that contains the node information.

    node_id : str
        The ID of the node to generate text representation for.

    node_type : NodeType
        The type of the node to generate text representation for.

    Returns:
    --------
    str
        The text representation of the node.
    """
    node_type_dict = {
        NodeType.STATION: (topology.get_station_from_hash, "Station: MAC: {} ConnectedTo: {}"),
        NodeType.AGENT: (topology.get_agent_from_hash, "Agent: Model: {} NumRadios: {} ID: {}"),
        NodeType.CONTROLLER: (topology.get_agent_from_hash, "Agent: Model: {} NumRadios: {} ID: {}")
    }
    if node_type not in node_type_dict:
        return "Unknown! This shouldn't happen."
    get_node_method, node_format = node_type_dict[node_type]
    node_obj = get_node_method(node_id)
    if not node_obj:
        return "Node"
    if node_type == NodeType.STATION:
        return node_format.format(node_obj.get_mac(), topology.get_bssid_connection_for_sta(node_obj.get_mac()))
    if node_type in [NodeType.AGENT, NodeType.CONTROLLER]:
        return node_format.format(node_obj.get_manufacturer(), node_obj.num_radios(), node_obj.get_id())
    return ""


def add_children_to_graph_recursive(agent: Agent, graph):
    """
    Recursively add children and connected stations of the given Agent to the provided networkx Graph.

    Parameters:
    -----------
    agent : Agent
        The Agent object whose children and connected stations will be added to the graph.

    graph : networkx.Graph
        The graph to which the children and connected stations will be added.

    Returns:
    --------
    None.

    Raises:
    -------
    None.

    Usage:
    ------
    This function can be used to recursively add children and connected stations of an Agent to a networkx Graph.

    Example:
    --------
    add_children_to_graph_recursive(agent, graph)
    """
    for child in agent.get_children():
        marker_references.append(child.get_hash_id())
        graph.add_node(child.get_hash_id())
        graph.nodes()[child.get_hash_id()]['type'] = NodeType.AGENT
        add_children_to_graph_recursive(child, graph)

    for sta in agent.get_connected_stations():
        marker_references.append(sta.get_hash_mac())
        graph.add_node(sta.get_hash_mac())
        graph.nodes()[sta.get_hash_mac()]['type'] = NodeType.STATION


def get_iface_markers(agent: Agent):
    """
    Get interface markers for an Agent.

    Parameters:
    - agent (Agent): The agent whose interface markers will be obtained.

    Returns:
    A dictionary with the following keys:
        - 'x' (list): List of X positions of interface markers.
        - 'y' (list): List of Y positions of interface markers.
        - 'node_labels' (list): List of node labels.
        - 'node_hover_text' (list): List of node hover text.
        - 'node_colors' (list): List of node colors.
        - 'node_sizes' (list): List of node sizes.
        - 'node_symbols' (list): List of node symbols.

    This function obtains interface markers for an Agent using its orientation and interfaces. The markers are positioned in such a way that they are visible and do not overlap with the Agent marker. The markers have diamond shapes and are colored red or blue depending on whether the interface is wired or not. The function returns a dictionary containing the lists of X and Y positions, node labels, node hover text, node colors, node sizes and node symbols of the interface markers.
    """
    x_distance = 14  # Distance between two interface markers
    x_min = 20       # Distance between the agent marker and the interface marker
    y_distance = 7
    y_min = 8

    interfaces_by_orientation = [
        agent.get_interfaces_by_orientation(ORIENTATION.UP),
        agent.get_interfaces_by_orientation(ORIENTATION.RIGHT),
        agent.get_interfaces_by_orientation(ORIENTATION.DOWN)
    ]

    node_x, node_y, node_labels = [], [], []
    node_hover_text, node_colors, node_sizes, node_symbols = [], [], [], []

    for idx, interfaces in enumerate(interfaces_by_orientation):
        x0, y0 = agent.x, agent.y
        if idx == 0:
            # UP
            x0 -= (len(interfaces) / 2) * x_distance
            y0 += y_min
        elif idx == 1:
            # RIGHT
            x0 += x_min
            y0 -= (len(interfaces) / 2) * y_distance + y_distance / 2
        else:
            # DOWN
            x0 -= (len(interfaces) / 2) * x_distance
            y0 -= y_min

        if len(interfaces) % 2 != 0:
            if idx == 0:
                x0 += x_distance / 2
            else:
                y0 += y_distance / 2

        for i in interfaces:
            i.x, i.y = x0, y0
            if idx == 0:
                x0 += x_distance
            elif idx == 1:
                y0 += y_distance
            else:
                x0 += x_distance

    for i in agent.get_interfaces():
        marker_references.append(i.get_hash_id())
        node_x.append(i.x)
        node_y.append(i.y)
        node_labels.append("")
        node_hover_text.append(f'Interface {i.get_interface_number()} with MAC: {i.params["MACAddress"]} and type: {i.params["MediaTypeString"]}')
        node_sizes.append(14)
        node_symbols.append("diamond")
        node_colors.append("red" if i.params["wired"] else "blue")

    return {
        'x': node_x,
        'y': node_y,
        'node_labels': node_labels,
        'node_hover_text': node_hover_text,
        'node_colors': node_colors,
        'node_sizes': node_sizes,
        'node_symbols': node_symbols
    }

def add_edge_between_interfaces(iface1: Interface, iface_or_station, edge_interfaces_x, edge_interfaces_y):
    """
    Adds an edge between two interfaces or between an interface and a station to the graph.

    Args:
        iface1 (Interface): The first interface to connect.
        iface_or_station: The interface or station to connect to the first interface.
        edge_interfaces_x (list): The x-coordinates of the edge interfaces.
        edge_interfaces_y (list): The y-coordinates of the edge interfaces.
    """
    edge_interfaces_x.append(iface1.x)
    edge_interfaces_x.append(iface_or_station.x)
    edge_interfaces_x.append(None)
    edge_interfaces_y.append(iface1.y)
    edge_interfaces_y.append(iface_or_station.y)
    edge_interfaces_y.append(None)

def get_color_for_agent(color_selector: ColorSync, agent: Agent) -> str:
    """Gets a color string for a given agent.

    Args:
        color_selector (ColorSync): The color selector
        agent (Agent): The Agent to get a color for

    Returns:
        str: The string representation of the color to be used for rendering (e.g. 'purple')
    """
    if not agent:
        return color_selector.get_color_list()[0]
    agent_mac = agent.get_id()
    if not color_selector.knows_agent(agent_mac):
        color_selector.add_agent(agent_mac)
    return color_selector.get_color_for_agent(agent_mac)

g_ColorSync = ColorSync('green')
g_RenderState = AgentRenderState()

def get_plotly_friendly_render_state_string(render_state: EnumAgentRenderState) -> str:
    """
    Return a string representing the Plotly-friendly render state of an agent, given its render
    state. This function maps the EnumAgentRenderState enumeration to Plotly's marker symbols.

    Args:
        render_state (EnumAgentRenderState): The render state of an agent.

    Returns:
        str: A string representing the Plotly-friendly render state of the agent, based on its
        render state. Returns 'circle' if the render state is UNKNOWN, CLOSED, or SOLID.
        Returns 'open-circle' if the render state is OPEN.
    """
    marker_symbol_string: str = ""
    if render_state in (EnumAgentRenderState.UNKNOWN, EnumAgentRenderState.CLOSED, EnumAgentRenderState.SOLID):
        marker_symbol_string = "circle"
    elif render_state == EnumAgentRenderState.OPEN:
        marker_symbol_string = "circle-open"
    return marker_symbol_string

def get_topology() -> Topology:
    """Front-end call for getting a topology.
    For various reasons, the global topology instance for the current connection may not yet be
    available (not yet deserialized, NBAPI thread is not running, etc).

    In that case, we still want to emit a default topology object so the UI can continue rendering.

    Returns:
        Topology: A default dummy topology, or a real topology representing the network if available.
    """
    if nbapi_thread is None or nbapi_thread.get_topology() is None:
        return Topology({}, "")
    return nbapi_thread.get_topology()

# Create topology graph of known easymesh entities.
# Nodes indexed via MAC, since that's effectively a uuid, or a unique  graph key.
def network_graph(topology: Topology):
    """
    This function generates a network graph of the given topology using the plotly library.

    Parameters:
    ----------
    topology: Topology
        The topology object to generate the network graph for.

    Returns:
    -------
    plotly.graph_objs._figure.Figure
        A plotly Figure object containing the network graph of the topology. If there are no nodes in the graph, an empty figure will be returned.
    """
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

    G = nx.Graph()

    marker_references.clear()
    marker_references.append(topology.controller.get_hash_id())
    G.add_node(topology.controller.get_hash_id())
    G.nodes()[topology.controller.get_hash_id()]['type'] = NodeType.CONTROLLER
    add_children_to_graph_recursive(topology.controller, G)

    # Add edges/connections between agents (builds general graph)
    for agent in topology.agents:
        for ifc in agent.get_interfaces():
            for child_iface in ifc.get_children():
                if not child_iface.get_children():
                    G.add_edge(child_iface.get_parent_agent().get_hash_id(), ifc.get_parent_agent().get_hash_id())

            if ifc.get_connected_stations():
                for sta in ifc.get_connected_stations():
                    G.add_edge(sta.get_hash_mac(), ifc.get_parent_agent().get_hash_id())

    if len(G.nodes()) == 0:
    # If the graph is empty, there's no EasyMesh nodes to render. Bail.
        logging.debug("Zero nodes in the topology graph, skipping render cycle")
        return go.Figure(data=[],layout=layout)
    pos = graphviz_layout(G, prog="dot")

    # DEBUG: Calculate position range of the graphed nodes
    # x_axis_range = [min(pos.values(), key=lambda x: x[0])[0], max(pos.values(), key=lambda x: x[0])[0] ]
    # y_axis_range = [min(pos.values(), key=lambda x: x[1])[1], max(pos.values(), key=lambda x: x[1])[1] ]

    for node in G.nodes:
        G.nodes[node]['pos'] = list(pos[node])
        x, y = G.nodes[node]['pos']
        agent = get_topology().get_agent_from_hash(node)
        if agent:
            agent.x = x
            agent.y = y
        else:
            station = get_topology().get_station_from_hash(node)
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
        shape_type = 'circle'
        if G.nodes[node]['type'] == NodeType.AGENT or G.nodes[node]['type'] == NodeType.CONTROLLER:
            agent = topology.get_agent_from_hash(node)
            g_RenderState.add_new_agent(agent)
            shape_type = get_plotly_friendly_render_state_string(g_RenderState.get_state(agent))
        node_hover_text.append(gen_node_text(get_topology(), node, G.nodes[node]['type']))
        node_type = G.nodes[node]['type']
        if node_type == NodeType.CONTROLLER:
            agent = topology.get_agent_from_hash(node)
            node_sizes.append(52)
            node_symbols.append(shape_type)
            node_colors.append(get_color_for_agent(g_ColorSync, agent))
            node_labels.append("  prplMesh Controller + Agent<br>  running on prplOs")
        if G.nodes[node]['type'] == NodeType.AGENT:
            agent = topology.get_agent_from_hash(node)
            node_sizes.append(45)
            node_symbols.append(shape_type)
            node_colors.append(get_color_for_agent(g_ColorSync, agent))
            if topology.get_agent_from_hash(node).params["ManufacturerModel"] == "Ubuntu": # RDKB
                node_labels.append("  prplMesh Agent on RDK-B<br>  (Turris-Omnia)")
            elif topology.get_agent_from_hash(node).params["ManufacturerModel"] == "X5042": # ARRIS/ COMMSCOPE 3ʳᵈ
                node_labels.append("  3ʳᵈ party EasyMesh Agent on 3ʳᵈ party OS<br>  (Commscope/ARRIS X5)")
            elif topology.get_agent_from_hash(node).params["Manufacturer"] == "Sagemcom": # prplMesh on Sagemcomm extender
                node_labels.append("  prplMesh Agent on SWAN OS<br>  (Sagemcom Extender)")
            elif topology.get_agent_from_hash(node).params["ManufacturerModel"] == "GL.iNet GL-B1300": # prplMesh on GL-inet
                node_labels.append("  prplMesh Agent on prplOS<br>  (GL.iNet B1300)")
            elif topology.get_agent_from_hash(node).params["ManufacturerModel"] == "prpl Foundation Haze":
                node_labels.append("  prplMesh Agent on prplOS<br>  (Haze)")
            elif topology.get_agent_from_hash(node).params["ManufacturerModel"] == "WNC RERQ-WI81":
                node_labels.append("  prplMesh Agent on prplOS<br>  (Freedom)")
            elif topology.get_agent_from_hash(node).params["ManufacturerModel"] == "freedom_rdkb":
                node_labels.append("  prplMesh Agent on RDK-B<br>  (Freedom)")
            else:
                node_labels.append(" unknown EasyMesh Agent")

        if G.nodes[node]['type'] == NodeType.STATION:
            node_sizes.append(35)
            node_symbols.append('circle-open')
            node_colors.append('red')
            sta = topology.get_station_from_hash(node)
            if sta.get_steered():
                node_labels.append(f'  Client STA: {topology.get_station_from_hash(node).params["MACAddress"][-2::]}<br>  steered by prplMesh Controller<br>  via prplMesh Northbound API')# + topology.get_station_from_hash(node).params["mac"])
            elif 'Hostname' in sta.params and sta.params['Hostname'] and sta.params['Hostname'] != '0':
                hostname = sta.params['Hostname'] + '-' + sta.params['MACAddress'][-2::]
                node_labels.append(f'Client STA: {hostname}')
            else:
                node_labels.append(f'  Client STA: {topology.get_station_from_hash(node).params["MACAddress"][-2::]}')

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
    marker_references.clear()

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
        line=dict(width=0.01, color='#111'),
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

    # Add graph data
    for a in get_topology().get_agents():
        a.sort_interfaces()
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
        customdata=marker_references,
        hoverinfo='text',
        marker=dict(
            colorscale='Electric',
            reversescale=True,
            color=node_colors,
            size=node_sizes,
            line_width=2))

    edge_interfaces_ethernet_x = []
    edge_interfaces_ethernet_y = []

    edge_interfaces_wifi_x = []
    edge_interfaces_wifi_y = []

    edge_interfaces_wifi_fronthaul_x = []
    edge_interfaces_wifi_fronthaul_y = []

    # Generate edges between interfaces; based on calculated agent coordinates
    for agent in topology.agents:
        for ifc in agent.get_interfaces():
            for child in ifc.get_children():
                if not child.get_children():
                    if child.params["wireless"] or ifc.params["wireless"]:
                        add_edge_between_interfaces(child, ifc, edge_interfaces_wifi_x, edge_interfaces_wifi_y)
                    else:
                        add_edge_between_interfaces(child, ifc, edge_interfaces_ethernet_x, edge_interfaces_ethernet_y)

            if ifc.get_connected_stations():
                for sta in ifc.get_connected_stations():
                    add_edge_between_interfaces(ifc, sta, edge_interfaces_wifi_fronthaul_x, edge_interfaces_wifi_fronthaul_y)

    edge_trace_interfaces_ethernet = go.Scatter(
        x=edge_interfaces_ethernet_x, y=edge_interfaces_ethernet_y,
        line=dict(width=2, color='#111', dash="solid"),
        hoverinfo='none',
        mode='lines')

    edge_trace_interfaces_wifi = go.Scatter(
        x=edge_interfaces_wifi_x, y=edge_interfaces_wifi_y,
        line=dict(width=2, color='#111', dash="dash"),
        hoverinfo='none',
        mode='lines')

    edge_trace_interfaces_wifi_fronthaul = go.Scatter(
        x=edge_interfaces_wifi_fronthaul_x, y=edge_interfaces_wifi_fronthaul_y,
        line=dict(width=2, color='#c119b6', dash="dash"),
        hoverinfo='none',
        mode='lines')

    fig = go.Figure(data=[edge_trace, node_trace, node_ifaces, edge_trace_interfaces_ethernet, edge_trace_interfaces_wifi, edge_trace_interfaces_wifi_fronthaul], layout=layout)
    fig.update_traces(textposition='middle right', textfont_size=14) # , marker_symbol="diamond")

    # Add legend image
    legendImage = Image.open("res/legend_small.png")
    fig.add_layout_image(
        dict(
        source=legendImage,
        xref="paper",
        yref="paper",
        x=1,
        y=1,
        sizex=0.35,
        sizey=0.35,
        xanchor="right",
        yanchor="top",
        opacity=0.8,
        layer="above")
    )

    fig.update()

    # "Zoom out"/autorange the graph, by scaling the calculated autorange
    full_fig = fig.full_figure_for_development(warn=False)
    x_range = full_fig.layout.xaxis.range
    y_range = full_fig.layout.yaxis.range

    # Adjust range/scaling based on autorange calculation
    if abs(x_range[1]-x_range[0]) < 40:
        x_range = [x_range[0]*0.5-x_range[1]*2, x_range[1]*5]
    elif abs(x_range[1]-x_range[0]) < 500:
        x_range = [x_range[0]*0.6, x_range[1]*1.5]
    elif abs(x_range[1]-x_range[0]) < 1000:
        x_range = [x_range[0]*0.8, x_range[1]*1.2]
    else:
        x_range = [x_range[0]*0.9, x_range[1]*1.15]

    if abs(y_range[1]-y_range[0]) < 40:
        y_range = [y_range[0]*0.8-y_range[1]*3, y_range[1]*3]
    else:
        y_range = [y_range[0]*0.9-y_range[1]*0.2, y_range[1]*1.2]


    fig.update_layout(
        xaxis={"range": x_range},
        yaxis={"range": y_range},
    )

    return fig

styles = {
    'pre': {
        'border': 'thin lightgrey solid',
        'overflowX': 'scroll'
    }
}

# RUID -> STA_MAC -> [RSSI measurements]
g_RSSI_Measurements = {}

stations_have_moved = []

g_ControllerConnectionCtx = None

'''
For keeping track of the last clicked station, for the RSSI plotting.
'''
LAST_CLICKED_STATION: Station = None
def get_last_clicked_station() -> Station:
    """Gets the last station node clicked in the topology graph.

    Returns:
        Station: The last clicked station.
    """
    return LAST_CLICKED_STATION
def set_last_clicked_station(last_clicked_sta: Station) -> None:
    """Sets the last station node clicked in the topology graph.

    Args:
        last_clicked_sta (Station): The last clicked station.
    """
    global LAST_CLICKED_STATION
    LAST_CLICKED_STATION = last_clicked_sta

# Component callbacks
@app.callback(
    Output('output', 'children'),
    Input('submit-val', 'n_clicks'),
    State('ip_input', 'value'),
    State('port_input', 'value'),
    State('httpauth_user', 'value'),
    State('httpauth_pass', 'value')
)
def connect_to_controller(n_clicks: int, ip: str, port: str, httpauth_u: str, httpauth_pw: str) -> str:
    """Connect click callback. Starts an HTTP client thread pointing at ip:port

    Args:
        n_clicks (int): Clicked? If 0, do nothing.
        ip (str): The IP address of the Controller to connect to.
        port (str): The port of the controller to connect to.
        httpauth_u (str): The HTTP Basic Auth username of the Controller's HTTP proxy.
        httpauth_pw (str): The HTTP Basic Auth password of the Controller's HTTP proxy.

    Returns:
        str: A success or failure message sent to the UI.
    """
    if not n_clicks:
        return ""
    logging.debug(f"Request to monitor controller at {ip}:{port}")
    if not validation.validate_ipv4(ip):
        return f"IP address '{ip}' seems malformed. Try again."
    if not validation.validate_port(port):
        return f"Port '{port}' seems malformed. Try again."
    global nbapi_thread
    if nbapi_thread:
        nbapi_thread.quit()
    logging.debug(f"Starting NBAPI task at {ip}:{port}")
    global g_ControllerConnectionCtx
    g_ControllerConnectionCtx = ControllerConnectionCtx(ip, port, HTTPBasicAuthParams(httpauth_u, httpauth_pw))
    nbapi_thread = NBAPITask(g_ControllerConnectionCtx, cadence_ms=2000)
    nbapi_thread.start()
    return f"Connected to {ip}:{port}"

@app.callback(Output('my-graph', 'figure'),
              Input('graph-interval', 'n_intervals'))
def update_graph(_):
    """
    Updates the contents of the 'my-graph' component based on a periodic timer.

    Parameters:
    ----------
    _ : int
        A dummy variable that is not used in the function.

    Returns:
    -------
    Graph
        A Plotly figure/graph representing the current topological state of the EasyMesh network.
    """
    return network_graph(get_topology())

@app.callback(Output('easymesh_ssid', 'value'),Input('transition-interval', 'n_intervals'))
def update_prplmesh_ssid(_):
    """Grab the static network SSID.

    Args:
        _ (int): Unused

    Returns:
        str: The static SSID of the first radio in the network.
    """
    return get_topology().get_ssid()

@app.callback(Output('vbss-creation-client-mac', 'options'),
              Input('vbss-creation-interval', 'n_intervals')
)
def update_stations(_):
    """Populates the available station list for the client MAC field of a VBSS creation request.
    """
    return [sta.get_mac() for sta in get_topology().get_stations()]

@app.callback(Output('transition_station', 'options'),
              Output('transition_bssid', 'options'),
              Output('transition_bssid', 'placeholder'),
              Input('transition-interval', 'n_intervals'),
              Input('transition-type-selection', 'value'))
def update_transition_dropdown_menus(_, _type):
    """Periodically update the available stations and BSSes for initiating a transition

    Args:
        _ (int): Unused
        _type (str): The type of transition

    Returns:
        A 3-tuple:  Lists of options, ([Stations], [Target_radios], "Description String")
    """
    placeholder = 'Select a new BSSID'
    avail_stations = [sta.get_mac() for sta in get_topology().get_stations()]
    if _type is None or _type == 'Client Steering':
        avail_targets = [bss.get_bssid() for bss in get_topology().get_bsses()]
    elif _type == 'VBSS':
        avail_targets = [radio.get_ruid() for radio in get_topology().get_radios()]
        placeholder = 'Select a new RUID'
    return (avail_stations, avail_targets, placeholder)

@app.callback(Output('vbss-move-client-mac', 'options'),
              Input('vbss-move-interval', 'n_intervals')
)
def update_vbss_move_client_mac(_):
    """Populate the client MAC dropdown for VBSS moves.
    """
    return [sta.get_mac() for sta in get_topology().get_stations()]

@app.callback(Output('vbss-destruction-bssid', 'options'),
              Input('vbss-move-interval', 'n_intervals')
)
def update_vbss_destruction_bssid_dropdown(_):
    """Populates the VBSSID dropdown selection for the Destroy component.
    """

    # TODO: the below commented-out code should be the only code in this function.
    # Currently, prplMesh does not populate the 'IsVBSS' field correctly for virtual BSSes.
    # return [bss.get_bssid() for bss in get_topology().get_bsses() if bss.is_vbss()]

    return [bss.get_bssid() for bss in get_topology().get_bsses()]

@app.callback(Output('vbss-move-dest-ruid', 'options'),
              Input('vbss-move-interval', 'n_intervals')
)
def update_vbss_move_ruid_dropdown(_):
    """Populate the destination RUID dropdown for VBSS moves.
    """
    return [radio.get_ruid() for radio in get_topology().get_radios()]

@app.callback(Output('vbss-creation-ruid', 'options'),
              Input('vbss-creation-interval', 'n_intervals')
)
def update_vbss_creation_ruid_dropdown(_):
    """Populates the RUID dropdown field for creating a VBSS.
    """
    return [radio.get_ruid() for radio in get_topology().get_radios()]

@app.callback(
    Output('transition-output', 'children'),
    Input('transition-submit', 'n_clicks'),
    State('transition_station', 'value'),
    State('transition_bssid', 'value'),
    State('transition-type-selection', 'value'),
)
def on_transition_click(n_clicks: int, station: str, target_id: str, transition_type: str):
    """Callback handling a begin transition button click

    Args:
        n_clicks (int): Clicked? If 0, do nothing
        station (str): The station to initiate a move for
        target_id (str): The target MAC, either a BSSID for 11v steering or a radio MAC for a VBSS move.
        transition_type (str): The type of transition. Either 'VBSS', or 11v.

    Returns:
        _type_: _description_
    """
    if not n_clicks:
        return "Click Transition to begin."
    if not station:
        return "Select a station."
    if not target_id:
        return "Select a new target."
    if transition_type == 'VBSS':
        target_type = 'RUID'
        if not get_topology().validate_vbss_move_request(station, target_id):
            return f"Station {station} is already connected to {target_id}"
    else:
        target_type = 'BSSID'
    logging.debug(f"Sending client steering request (type: {transition_type}) from STA {station} to {target_id}")
    send_client_steering_request(g_ControllerConnectionCtx, station, target_id)
    return f"Requesting a {transition_type} transition of STA {station} to {target_type} {target_id}"


@app.callback(Output('node-click', 'children'),
              Input('my-graph', 'clickData'))
def node_click(clickData):
    """
    Updates the contents of the 'node-click' component based on the clicked data of the 'my-graph' component.

    Parameters:
    ----------
    clickData: dict
        A dictionary containing the data of the clicked point on the 'my-graph' component.

    Returns:
    -------
    str
        The string representation of the clicked node's parameters, depending on whether it's an agent, station, or interface.
        If there is no click data, it returns an empty string.
        If the clicked point doesn't have a 'customdata' attribute, it returns "Node data not available".
        If the clicked point is not found in any of the node types, it returns "None found!".
    """
    if not clickData:
        return ""
    clicked_point = clickData['points'][0]
    if 'customdata' not in clicked_point:
        return "Node data not available"
    node_hash = clicked_point['customdata']
    agent = get_topology().get_agent_from_hash(node_hash)
    if agent:
        return json.dumps(agent.params, indent=2)

    sta = get_topology().get_station_from_hash(node_hash)
    if sta:
        logging.debug("Station clicked!")
        set_last_clicked_station(sta)
        return json.dumps(sta.params, indent=2)

    interface = get_topology().get_interface_from_hash(node_hash)
    if interface:
        return json.dumps(interface.params, indent=2)
    return "None found!"

@app.callback(Output('vbss-move-output', 'children'),
              Input('vbss-move-btn', 'n_clicks'),
              State('vbss-move-ssid', 'value'),
              State('vbss-move-password', 'value'),
              State('vbss-move-dest-ruid', 'value'),
              State('vbss-move-client-mac', 'value')
)
def vbss_move_callback(n_clicks: int, ssid: str, password: str, dest_ruid: str, client_mac: str):
    """Handle a VBSS move click
    """
    if not n_clicks:
        return ""
    if not ssid:
        return "Enter an SSID"
    if not password:
        return "Enter a password"
    if not dest_ruid:
        return "Select a destination RUID"
    if not client_mac:
        return "Select a client MAC"
    password_ok, password_error = validation.validate_vbss_password_for_creation(password)
    if not password_ok:
        return password_error
    bssid = get_topology().get_bssid_connection_for_sta(client_mac)
    bss = get_topology().get_bss_by_bssid(bssid)
    send_vbss_move_request(g_ControllerConnectionCtx, client_mac, dest_ruid, ssid, password, bss)
    return "Sent VBSS move request"

@app.callback(Output('vbss-creation-output', 'children'),
              Input('vbss-creation-submit', 'n_clicks'),
              State('vbss-ssid', 'value'),
              State('vbss-pw', 'value'),
              State('vbss-creation-client-mac', 'value'),
              State('vbss-creation-vbssid', 'value'),
              State('vbss-creation-ruid', 'value')
)
def vbss_creation_click(n_clicks: int, ssid: str, password: str, client_mac: str, vbssid: str, ruid: str):
    """Callback for VBSS Creation Button click

    Args:
        n_clicks (int): How many clicks? Binary, 1 or 0. If 0, just bail.
        ssid (str): SSID of the VBSS to create.
        password (str): Password for the VBSS.
        client_mac (str): The Client (STA) that this VBSS is meant for.
        vbssid (str): The VBSSID to use for the newly created VBSS.

    Returns:
        str: Error string if inputs are invalid, success of sending the creation request otherwise.
    """
    if not n_clicks:
        return ""
    if ssid is None:
        return "Enter an SSID"
    if password is None:
        return "Enter a password"
    if vbssid is None:
        return "Enter a VBSSID"
    if client_mac is None:
        return "Select a station"
    if ruid is None:
        return "Select a Radio to create the VBSS on."
    is_password_valid, password_error = validation.validate_vbss_password_for_creation(password)
    if not is_password_valid:
        return f"Invalid password: {password_error}"
    is_client_mac_valid, client_mac_error = validation.validate_vbss_client_mac(client_mac, get_topology())
    if not is_client_mac_valid:
        return f"Client MAC invalid: {client_mac_error}"
    is_vbssid_valid, vbssid_error = validation.validate_vbss_vbssid(vbssid, get_topology())
    if not is_vbssid_valid:
        return f"VBSSID invalid: {vbssid_error}"
    radio = get_topology().get_radio_by_ruid(ruid)
    if radio is None:
        return "Radio is unknown"
    send_vbss_creation_request(g_ControllerConnectionCtx, vbssid, client_mac, ssid, password, radio)
    return "Sent a VBSS creation request."


@app.callback(Output('vbss-destruction-output', 'children'),
              Input('vbss-destruction-submit', 'n_clicks'),
              State('vbss-destruction-disassociate', 'on'),
              State('vbss-destruction-bssid', 'value')
)
def vbss_destruction_click(n_clicks: int, should_disassociate: bool, bssid: str):
    """Callback for VBSS destruction click

    Args:
        n_clicks (int): How many clicks? Binary, 1 or 0. If 0, just bail.
        should_disassociate (bool): If set, disassociate all clients prior to tearing down the BSS.
        bssid (str): The BSSID of the BSS to destroy.

    Note: Canonically, the NBAPI method also takes a 'client_mac', but it is unused, so not parameterized in the UI.
    """
    if not n_clicks:
        return ""
    bss = get_topology().get_bss_by_bssid(bssid)
    if not bss:
        return f"Could not find a BSS for BSSID '{bssid}'"
    dummy_client_mac_addr = "aa:bb:cc:dd:ee:ff"
    send_vbss_destruction_request(g_ControllerConnectionCtx, dummy_client_mac_addr, should_disassociate, bss)
    return f"Sent VBSS destruction request for '{bssid}'"


#  station -> list of moves
g_Transition_X_Positions = {}
@app.callback(
    Output('rssi-plot', 'figure'),
    Input('rssi-plot-interval', 'n_intervals')
)
def update_rssi_plot(n_intervals: int):
    """Adds data points for the currently selected station in the 'rssi-plot' div.

    Args:
        int (n_intervals): Number of times this callback has fired.
    """
    station_of_interest = get_last_clicked_station()
    if not station_of_interest:
        # Log that there's no station selected once.
        if n_intervals == 0:
            logging.debug("No station!")
        return dict()
    selected_sta_mac = station_of_interest.get_mac()
    # Store as a static variable so we can clear the RSSI table when a new station is selected.
    if update_rssi_plot.last_sta is None:
        update_rssi_plot.last_sta = station_of_interest
    if update_rssi_plot.last_sta.get_mac() != selected_sta_mac:
        logging.debug(f"New station clicked ({selected_sta_mac}), resetting plot data")
        update_rssi_plot.last_sta = station_of_interest


    fig = go.Figure()

    unassoc_color_lut = {}
    for key in get_rssi_measurements().items():
        radio_mac = key[0]
        agent = get_topology().get_agent_by_ruid(radio_mac)
        unassoc_color_lut[radio_mac] = get_color_for_agent(g_ColorSync, agent)

    # We need to render curves starting at the most recent move, instead of t=0
    initial_x_offset = 0
    for ruid, sta_list in get_rssi_measurements().items():
        for sta_mac, measurement_list in sta_list.items():
            if sta_mac == selected_sta_mac:
                y_axis_vals = measurement_list
                a = max(len(measurement_list), 500)
                x_axis_vals = list(range(initial_x_offset, a))
                trace_name = f"STA {station_of_interest.params['Hostname']} ({selected_sta_mac}) relative to radio {ruid}"
                trace = go.Scatter(x=x_axis_vals, y=y_axis_vals, marker=dict(color=unassoc_color_lut[ruid]), name=trace_name, mode="lines", hoverinfo="all")
                fig.add_trace(trace)
                if get_did_station_move(sta_mac):
                    logging.debug(f"station {sta_mac} has moved, drawing vertical marker.")
                    if sta_mac not in g_Transition_X_Positions:
                        g_Transition_X_Positions[sta_mac] = []
                    pos = len(measurement_list) - 1
                    g_Transition_X_Positions[sta_mac].append(pos)
                    trace_name = f"VBSS move for STA {sta_mac}"

    # Must render each VBSS move every render cycle to maintain VBSS move history in the plot.
    for station_mac, move_list in g_Transition_X_Positions.items():
        if station_mac == selected_sta_mac:
            for move_position in move_list:
                fig.add_vline(x=move_position, line_width=3, line_dash='dash', line_color='black')
    return fig
# Init callback function attribute (static)
update_rssi_plot.last_sta = None

def get_app_title(config: configparser.ConfigParser) -> str:
    """Get the Dash app title based on the branding field of the config passed in.

    Args:
        config (configparser.ConfigParser): The config file for the app.

    Returns:
        str: The appropriate branding based on the value of the 'branding' key in the 'ui' section
        of the config, if found.
        If this key is missing, a default title is returned.
    """
    if 'ui' in config and 'branding' in config['ui']:
        branding = config['ui']['branding'].lower()
        if branding in ('prpl', 'prplmesh'):
            return 'CableLabs/prpl Mesh Monitor'
    # default
    return 'CableLabs EasyMesh Network Monitor'

def get_branding_sensitive_string_from_config(config: configparser.ConfigParser) -> str:
    """Get brand-sensitive string from config branding field

    Args:
        config (configparser.ConfigParser): The config

    Returns:
        str: The brand string for the 'branding' key in the 'ui' section of the config, if found.
        Otherwise returns default brand string.
    """
    if 'ui' in config and 'branding' in config['ui']:
        if config['ui']['branding'].lower() in ('prpl', 'prplmesh'):
            return 'prplMesh'
    # default
    return 'EasyMesh'

def gen_app_layout(config: configparser.ConfigParser):
    """Create an HTML layout based on the configuration file provided.

    Args:
        config (configparser.ConfigParser): The config file

    Returns:
        plotly layout: The HTML layout for the app
    """
    ui_section = config["ui"]
    auth_section = config["auth"]
    brand_string = get_branding_sensitive_string_from_config(config)
    layout = html.Div([
        html.Div([html.H1(f"{brand_string} Network Topology Graph")],
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
                                dcc.Markdown(d(f"""
                                **{brand_string} Network Controller**

                                Input the IP and Port of the Controller in the {brand_string} network to visualize.
                                """)),
                                dcc.Input(id="ip_input", type="text", placeholder="192.168.1.1", value=ui_section.get('controller-addr', '192.168.1.110')),
                                dcc.Input(id="port_input", type="text", placeholder="8080", value=ui_section.get('controller-port', '8080')),
                                html.Br(),
                                html.Br(),
                                dcc.Markdown(d("""
                                **HTTP Basic Auth Params**

                                Username and password for the HTTP proxy.
                                """)),
                                dcc.Input(id='httpauth_user', type='text', placeholder='admin', value=auth_section.get('http-auth-user', 'admin')),
                                dcc.Input(id='httpauth_pass', type='text', placeholder='admin', value=auth_section.get('http-auth-pass', 'admin')),
                                html.Button('Submit', id='submit-val', n_clicks=0),
                                html.Div(id="output", children='Press Submit to connect'),
                                html.Br(),
                                dcc.Markdown(d(f"""
                                **{brand_string} credentials**

                                SSID of the prplMesh network
                                """)),
                                dcc.Input(id='easymesh_ssid', type='text', value='SSID', readOnly=True, disabled=True),
                                dcc.Markdown(d("""
                                **Create VBSS**
                                """)),
                                dcc.Input(id="vbss-ssid", type="text", placeholder="VBSS SSID"),
                                dcc.Input(id="vbss-pw", type="password", placeholder="VBSS Password"),
                                dcc.Input(id='vbss-creation-vbssid', type='text', placeholder='VBSSID'),
                                dcc.Dropdown(options=[], id='vbss-creation-client-mac', placeholder='Select a station.'),
                                dcc.Dropdown(options=[], id='vbss-creation-ruid', placeholder='Select a RUID.'),
                                dcc.Interval(id='vbss-creation-interval', interval=300, n_intervals=0),
                                html.Div(id="vbss-creation-output", children='Press Transition to begin station transition.'),
                                html.Button('Create VBSS', id='vbss-creation-submit', n_clicks=0),
                                html.Br(),
                                html.Br(),
                                dcc.Markdown(d("""
                                **Move VBSS**
                                """)),
                                dcc.Input(id='vbss-move-ssid', type='text', placeholder='Destination SSID'),
                                dcc.Input(id='vbss-move-password', type='text', placeholder='Destination password'),
                                dcc.Dropdown(options=[], id='vbss-move-client-mac', placeholder='Select a station'),
                                dcc.Dropdown(options=[], id='vbss-move-dest-ruid', placeholder='Select a destination RUID'),
                                dcc.Interval(id='vbss-move-interval', interval=100, n_intervals=0),
                                html.Button('Move', id='vbss-move-btn', n_clicks=0),
                                html.Div(id='vbss-move-output', children='Click move'),
                                dcc.Markdown(d("""
                                **Destroy VBSS**
                                """)),
                                daq.BooleanSwitch(id='vbss-destruction-disassociate', label='Disassociate Clients?', on=True),
                                dcc.Dropdown(options=[], id='vbss-destruction-bssid', placeholder='Select a VBSSID to destroy.'),
                                html.Button('Destroy', id='vbss-destruction-submit', n_clicks=0),
                                html.Div(id='vbss-destruction-output', children='Click destroy'),
                            ],
                            style={'height': '300px'}
                        ),
                    ]
                ),
                html.Div(
                    className="eight columns",
                    children=[
                        html.Div(
                            className="twelve columns",
                            children=[dcc.Graph(id="my-graph",
                                                figure=network_graph(get_topology()), animate=True, config={'displayModeBar': True}),
                                    dcc.Interval(id='graph-interval', interval=3000, n_intervals=0)],
                            style={'height': '800px'}
                        ),
                        html.Div(
                            className="twelve columns",
                            children=[dcc.Graph(id="rssi-plot",
                                    figure=dict(
                                        layout=dict(
                                        )
                                    ), config={'displayModeBar': True}),
                                    dcc.Interval(id='rssi-plot-interval', interval=500, n_intervals=0)],
                        ),
                    ]
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
    return layout

if __name__ == '__main__':
    config_parser = configparser.ConfigParser()
    config_parser.read("config.ini")
    # Silence imported module logs
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, datefmt='%Y-%m-%d_%H:%M:%S')
    app.layout = gen_app_layout(config_parser)
    app.title = get_app_title(config_parser)
    debug: str = config_parser.getboolean('server', 'debug')
    host: str  = config_parser.get('server', 'host', fallback='localhost')
    port: str = config_parser.get('server', 'port', fallback='8000')
    logging.debug(f"Running, config opts: debug: {debug} host: {host} port: {port}")
    app.run_server(debug=debug, host=host, port=port)
    if nbapi_thread:
        nbapi_thread.quit()
