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
import plotly.graph_objs as go
import requests
from dash import Dash, Input, Output, State, dcc, html
import dash_daq as daq
from networkx.drawing.nx_pydot import graphviz_layout
from PIL import Image

import validation
from easymesh import (BSS, ORIENTATION, Agent, Interface, Neighbor, Radio,
                      Station, UnassociatedStation)
from path_parser import parse_index_from_path_by_key
from topology import Topology
from nbapi_rpc import *
from controller_ctx import ControllerConnectionCtx
from http_auth import HTTPBasicAuthParams
from colors import ColorSync

app = Dash(__name__)
app.title = 'CableLabs EasyMesh Network Monitor'

g_StationsToRadio = {}
class NodeType(Enum):
    UNKNOWN = 0
    STATION = 1
    AGENT = 2
    CONTROLLER = 3

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
    x_distance = 14 # Distance between two interface markers
    x_min = 20      # Distance between the agent marker and the interface marker
    y_distance = 7
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
        marker_references.append(i.get_hash_id())
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

def get_color_for_agent(color_selector: ColorSync, agent: Agent) -> str:
    """Gets a color string for a given agent.

    Args:
        color_selector (ColorSync): The color selector
        agent (Agent): The Agent to get a color for

    Returns:
        str: The string representation of the color to be used for rendering (e.g. 'purple')
    """
    agent_mac = agent.get_id()
    if not color_selector.knows_agent(agent_mac):
        color_selector.add_agent(agent_mac)
    return color_selector.get_color_for_agent(agent_mac)

