

class ColorSync:
    def __init__(self, default_agent_color: str)-> None:
        self.colors = ['purple', 'green', 'orange', 'black']
        self.agent_color_map = {}
        self.color_idx = 0
        self.default_agent_color = default_agent_color
    def get_color_for_agent(self, agent_mac: str) -> str:
        if agent_mac not in self.agent_color_map:
            return self.default_agent_color
        return self.agent_color_map[agent_mac]
    def add_agent(self, agent_mac: str) -> None:
        self.agent_color_map[agent_mac] = self.colors[self.color_idx]
        self.color_idx = (self.color_idx + 1) % len(self.colors)
    def knows_agent(self, agent_mac: str) -> bool:
        return agent_mac in self.agent_color_map.keys()

