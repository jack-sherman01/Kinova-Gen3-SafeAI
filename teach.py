#!/usr/bin/env -S bash -c 'exec "$(dirname "$0")/.venv/bin/python" "$0" "$@"'
"""Kinesthetic teaching for the Kinova Gen3: drag the arm by hand (admittance mode), record, replay.

  record: ./teach.py record demo.json                    # Enter = save keyframe, q+Enter = finish
          ./teach.py record demo.json --continuous 20    # sample at 20 Hz until Enter
  replay: ./teach.py replay demo.json [--vel 20]         # moves to the first pose, then plays the rest

Admittance is always disabled on exit, including on Ctrl+C / errors.
"""
import argparse
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "Kinova-kortex2_Gen3_G3L", "api_python", "examples"))
import utilities

from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
from kortex_api.autogen.client_stubs.BaseCyclicClientRpc import BaseCyclicClient
from kortex_api.autogen.messages import Base_pb2

TIMEOUT_DURATION = 300  # seconds to wait for a replay to finish
ADMITTANCE_MODES = {
    "joint": Base_pb2.JOINT,            # each joint moves freely (usual choice for teaching)
    "cartesian": Base_pb2.CARTESIAN,    # push the end effector, arm follows in Cartesian space
    "nullspace": Base_pb2.NULL_SPACE,   # 7-DoF only: elbow moves, end effector stays fixed
}


def check_for_end_or_abort(e):
    def check(notification, e=e):
        print("EVENT : " + Base_pb2.ActionEvent.Name(notification.action_event))
        if notification.action_event in (Base_pb2.ACTION_END, Base_pb2.ACTION_ABORT):
            e.set()
    return check


def set_single_level_servoing(base):
    mode = Base_pb2.ServoingModeInformation()
    mode.servoing_mode = Base_pb2.SINGLE_LEVEL_SERVOING
    base.SetServoingMode(mode)


def set_admittance(base, mode):
    admittance = Base_pb2.Admittance()
    admittance.admittance_mode = mode
    base.SetAdmittance(admittance)


def read_state(base_cyclic):
    fb = base_cyclic.RefreshFeedback()
    b = fb.base
    return {
        "t": time.time(),
        "joints_deg": [a.position for a in fb.actuators],
        "tool_pose": [b.tool_pose_x, b.tool_pose_y, b.tool_pose_z,
                      b.tool_pose_theta_x, b.tool_pose_theta_y, b.tool_pose_theta_z],
    }


def angle_diff(a, b):
    """Smallest signed difference b - a in degrees (joint angles are reported in [0, 360))."""
    return (b - a + 180.0) % 360.0 - 180.0


def max_joint_delta(q0, q1):
    return max(abs(angle_diff(a, b)) for a, b in zip(q0, q1))


def record(base, base_cyclic, args):
    set_single_level_servoing(base)
    samples = []
    print(f"Enabling {args.mode} admittance: the arm is now compliant, support it by hand.")
    set_admittance(base, ADMITTANCE_MODES[args.mode])
    try:
        if args.continuous:
            stop = threading.Event()

            def sampler():
                period = 1.0 / args.continuous
                while not stop.is_set():
                    samples.append(read_state(base_cyclic))
                    time.sleep(period)

            thread = threading.Thread(target=sampler, daemon=True)
            thread.start()
            input(f"Recording at {args.continuous} Hz. Drag the arm, press Enter to stop...")
            stop.set()
            thread.join()
        else:
            print("Drag the arm to a pose and press Enter to save it; type q + Enter to finish.")
            while True:
                if input(f"[{len(samples)} saved] > ").strip().lower() == "q":
                    break
                s = read_state(base_cyclic)
                samples.append(s)
                print("  saved joints:", [round(q, 1) for q in s["joints_deg"]])
    finally:
        set_admittance(base, Base_pb2.DISABLED)
        print("Admittance disabled.")

    if not samples:
        print("Nothing recorded.")
        return False
    with open(args.file, "w") as f:
        json.dump({"mode": args.mode, "continuous_hz": args.continuous, "samples": samples}, f, indent=1)
    print(f"Saved {len(samples)} samples to {args.file}")
    return True


def execute_and_wait(base, send):
    e = threading.Event()
    handle = base.OnNotificationActionTopic(check_for_end_or_abort(e), Base_pb2.NotificationOptions())
    send()
    finished = e.wait(TIMEOUT_DURATION)
    base.Unsubscribe(handle)
    if not finished:
        print("Timeout waiting for motion to finish")
    return finished


def joint_action(joints, name="reach_joints"):
    action = Base_pb2.Action()
    action.name = name
    action.application_data = ""
    for i, q in enumerate(joints):
        ja = action.reach_joint_angles.joint_angles.joint_angles.add()
        ja.joint_identifier = i
        ja.value = q
    return action


def reach_joints(base, joints):
    action = joint_action(joints)
    return execute_and_wait(base, lambda: base.ExecuteAction(action))


def replay(base, args):
    with open(args.file) as f:
        samples = json.load(f)["samples"]
    poses = [s["joints_deg"] for s in samples]

    # Drop poses that barely differ from the previous kept pose (mainly for continuous recordings)
    kept = [poses[0]]
    for q in poses[1:]:
        if max_joint_delta(kept[-1], q) >= args.min_step:
            kept.append(q)
    print(f"Replaying {len(kept)} of {len(poses)} recorded poses at <= {args.vel} deg/s")

    set_single_level_servoing(base)
    print("Moving to the first recorded pose...")
    if not reach_joints(base, kept[0]):
        return False
    if len(kept) == 1:
        return True

    waypoints = Base_pb2.WaypointList()
    waypoints.duration = 0.0
    waypoints.use_optimal_blending = args.blend
    for i, (prev, q) in enumerate(zip(kept, kept[1:])):
        wp = waypoints.waypoints.add()
        wp.name = f"waypoint_{i}"
        wp.angular_waypoint.angles.extend(q)
        wp.angular_waypoint.duration = max(args.min_duration, max_joint_delta(prev, q) / args.vel)

    result = base.ValidateWaypointList(waypoints)
    if len(result.trajectory_error_report.trajectory_error_elements) > 0:
        print("Trajectory rejected by the robot:")
        print(result.trajectory_error_report)
        return False
    print("Executing trajectory...")
    return execute_and_wait(base, lambda: base.ExecuteWaypointTrajectory(waypoints))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["record", "replay"])
    parser.add_argument("file", help="JSON file to write (record) or read (replay)")
    parser.add_argument("--mode", choices=ADMITTANCE_MODES, default="joint", help="record: admittance mode")
    parser.add_argument("--continuous", type=float, default=0,
                        help="record: sample continuously at this rate (Hz) instead of keyframes")
    parser.add_argument("--vel", type=float, default=20.0, help="replay: max joint speed (deg/s)")
    parser.add_argument("--min-step", type=float, default=2.0,
                        help="replay: skip poses closer than this to the previous one (deg)")
    parser.add_argument("--min-duration", type=float, default=0.5, help="replay: min time per waypoint (s)")
    parser.add_argument("--blend", action="store_true", help="replay: smooth blending between waypoints")
    args = utilities.parseConnectionArguments(parser)

    with utilities.DeviceConnection.createTcpConnection(args) as router:
        base = BaseClient(router)
        base_cyclic = BaseCyclicClient(router)
        ok = record(base, base_cyclic, args) if args.command == "record" else replay(base, args)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
