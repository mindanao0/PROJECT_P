# ANIMA — local system graph

ANIMA is a Fedora desktop prototype for a system monitor whose main view is a live node graph. Every subsystem owns a dense local node network. Twenty-four separate edges from each subsystem join nodes on the central ANIMA torus; task packets follow graph edges into the core and onward to another subsystem. The core has its own 384 connected surface nodes and bends in response to activity routed through it.

The app renders with the machine's OpenGL driver. It needs no hosted model, cloud service, or API key. CPU, memory, disk, network, process, and NVIDIA GPU readings come from the local machine. Animated task paths are labeled as examples because ordinary utilization counters do not reveal the real causal path between devices.

## Run on Fedora

Install Python and the desktop's OpenGL driver, then:

```bash
chmod +x run.sh
./run.sh
```

`run.sh` creates a project virtual environment, installs the pinned-range Python dependencies from `requirements.txt`, and starts the renderer. It requires a graphical desktop session. Fedora's system Python stays untouched.

The renderer uses SDL through `pygame-ce`, PyOpenGL for OpenGL drawing, NumPy for batched GPU vertices, and `psutil` for local system readings. NVIDIA utilization is shown when `nvidia-smi` is available. On other GPUs the GPU utilization field stays `--`; the node graph still renders on the active OpenGL device.

## Controls

| Key | Action |
| --- | --- |
| `1` | Simulate reading storage through RAM and processes into CPU |
| `2` | Simulate a CPU/RAM/GPU job |
| `3` | Simulate a network download to storage |
| `4` | Send an unknown process route into ANIMA, then fade it inside the core |
| `Space` | Pause or resume graph and packets |
| `Esc` or `Q` | Quit |

The colored webs identify CPU, RAM, GPU, storage, processes, network, and ANIMA. Inactive links remain dim. Packets brighten the exact local edges and central surface edges they traverse. The center changes shape while packets are inside it. Screen labels show local telemetry; scenario routes remain marked as simulated.

## Development

Run the graph and routing tests without launching the window:

```bash
python3 -m unittest discover -s tests -v
```

The tests verify that each device has distinct paths into the central mesh, every sample route uses actual graph edges, curves meet their nodes, activity changes the ANIMA surface, and unknown routes stay in the center before fading.

## Current scope

This is the local rendering and interaction prototype. It reads common host counters and NVIDIA utilization when available. Device-specific AMD/Intel GPU metrics, sensor permissions and discovery, and process-to-device causal tracing need hardware-specific backends; the sample animations do not claim those paths are measured.
