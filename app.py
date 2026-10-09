"""ANIMA's Fedora-local, GPU-rendered node-flow showcase."""
from __future__ import annotations

import sys
import time

from anima.graph import NodeGraph
from anima.gpu_view import GpuView
from anima.simulation import SCENARIOS, Traffic
from anima.telemetry import LocalTelemetry


def main() -> int:
    graph = NodeGraph()
    traffic = Traffic(graph)
    telemetry = LocalTelemetry()
    try:
        view = GpuView(graph, traffic)
    except Exception as exc:
        telemetry.close()
        print("ANIMA could not create an OpenGL window. Install a Fedora Mesa/NVIDIA/AMD OpenGL driver and run from a graphical desktop.", file=sys.stderr)
        print(f"OpenGL error: {exc}", file=sys.stderr)
        return 2

    import pygame

    clock = pygame.time.Clock()
    running = True
    try:
        while running:
            dt = min(clock.tick(60) / 1000.0, .05)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_ESCAPE, pygame.K_q):
                        running = False
                    elif event.key == pygame.K_SPACE:
                        traffic.paused = not traffic.paused
                    elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                        mode = (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4).index(event.key)
                        traffic.select(tuple(SCENARIOS)[mode])
                elif event.type == pygame.VIDEORESIZE:
                    view._set_projection()
            traffic.update(dt)
            snapshot = telemetry.update()
            view.draw(snapshot)
    except KeyboardInterrupt:
        pass
    finally:
        view.close()
        telemetry.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
