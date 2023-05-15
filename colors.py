# pylint: disable=line-too-long

"""
A simple color synchronization module for assigning colors to agents.

The `ColorSync` class provides a way to assign colors to agents based on their MAC addresses. The module maintains a fixed set of colors and cycles through them when new agents are added. The default color can be specified when creating a `ColorSync` instance.

Example usage:
    cs = ColorSync(default_agent_color='purple')
    cs.add_agent('11:22:33:44:55:66')
    color = cs.get_color_for_agent('11:22:33:44:55:66')

Classes:
    ColorSync: A class for managing color assignments to agents.

Attributes:
    None

Methods:
    __init__(default_agent_color: str) -> None: Initializes a new `ColorSync` instance with a default color.
    get_color_for_agent(agent_mac: str) -> str: Returns the color assigned to the specified agent.
    add_agent(agent_mac: str) -> None: Assigns a color to a new agent based on the cycle of available colors.
    knows_agent(agent_mac: str) -> bool: Checks if the specified agent is known to the `ColorSync` instance.
"""

from typing import List

class ColorSync:
    """
    A color synchronization class for assigning colors to agents.

    The `ColorSync` class provides a way to assign colors to agents based on their MAC addresses. The module maintains a fixed set of colors and cycles through them when new agents are added. The default color can be specified when creating a `ColorSync` instance.

    Example usage:
        cs = ColorSync(default_agent_color='purple')
        cs.add_agent('11:22:33:44:55:66')
        color = cs.get_color_for_agent('11:22:33:44:55:66')

    Methods:
        __init__(default_agent_color: str) -> None:
            Initializes a new `ColorSync` instance with a default color.

        get_color_for_agent(agent_mac: str) -> str:
            Returns the color assigned to the specified agent. If the agent is not yet known to the `ColorSync` instance, the default color will be returned.

        add_agent(agent_mac: str) -> None:
            Assigns a color to a new agent based on the cycle of available colors.

        knows_agent(agent_mac: str) -> bool:
            Checks if the specified agent is known to the `ColorSync` instance.
    """
    def __init__(self, default_agent_color: str)-> None:
        self.colors = ['purple', 'green', 'orange', 'black']
        self.agent_color_map = {}
        self.color_idx = 0
        self.default_agent_color = default_agent_color

    def get_color_for_agent(self, agent_mac: str) -> str:
        """
        Returns the color assigned to the specified agent.

        If the agent is not yet known to the `ColorSync` instance, the default color will be returned.

        Arguments:
        - agent_mac (str): The MAC address of the agent to get the color for.

        Returns:
        - str: The color assigned to the agent, or the default color if the agent is not yet known to the `ColorSync` instance.
        """
        if agent_mac not in self.agent_color_map:
            return self.default_agent_color
        return self.agent_color_map[agent_mac]

    def add_agent(self, agent_mac: str) -> None:
        """
        Adds a new agent to the `ColorSync` instance and assigns a color to it.

        The color is chosen from a pre-defined list of colors, and each agent is assigned a unique color.
        If the list of colors is exhausted, the method will start again from the beginning of the list.

        Arguments:
        - agent_mac (str): The MAC address of the agent to add.

        Returns:
        - None
        """
        self.agent_color_map[agent_mac] = self.colors[self.color_idx]
        self.color_idx = (self.color_idx + 1) % len(self.colors)

    def knows_agent(self, agent_mac: str) -> bool:
        """
        Checks if the specified agent is known to the `ColorSync` instance.

        Returns `True` if the agent is known, `False` otherwise.

        Arguments:
        - agent_mac (str): The MAC address of the agent to check.

        Returns:
        - bool: `True` if the agent is known, `False` otherwise.
        """
        return agent_mac in self.agent_color_map

    def get_color_list(self) -> List[str]:
        """Gets this instances' color list.

        Returns:
            List[str]: The list of color strings that this color sync instance has.
        """
        return self.colors
