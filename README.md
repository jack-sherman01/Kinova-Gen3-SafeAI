# Kinova Gen3 demo workspace

Tools for running demos on a Kinova Gen3 arm with the Kortex Python API: connection checks,
the official examples, a custom home pose, keyboard teleoperation, and drag-and-teach
trajectory recording/replay.

## Contents

```
setup_env.sh               create .venv (Kortex API wheel + protobuf/pygame)
requirements.txt           extra Python deps installed by setup_env.sh
setup_network.sh           static IP 192.168.1.11/24 on the wired NIC, then ping the robot
check_connection.py        read-only check: arm state, devices, joint angles, tool pose
run.sh                     run the official Kortex examples (or any script) with the venv
home.py                    set / go to a workspace home pose (stored in home.json)
home.json                  the saved workspace home pose
teleop.py                  keyboard teleoperation (Cartesian velocity + gripper)
teach.py                   drag-and-teach: record trajectories in admittance mode, replay them
Kinova-kortex2_Gen3_G3L/   official Kortex API repo (git submodule; examples in api_python/examples)
```

All robot scripts accept `--ip`, `-u`, `-p` (defaults `192.168.1.10` / `admin` / `admin`).

## 1. Setup (once per machine)

```bash
git clone --recurse-submodules <this repo> && cd ICLR-Sheng   # or: git submodule update --init
./setup_env.sh
```

`setup_env.sh` creates `.venv` (tested with Python 3.12), downloads `kortex_api-2.6.0.post3` from
Kinova's Artifactory into `wheels/`, and installs it plus `requirements.txt`. kortex_api pins
`protobuf==3.5.1`, which does not work on Python >= 3.10, so 3.20.3 is installed instead; pip prints
a dependency-conflict warning, which is expected.

`home.py`, `teach.py` and `teleop.py` use `.venv` automatically via their shebang (`./teach.py ...`).

## 2. Connect to the robot (each session)

1. Power on the arm and wait until it has booted (~1 min).
2. Connect the Ethernet cable to the **robot base** port and the PC's wired port (`enp131s0`).
3. Run:

```bash
./setup_network.sh          # or ./setup_network.sh <iface> for another interface
./run.sh check              # no motion: prints arm state, devices, joint angles, tool pose
```

The IP is not persistent; rerun `setup_network.sh` after a reboot.
If `ip -br link` shows the interface as `NO-CARRIER`, there is no physical link: check the robot is
powered and booted, the cable, and the port. The Web App is at http://192.168.1.10.

## 3. Official Kortex examples (`run.sh`)

```bash
./run.sh list                                                   # list all examples
./run.sh 111-kinematics/01-compute-kinematics.py
./run.sh 102-Movement_high_level/01-move_angular_and_cartesian.py
./run.sh 102-Movement_high_level/02-sequence.py
./run.sh 106-Gripper_command/01-gripper_command.py
./run.sh 110-Waypoints/01-send_angular_wapoint_trajectory.py
./run.sh 108-Gen3_torque_control/01-torque_control_cyclic.py    # riskiest, run last
```

Most motion examples first move to the robot's built-in **"Home"** action, not the workspace home below.

## 4. Workspace home pose (`home.py`)

A custom, comfortable home pose stored in `home.json`, independent of the robot's built-in "Home".

```bash
./home.py set     # admittance on: drag the arm to the pose, press Enter to save
./home.py here    # save the current pose without admittance
./home.py go      # move to the saved home pose
./home.py show    # print the saved joint angles
```

## 5. Keyboard teleoperation (`teleop.py`)

```bash
./teleop.py
```

Opens a small window; keys only work while it has focus. The arm moves only while keys are held.

| Keys | Action |
|---|---|
| W / S, A / D, R / F | ±x, ±y, ±z (base frame: x forward, y left, z up) |
| U / O, I / K, J / L | roll, pitch, yaw |
| E / Q (hold) | open / close gripper |
| T | toggle base / tool reference frame |
| [ / ] | slower / faster (10 %–100 %, starts at 50 %) |
| H | go to workspace home (`home.json`); any move key or SPACE interrupts |
| SPACE | stop |
| ESC or close window | quit |

Full speed is 0.1 m/s and 20 deg/s. The arm stops when all keys are released, the window loses
focus, or the program exits. **Quit with ESC or by closing the window** so cleanup runs; if it hangs,
use `pkill -INT -f teleop.py`, and `pkill -KILL -f teleop.py` only as a last resort (then make sure
the arm has stopped).

## 6. Drag-and-teach: record and replay trajectories (`teach.py`)

The arm is put in admittance mode so it can be moved by hand; poses are recorded to JSON and replayed.

```bash
./home.py go
./teach.py record traj1.json --continuous 20    # continuous 20 Hz recording; Enter to stop
./teach.py record traj1.json                    # or keyframes: Enter = save pose, q + Enter = done

./home.py go
./teach.py replay traj1.json --vel 10           # move to first pose, then play back
```

| Option | Applies to | Meaning |
|---|---|---|
| `--continuous HZ` | record | sample continuously at HZ instead of keyframes |
| `--mode joint\|cartesian\|nullspace` | record | admittance mode (default `joint`) |
| `--vel DEG_S` | replay | max joint speed (default 20) |
| `--min-step DEG` | replay | skip poses closer than this to the previous one (default 2) |
| `--min-duration S` | replay | minimum time per waypoint (default 0.5) |
| `--blend` | replay | smooth blending; may not pass exactly through every pose |

Recorded file format: `{"mode", "continuous_hz", "samples": [{"t", "joints_deg", "tool_pose"}]}`,
where `tool_pose` is `[x, y, z, theta_x, theta_y, theta_z]` (m, deg). The gripper is not recorded.
The robot validates the trajectory before replay executes it.

**Where to hold the arm:**
- `joint` mode: one hand on the forearm/wrist (just behind the gripper), the other supporting the
  elbow/upper arm. To rotate a joint, push on the link just after it.
- `cartesian` mode: hold the wrist and move it like the gripper.
- `nullspace` mode (7-DoF only): keep the gripper still and push the elbow.
- Don't push on the gripper fingers. Keep holding the arm until "Admittance disabled" is printed.

Admittance is always turned off when recording ends, including on Ctrl+C.

## Safety

- The arm must be secured to the table with a clear workspace; keep the e-stop within reach.
- Use low speeds (`--vel 10`, teleop `[`) for first runs. Replay's first move to the start pose can be large.
- If the arm drifts or feels heavy in admittance, check the payload/tool settings in the Web App.
