"""OpenGL renderer: graph edges, subsystem nodes, and packet highlights."""
from __future__ import annotations

import math
import numpy as np
import pygame
from OpenGL.GL import *

from .graph import ANIMA_GROUP, GROUPS, NodeGraph
from .simulation import Traffic
from .telemetry import Snapshot


WIDTH, HEIGHT = 1440, 900
BG = (0.012, 0.024, 0.038)


class GpuView:
    def __init__(self, graph: NodeGraph, traffic: Traffic, title: str = "ANIMA · SYSTEM GRAPH") -> None:
        pygame.init()
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 2)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 1)
        pygame.display.gl_set_attribute(pygame.GL_DOUBLEBUFFER, 1)
        flags = pygame.OPENGL | pygame.DOUBLEBUF | pygame.RESIZABLE
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), flags, vsync=1)
        pygame.display.set_caption(title)
        self.graph, self.traffic = graph, traffic
        self.font = pygame.font.SysFont("monospace", 15)
        self.small = pygame.font.SysFont("monospace", 12)
        self.width, self.height = WIDTH, HEIGHT
        self.start = pygame.time.get_ticks() / 1000
        self.label_cache: dict[tuple[str, tuple[int, int, int]], int] = {}
        self.texture_lru: list[tuple[str, tuple[int, int, int]]] = []
        self._set_projection()

    def _set_projection(self) -> None:
        self.width, self.height = self.screen.get_size()
        glViewport(0, 0, self.width, self.height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0, 1, 1, 0, -2, 2)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_POINT_SMOOTH)

    def draw(self, snapshot: Snapshot) -> None:
        now = pygame.time.get_ticks() / 1000 - self.start
        w, h = self.width, self.height
        graph = self.graph
        traffic = self.traffic
        glClearColor(*BG, 1)
        glClear(GL_COLOR_BUFFER_BIT)
        glLoadIdentity()

        points = [graph.point(i, traffic.clock, traffic.activity) for i in range(len(graph.nodes))]
        active = traffic.active_edges()
        line_positions: list[tuple[float, float, float]] = []
        line_colors: list[tuple[float, float, float, float]] = []
        for edge in graph.edges:
            color = GROUPS[edge.group].color if edge.group < ANIMA_GROUP else self._core_color(graph.nodes[edge.a].u)
            pulse = active.get((min(edge.a, edge.b), max(edge.a, edge.b)))
            rgba = (*pulse[0], .98) if pulse else (*color, .20 if edge.kind == "bridge" else .115 if edge.kind == "anima" else .17)
            curve = graph.edge_curve(edge.a, edge.b, traffic.clock, traffic.activity)
            steps = 12 if edge.kind == "bridge" else 5 if edge.kind == "anima" else 1
            previous = curve(0)
            for j in range(1, steps + 1):
                current = curve(j / steps)
                line_positions.extend((previous, current))
                line_colors.extend((rgba, rgba))
                previous = current
        self._draw_arrays(GL_LINES, line_positions, line_colors)

        node_positions = [(p[0], p[1], p[2] * .1) for p in points]
        node_colors = []
        for node in graph.nodes:
            color = GROUPS[node.group].color if node.group < ANIMA_GROUP else self._core_color(node.u)
            node_colors.append((*color, .44 + .35 * (node.z + .5)))
        self._draw_arrays(GL_POINTS, node_positions, node_colors, point_size=2.8)

        packets = traffic.packet_positions()
        packet_positions = [(x, y, 0) for x, y, _, _ in packets]
        packet_colors = [(*color, alpha) for _, _, color, alpha in packets]
        self._draw_arrays(GL_POINTS, packet_positions, packet_colors, point_size=9)

        self._draw_hud(snapshot, packets, now)
        pygame.display.flip()

    @staticmethod
    def _core_color(u: float) -> tuple[float, float, float]:
        warm = max(0.0, math.cos(u + .5)) ** 3
        return .42 + .58 * warm, .69 + .23 * warm, .9 - .45 * warm

    @staticmethod
    def _draw_arrays(mode: int, positions, colors, point_size: float = 1.0) -> None:
        if not positions:
            return
        vertices = np.ascontiguousarray(positions, dtype=np.float32)
        rgba = np.ascontiguousarray(colors, dtype=np.float32)
        glEnableClientState(GL_VERTEX_ARRAY)
        glEnableClientState(GL_COLOR_ARRAY)
        glVertexPointer(3, GL_FLOAT, 0, vertices)
        glColorPointer(4, GL_FLOAT, 0, rgba)
        if mode == GL_POINTS:
            glPointSize(point_size)
        glDrawArrays(mode, 0, len(vertices))
        glDisableClientState(GL_VERTEX_ARRAY)
        glDisableClientState(GL_COLOR_ARRAY)

    def _text(self, text: str, x: float, y: float, color=(207, 226, 239), font=None) -> None:
        key = (text, color)
        texture = self.label_cache.get(key)
        if texture is None:
            font = font or self.small
            surface = font.render(text, True, color)
            rgba = pygame.image.tostring(surface, "RGBA", True)
            texture = glGenTextures(1)
            glBindTexture(GL_TEXTURE_2D, texture)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, surface.get_width(), surface.get_height(), 0, GL_RGBA, GL_UNSIGNED_BYTE, rgba)
            self.label_cache[key] = texture
            self.texture_lru.append(key)
            if len(self.texture_lru) > 420:
                oldest = self.texture_lru.pop(0)
                glDeleteTextures([self.label_cache.pop(oldest)])
        surface = (font or self.small).render(text, True, color)
        glBindTexture(GL_TEXTURE_2D, texture)
        glEnable(GL_TEXTURE_2D)
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        tw, th = surface.get_width() / self.width, surface.get_height() / self.height
        glTexCoord2f(0, 1); glVertex2f(x, y)
        glTexCoord2f(1, 1); glVertex2f(x + tw, y)
        glTexCoord2f(1, 0); glVertex2f(x + tw, y + th)
        glTexCoord2f(0, 0); glVertex2f(x, y + th)
        glEnd()
        glDisable(GL_TEXTURE_2D)

    def _rule(self, x1: float, y1: float, x2: float, y2: float, color=(30, 51, 66)) -> None:
        glColor4ub(*color, 255)
        glBegin(GL_LINES)
        glVertex2f(x1, y1); glVertex2f(x2, y2)
        glEnd()

    def _draw_hud(self, snapshot: Snapshot, packets, now: float) -> None:
        self._rule(.018, .105, .982, .105)
        self._text("ANIMA / NODE FLOW", .025, .030, (222, 240, 249), self.font)
        self._text("LOCAL GPU RENDER · FEDORA", .73, .035, (130, 163, 183))
        metrics = [
            ("CPU", f"{snapshot.cpu:4.0f}%", (120, 205, 255)),
            ("RAM", f"{snapshot.ram_used/2**30:4.1f}/{snapshot.ram_total/2**30:.0f} GiB", (104, 237, 190)),
            ("GPU", f"{snapshot.gpu:4.0f}%" if snapshot.gpu is not None else "--", (255, 190, 99)),
            ("DISK R/W", f"{snapshot.disk_read/2**20:.1f}/{snapshot.disk_write/2**20:.1f} MiB/s", (219, 190, 255)),
            ("NET ↓/↑", f"{snapshot.net_down/2**20:.1f}/{snapshot.net_up/2**20:.1f} MiB/s", (117, 224, 237)),
        ]
        for i, (label, value, color) in enumerate(metrics):
            x = .025 + i * .194
            self._text(label, x, .063, tuple(int(c * 255) for c in color))
            self._text(value, x + .055, .061, (221, 237, 246))

        # Device-cluster names sit beside their actual node webs.
        label_positions = ((.20, .305), (.79, .305), (.88, .625), (.77, .955), (.23, .955), (.12, .625))
        for group, (x, y) in zip(GROUPS, label_positions):
            col = tuple(int(c * 255) for c in group.color)
            self._text(group.label, x - .025, y, col)

        self._text("ANIMA", .49, .455, (222, 239, 248), self.font)
        self._text(f"{sum(1 for x, _, _, _ in packets if .36 < x < .66)} ROUTES IN CORE", .455, .482, (157, 190, 208))

        y = .875
        self._rule(.018, y - .012, .982, y - .012)
        title, _, unknown = __import__("anima.simulation", fromlist=["SCENARIOS"]).SCENARIOS[self.traffic.mode]
        route = "Processes → ANIMA → internal node path → fade" if unknown else self._route_text(self.traffic.mode)
        self._text(f"SAMPLE FLOW  {route}", .025, y + .006, (210, 231, 243))
        if snapshot.processes:
            names = "  ·  ".join(f"{name} {cpu:.0f}%" for name, cpu, _ in snapshot.processes[:4])
            self._text(f"TOP PROCESSES  {names}", .025, .925, (133, 161, 180))
        self._text(f"{title.upper()} · SIMULATED ROUTING", .70, .925, (147, 178, 197))

    @staticmethod
    def _route_text(mode: str) -> str:
        return {
            "read": "Storage → ANIMA → RAM → ANIMA → Processes → ANIMA → CPU",
            "gpu": "CPU → ANIMA → RAM → ANIMA → GPU",
            "download": "Network → ANIMA → RAM → ANIMA → Storage",
        }.get(mode, "")

    def close(self) -> None:
        for texture in self.label_cache.values():
            glDeleteTextures([texture])
        pygame.quit()
