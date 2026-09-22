#!/usr/bin/env python3
"""Read-only connection check for the Kinova Gen3: prints arm state and joint angles. Does NOT move the arm."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "Kinova-kortex2_Gen3_G3L", "api_python", "examples"))
import utilities

from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
from kortex_api.autogen.client_stubs.BaseCyclicClientRpc import BaseCyclicClient
from kortex_api.autogen.client_stubs.DeviceManagerClientRpc import DeviceManagerClient
from kortex_api.autogen.messages import Base_pb2


def main():
    args = utilities.parseConnectionArguments()
    with utilities.DeviceConnection.createTcpConnection(args) as router:
        base = BaseClient(router)
        base_cyclic = BaseCyclicClient(router)
        device_manager = DeviceManagerClient(router)

        print(f"Connected to {args.ip}")
        print("Arm state:", Base_pb2.ArmState.Name(base.GetArmState().active_state))

        devices = device_manager.ReadAllDevices()
        print(f"Devices ({len(devices.device_handle)}):")
        for d in devices.device_handle:
            print(f"  id={d.device_identifier} type={d.device_type}")

        feedback = base_cyclic.RefreshFeedback()
        print("Joint angles (deg):", [round(a.position, 2) for a in feedback.actuators])
        b = feedback.base
        print(f"Tool pose: x={b.tool_pose_x:.3f} y={b.tool_pose_y:.3f} z={b.tool_pose_z:.3f} "
              f"thx={b.tool_pose_theta_x:.1f} thy={b.tool_pose_theta_y:.1f} thz={b.tool_pose_theta_z:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