g_ColorSync = ColorSync('green')
# Agent MAC -> Shape type, for blinking.
g_RenderState = {}
def was_last_rendered_as_open_circle(agent: Agent) -> bool:
    if agent.get_id() in g_RenderState:
        return g_RenderState[agent.get_id()] == 'circle-open'

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

    G = nx.Graph()

    marker_references.clear()
    marker_references.append(topology.controller.get_hash_id())
    G.add_node(topology.controller.get_hash_id())
    G.nodes()[topology.controller.get_hash_id()]['type'] = NodeType.CONTROLLER
    #G.nodes()[topology.controller.get_hash_id()]['params'] = topology.controller.params
    add_children_to_graph_recursive(topology.controller, G)

    # Add edges/connections between agents (builds general graph)
    for agent in topology.agents:
        for ifc in agent.get_interfaces():
            for child_iface in ifc.get_children():
                if not child_iface.get_children():
                    G.add_edge(child_iface.get_parent_agent().get_hash_id(), ifc.get_parent_agent().get_hash_id())
                    # G.nodes()[child_iface.get_parent_agent().get_hash_id()]['type'] = NodeType.AGENT
                    # G.nodes()[ifc.get_parent_agent().get_hash_id()]['type'] = NodeType.AGENT

            if ifc.get_connected_stations():
                for sta in ifc.get_connected_stations():
                    G.add_edge(sta.get_hash_mac(), ifc.get_parent_agent().get_hash_id())
                    # G.nodes()[sta.get_hash_mac()]['type'] = NodeType.STATION
                    # G.nodes()[ifc.get_parent_agent().get_hash_id()]['type'] = NodeType.AGENT

    pos = graphviz_layout(G, prog="dot")

    # DEBUG: Calculate position range of the graphed nodes
    # x_axis_range = [min(pos.values(), key=lambda x: x[0])[0], max(pos.values(), key=lambda x: x[0])[0] ]
    # y_axis_range = [min(pos.values(), key=lambda x: x[1])[1], max(pos.values(), key=lambda x: x[1])[1] ]

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
        # if not G.nodes[node]['type']:
        #     G.nodes[node]['type'] = NodeType.STATION
        global g_RenderState
        shape_type = 'circle'
        if G.nodes[node]['type'] == NodeType.AGENT or G.nodes[node]['type'] == NodeType.CONTROLLER:
            agent = topology.get_agent_from_hash(node)
            if len(agent.get_connected_stations()) == 0:
                # No connected stations, don't blink.
                shape_type = 'circle'
            else:
                if not was_last_rendered_as_open_circle(agent):
                    shape_type = 'circle-open'
                    g_RenderState[agent.get_id()] = shape_type
                else:
                    shape_type = 'circle'
                    g_RenderState[agent.get_id()] = shape_type
        node_hover_text.append(gen_node_text(g_Topology, node, G.nodes[node]['type']))
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
    for a in g_Topology.get_agents():
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
    #print(f'X axis range: {x_range}  - Y axis range: {y_range}')

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
                            html.Br(),
                            html.Br(),
                            dcc.Markdown(d("""
                            **HTTP Basic Auth Params**

                            Username and password for the HTTP proxy.
                            """)),
                            dcc.Input(id='httpauth_user', type='text', placeholder='admin', value='admin'),
                            dcc.Input(id='httpauth_pass', type='text', placeholder='admin', value='admin'),
                            html.Button('Submit', id='submit-val', n_clicks=0),
                            html.Div(id="output", children='Press Submit to connect'),
                            html.Br(),
                            dcc.Markdown(d("""
                            **Easymesh credentials**

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
                                            figure=network_graph(g_Topology), animate=True, config={'displayModeBar': True}),
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

# RUID -> STA_MAC -> [RSSI measurements]
g_RSSI_Measurements = {}

stations_have_moved = []
def handle_station_moved(sta: Station, radio: Radio) -> None:
    logging.debug(f"Station {sta.get_mac()} has moved! From {g_StationsToRadio[sta.get_mac()]} to {radio.get_ruid()}")
    stations_have_moved.append(sta.get_mac())

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
        return Topology({}, {})

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
                            if radio.params['ID'] == iface.params['MACAddress']:
                                bss.interface = iface
                                break
                            # if e['parameters']['BSSID'] == iface.params['MACAddress']:
                            #    bss.interface = iface
                            #    break

    # 7. Map Stations to the BSS they're connected to.
    station_list: List[Station] = []
    for e in nbapi_json:
        if re.search(r"\.STA\.\d{1,10}\.$", e['path']):
            for agent in agent_list:
                for radio in agent.get_radios():
                    for bss in radio.get_bsses():
                        if e['path'].startswith(bss.path):
                            sta = Station(e['path'], e['parameters'])
                            station_list.append(sta)
                            bss.add_connected_station(sta)
                            if sta.get_mac() in g_StationsToRadio and g_StationsToRadio[sta.get_mac()] != radio.get_ruid():
                                handle_station_moved(sta, radio)
                                del g_StationsToRadio[sta.get_mac()]
                            g_StationsToRadio[sta.get_mac()] = radio.get_ruid()
                            bss.interface.orientation = ORIENTATION.DOWN
                            # Exclude stations that are actually agents
                            if not bss.interface.get_parent_agent().is_child(sta.get_mac()): #if not bss.interface.is_child(sta.get_mac()):
                                bss.interface.add_connected_station(sta)
                            # Append RSSI measurements.
                            if radio.get_ruid() not in g_RSSI_Measurements:
                                g_RSSI_Measurements[radio.get_ruid()] = {}
                            else:
                                if sta.get_mac() not in g_RSSI_Measurements[radio.get_ruid()]:
                                    g_RSSI_Measurements[radio.get_ruid()][sta.get_mac()] = []
                                else:
                                    g_RSSI_Measurements[radio.get_ruid()][sta.get_mac()].append(sta.get_rssi())

    # 8. Check and set stations steering history
    for e in nbapi_json:
        if re.search(r"\.SteerEvent\.\d{1,10}\.$", e['path']):
            for station in station_list:
                if station.params["MACAddress"] == e["parameters"]["DeviceId"] and e["parameters"]["Result"] == "Success":
                    station.set_steered(True)

    for e in nbapi_json:
        if re.search(r"\.UnassociatedSTA\.\d{1,10}\.$", e['path']):
            for agent in agent_list:
                for radio in agent.get_radios():
                    if e['path'].startswith(radio.path):
                        unassoc_sta = UnassociatedStation(e['path'], e['parameters'])
                        unassoc_sta.set_parent_radio(radio)
                        if radio.get_ruid() not in g_RSSI_Measurements:
                            g_RSSI_Measurements[radio.get_ruid()] = {}
                        else:
                            if unassoc_sta.get_mac() not in g_RSSI_Measurements[radio.get_ruid()]:
                                g_RSSI_Measurements[radio.get_ruid()][unassoc_sta.get_mac()] = []
                            else:
                                g_RSSI_Measurements[radio.get_ruid()][unassoc_sta.get_mac()].append(e['parameters']['SignalStrength'])

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

            # DEBUG: Load previously dumped JSON response
            # with open("Datamodel_JSON_dumps/test_dump.json", 'r') as f:
            #     nbapi_root_json_blob = json.loads(f.read())

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
def connect_to_controller(n_clicks: int, ip: str, port: str, httpauth_u: str, httpauth_pw: str):
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

@app.callback(Output('easymesh_ssid', 'value'),Input('transition-interval', 'n_intervals'))
def update_prplmesh_ssid(unused):
    return g_Topology.get_ssid()

@app.callback(Output('vbss-creation-client-mac', 'options'),
              Input('vbss-creation-interval', 'n_intervals')
)
def update_stations(_):
    """Populates the available station list for the client MAC field of a VBSS creation request.
    """
    return [sta.get_mac() for sta in g_Topology.get_stations()]

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

@app.callback(Output('vbss-move-client-mac', 'options'),
              Input('vbss-move-interval', 'n_intervals')
)
def update_vbss_move_client_mac(_):
    """Populate the client MAC dropdown for VBSS moves.
    """
    return [sta.get_mac() for sta in g_Topology.get_stations()]

@app.callback(Output('vbss-destruction-bssid', 'options'),
              Input('vbss-move-interval', 'n_intervals')
)
def update_vbss_destruction_bssid_dropdown(_):
    """Populates the VBSSID dropdown selection for the Destroy component.
    """

    # TODO: the below commented-out code should be the only code in this function.
    # Currently, prplMesh does not populate the 'IsVBSS' field correctly for virtual BSSes.
    # return [bss.get_bssid() for bss in g_Topology.get_bsses() if bss.is_vbss()]

    return [bss.get_bssid() for bss in g_Topology.get_bsses()]

@app.callback(Output('vbss-move-dest-ruid', 'options'),
              Input('vbss-move-interval', 'n_intervals')
)
def update_vbss_move_ruid_dropdown(_):
    """Populate the destination RUID dropdown for VBSS moves.
    """
    return [radio.get_ruid() for radio in g_Topology.get_radios()]

@app.callback(Output('vbss-creation-ruid', 'options'),
              Input('vbss-creation-interval', 'n_intervals')
)
def update_vbss_creation_ruid_dropdown(_):
    """Populates the RUID dropdown field for creating a VBSS.
    """
    return [radio.get_ruid() for radio in g_Topology.get_radios()]

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
    clicked_point = clickData['points'][0]
    if 'customdata' not in clicked_point:
        return "Node data not available"
    node_hash = clicked_point['customdata']
    agent = g_Topology.get_agent_from_hash(node_hash)
    if agent:
        return json.dumps(agent.params, indent=2)

    sta = g_Topology.get_station_from_hash(node_hash)
    if sta:
        logging.debug("Station clicked!")
        set_last_clicked_station(sta)
        return json.dumps(sta.params, indent=2)

    interface = g_Topology.get_interface_from_hash(node_hash)
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
    bssid = g_Topology.get_bssid_connection_for_sta(client_mac)
    bss = g_Topology.get_bss_by_bssid(bssid)
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
    is_client_mac_valid, client_mac_error = validation.validate_vbss_client_mac(client_mac, g_Topology)
    if not is_client_mac_valid:
        return f"Client MAC invalid: {client_mac_error}"
    is_vbssid_valid, vbssid_error = validation.validate_vbss_vbssid(vbssid, g_Topology)
    if not is_vbssid_valid:
        return f"VBSSID invalid: {vbssid_error}"
    radio = g_Topology.get_radio_by_ruid(ruid)
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
    bss = g_Topology.get_bss_by_bssid(bssid)
    if not bss:
        return f"Could not find a BSS for BSSID '{bssid}'"
    dummy_client_mac_addr = "aa:bb:cc:dd:ee:ff"
    send_vbss_destruction_request(g_ControllerConnectionCtx, dummy_client_mac_addr, should_disassociate, bss)
    return f"Sent VBSS destruction request for '{bssid}'"


def sta_has_moved(sta_mac: str) -> bool:
    ret = False
    if sta_mac in stations_have_moved:
        ret = True
        stations_have_moved.remove(sta_mac)
    return ret

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
    global RSSI_RELATIVE_TO_RADIO
    station_of_interest = get_last_clicked_station()
    if not station_of_interest:
        # Log that there's no station selected once.
        if (n_intervals == 0):
            logging.debug("No station!")
        return dict()
    selected_sta_mac = station_of_interest.get_mac()
    # Store as a static variable so we can clear the RSSI table when a new station is selected.
    if update_rssi_plot.last_sta == None:
        update_rssi_plot.last_sta = station_of_interest
    if update_rssi_plot.last_sta.get_mac() != selected_sta_mac:
        logging.debug(f"New station clicked ({selected_sta_mac}), resetting plot data")
        update_rssi_plot.last_sta = station_of_interest
    

    fig = go.Figure()

    unassoc_color_lut = {}
    for key in g_RSSI_Measurements.items():
        radio_mac = key[0]
        agent = g_Topology.get_agent_by_ruid(radio_mac)
        unassoc_color_lut[radio_mac] = get_color_for_agent(g_ColorSync, agent)

    # We need to render curves starting at the most recent move, instead of t=0
    initial_x_offset = 0
    for ruid, sta_list in g_RSSI_Measurements.items():
        for sta_mac, measurement_list in sta_list.items():
            if sta_mac == selected_sta_mac:
                y_axis_vals = measurement_list
                a = max(len(measurement_list), 500)
                x_axis_vals = list(range(initial_x_offset, a))
                trace_name = f"STA {station_of_interest.params['Hostname']} ({selected_sta_mac}) relative to radio {ruid}"
                trace = go.Scatter(x=x_axis_vals, y=y_axis_vals, marker=dict(color=unassoc_color_lut[ruid]), name=trace_name, mode="lines", hoverinfo="all")
                fig.add_trace(trace)
                if sta_has_moved(sta_mac):
                    logging.debug(f"station has moved, drawing vertical marker.")
                    if sta_mac not in g_Transition_X_Positions:
                        g_Transition_X_Positions[sta_mac] = []
                    pos = len(measurement_list) - 1
                    g_Transition_X_Positions[sta_mac].append(pos)
                    trace_name = f"VBSS move for STA {sta_mac}" 

    # Must render each VBSS move every render cycle to maintain VBSS move history in the plot.
    for station_mac, move_list in g_Transition_X_Positions.items():
        if station_mac == selected_sta_mac:
            for move_position in move_list:
                logging.debug(f"move for STA {sta_mac} happened at {move_position}")
                fig.add_vline(x=move_position, line_width=3, line_dash='dash', line_color='black')
    return fig
# Init callback function attribute (static)
update_rssi_plot.last_sta = None

if __name__ == '__main__':
    # Silence imported module logs
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("PIL.PngImagePlugin").setLevel(logging.WARNING)
    logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.DEBUG, datefmt='%Y-%m-%d_%H:%M:%S')
    app.run_server(debug=True)
    if nbapi_thread:
        nbapi_thread.quit()
