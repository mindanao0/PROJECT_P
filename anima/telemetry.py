"""Read local Linux status without cloud services."""
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
import shutil
import subprocess
import time

import psutil


@dataclass
class Snapshot:
    cpu: float = 0.0
    cores: list[float] = field(default_factory=list)
    ram_used: float = 0.0
    ram_total: float = 0.0
    swap_used: float = 0.0
    disk_read: float = 0.0
    disk_write: float = 0.0
    net_down: float = 0.0
    net_up: float = 0.0
    gpu: float | None = None
    gpu_name: str = "GPU sensor unavailable"
    processes: list[tuple[str, float, float]] = field(default_factory=list)
    updated: float = 0.0


class LocalTelemetry:
    """Poll psutil and optional NVIDIA telemetry on the local machine."""

    def __init__(self, refresh_seconds: float = 1.0) -> None:
        self.refresh_seconds = refresh_seconds
        self.snapshot = Snapshot()
        self._last_poll = 0.0
        self._last_counters = None
        self._last_counter_time = time.monotonic()
        self._gpu_future: Future | None = None
        self._gpu_value: float | None = None
        self._gpu_name = "GPU sensor unavailable"
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="anima-gpu")
        self._nvidia_smi = shutil.which("nvidia-smi")
        psutil.cpu_percent(interval=None, percpu=True)

    def update(self, now: float | None = None) -> Snapshot:
        now = time.monotonic() if now is None else now
        self._read_gpu_result()
        if now - self._last_poll < self.refresh_seconds:
            return self.snapshot
        self._last_poll = now
        snap = Snapshot()
        snap.gpu, snap.gpu_name = self._gpu_value, self._gpu_name
        snap.cpu = psutil.cpu_percent(interval=None)
        snap.cores = psutil.cpu_percent(interval=None, percpu=True)
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        snap.ram_used, snap.ram_total = memory.used, memory.total
        snap.swap_used = swap.used
        io = psutil.disk_io_counters()
        net = psutil.net_io_counters()
        counters = (io.read_bytes if io else 0, io.write_bytes if io else 0,
                    net.bytes_recv if net else 0, net.bytes_sent if net else 0)
        elapsed = max(.001, now - self._last_counter_time)
        if self._last_counters:
            delta = [max(0, after - before) / elapsed for before, after in zip(self._last_counters, counters)]
            snap.disk_read, snap.disk_write, snap.net_down, snap.net_up = delta
        self._last_counters, self._last_counter_time = counters, now
        snap.processes = self._processes()
        snap.updated = now
        self.snapshot = snap
        self._schedule_gpu_read()
        return self.snapshot

    @staticmethod
    def _processes() -> list[tuple[str, float, float]]:
        found = []
        for proc in psutil.process_iter(("name", "memory_info", "cpu_percent")):
            try:
                info = proc.info
                memory = info["memory_info"].rss if info.get("memory_info") else 0
                found.append((info.get("name") or "process", float(info.get("cpu_percent") or 0), float(memory)))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return sorted(found, key=lambda item: item[1], reverse=True)[:5]

    def _schedule_gpu_read(self) -> None:
        if self._nvidia_smi and (self._gpu_future is None or self._gpu_future.done()):
            self._gpu_future = self._executor.submit(self._query_nvidia)

    def _read_gpu_result(self) -> None:
        if self._gpu_future is not None and self._gpu_future.done():
            try:
                value = self._gpu_future.result()
                self._gpu_value, self._gpu_name = value
            except Exception:
                self._gpu_value, self._gpu_name = None, "GPU sensor unavailable"

    def _query_nvidia(self) -> tuple[float | None, str]:
        result = subprocess.run([self._nvidia_smi, "--query-gpu=utilization.gpu,name", "--format=csv,noheader,nounits"],
                                check=True, capture_output=True, text=True, timeout=.5)
        fields = [field.strip() for field in result.stdout.strip().split(",", 1)]
        return float(fields[0]), fields[1] if len(fields) > 1 else "NVIDIA GPU"

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
