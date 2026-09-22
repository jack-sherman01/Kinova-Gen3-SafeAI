#!/usr/bin/env -S bash -c 'exec "$(dirname "$0")/.venv/bin/python" "$0" "$@"'
"""Workspace home pose for the Kinova Gen3 (separate from the robot's built-in "Home" action).

  ./home.py set     # admittance on: drag arm to a comfortable pose, press Enter to save it
  ./home.py here    # save the current pose as home (no admittance)
  ./home.py go      # move to the saved home pose
  ./home.py show    # print the saved home pose
"""
import argparse
import json
import os
import sys

import teach  # also sets up the path to the Kortex examples' utilities
import utilities

from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
from kortex_api.autogen.client_stubs.BaseCyclicClientRpc import BaseCyclicClient
from kortex_api.autogen.messages import Base_pb2

HOME_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "home.json")


def save_home(state):
    with open(HOME_FILE, "w") as f:
        json.dump({"joints_deg": state["joints_deg"], "tool_pose": state["tool_pose"]}, f, indent=1)
    print("Saved home joints:", [round(q, 1) for q in state["joints_deg"]])


def load_home():
    if not os.path.exists(HOME_FILE):
        sys.exit(f"No home saved yet ({HOME_FILE}). Run: ./home.py set")
    with open(HOME_FILE) as f:
        return json.load(f)["joints_deg"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["set", "here", "go", "show"])
    args = utilities.parseConnectionArguments(parser)

    if args.command == "show":
        print("Home joints (deg):", [round(q, 1) for q in load_home()])
        return 0

    with utilities.DeviceConnection.createTcpConnection(args) as router:
        base = BaseClient(router)
        base_cyclic = BaseCyclicClient(router)
        teach.set_single_level_servoing(base)

        if args.command == "go":
            print("Moving to workspace home...")
            return 0 if teach.reach_joints(base, load_home()) else 1

        if args.command == "set":
            print("Enabling joint admittance: support the arm by hand.")
            teach.set_admittance(base, Base_pb2.JOINT)
            try:
                input("Drag the arm to the home pose, then press Enter...")
            finally:
                teach.set_admittance(base, Base_pb2.DISABLED)
                print("Admittance disabled.")
        save_home(teach.read_state(base_cyclic))
    return 0


if __name__ == "__main__":
    sys.exit(main())
