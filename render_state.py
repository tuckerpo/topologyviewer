# pylint: disable=logging-fstring-interpolation, line-too-long

"""
This module tracks the render states of EasyMesh entities.
"""

import logging
from enum import IntEnum
from easymesh import Agent

logger = logging.getLogger(__name__)

class EnumAgentRenderState(IntEnum):
    """Render state enums for Agents.
    """
    UNKNOWN = -1
    SOLID = 0
    OPEN = 1
    CLOSED = 2

class AgentRenderState():
    """Tracks the render state machine for Agents.
    """
    def __init__(self) -> None:
        self.agent_render_states = {}

    def __get_initial_render_state(self, agent: Agent) -> EnumAgentRenderState:
        if not agent:
            return EnumAgentRenderState.UNKNOWN
        if len(agent.get_connected_stations()) == 0:
            return EnumAgentRenderState.SOLID
        return EnumAgentRenderState.OPEN

    def add_new_agent(self, agent: Agent) -> None:
        """Add a new Agent to this instance. Determines initial render state based on Agent state.

        Args:
            agent (Agent): The Agent to track render state for.
        """
        if not agent:
            return
        agent_id = agent.get_id()
        if agent_id in self.agent_render_states:
            return
        render_state: EnumAgentRenderState = self.__get_initial_render_state(agent)
        self.agent_render_states[agent_id] = render_state

    def get_state(self, agent: Agent) -> EnumAgentRenderState:
        """Get the current render state for a given Agent.

        Args:
            agent (Agent): The Agent to get the current render state for.

        Returns:
            EnumAgentRenderState: The current render state for `agent`
        """
        if not agent:
            return EnumAgentRenderState.UNKNOWN
        agent_id = agent.get_id()
        render_state: EnumAgentRenderState
        if agent_id in self.agent_render_states:
            render_state = self.agent_render_states[agent_id]
            self.__increment_state(agent)
        else:
            render_state = EnumAgentRenderState.UNKNOWN
            logging.warning(f"Agent {agent_id} is unknown!")
        return render_state

    def __increment_state(self, agent: Agent) -> None:
        if not agent:
            return
        agent_id = agent.get_id()
        previous_render_state: EnumAgentRenderState
        new_render_state: EnumAgentRenderState
        if agent_id not in self.agent_render_states:
            return
        previous_render_state = self.agent_render_states[agent_id]
        if previous_render_state == EnumAgentRenderState.OPEN:
            new_render_state = EnumAgentRenderState.CLOSED
        elif previous_render_state == EnumAgentRenderState.CLOSED:
            new_render_state = EnumAgentRenderState.OPEN
        elif previous_render_state == EnumAgentRenderState.UNKNOWN:
            new_render_state = self.__get_initial_render_state(agent)
        elif previous_render_state == EnumAgentRenderState.SOLID:
            new_render_state = self.__get_initial_render_state(agent)
        # Finally, check if there's been any station updates.
        if len(agent.get_connected_stations()) == 0:
            new_render_state = EnumAgentRenderState.SOLID
        self.agent_render_states[agent_id] = new_render_state
