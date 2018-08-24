from abc import ABC


class CheatEngine(ABC):
    def __init__(self, memory):
        self._memory = memory


class SpaceInvadersCheatEngine(CheatEngine):
    def hack_kill_player(self):
        self._memory[0x2015] = 0

    def hack_kill_mobs(self):
        diff = 0x2136 - 0x2100
        self._memory[0x2100:0x2136] = [0] * diff

    def hack_add_lives(self):
        self._memory[0x21FF] = 7

    def hack_score(self):
        self._memory[0x20F1] = 1
        self._memory[0x20F2] = 255
        self._memory[0x20F3] = 255
