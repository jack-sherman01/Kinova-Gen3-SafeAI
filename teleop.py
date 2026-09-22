#!/usr/bin/env -S bash -c 'exec "$(dirname "$0")/.venv/bin/python" "$0" "$@"'
"""Keyboard teleoperation for the Kinova Gen3 (Cartesian velocity control).

Opens a small window; keys only work while it has focus. The arm moves only while keys are held
and stops when all are released, the window loses focus, or the program exits.

  W/S  +x/-x      A/D  +y/-y      R/F  +z/-z        (m/s, base frame: x forward, y left, z up)
  U/O  roll       I/K  pitch      J/L  yaw          (deg/s)
  E    open gripper (hold)        Q    close gripper (hold)
  T    toggle base/tool frame     [ ]  slower/faster
  H    go to workspace home (home.json)
  SPACE stop     ESC quit
"""
import argparse
import sys

import pygame

import home
import teach
import utilities

from kortex_api.autogen.client_stubs.BaseClientRpc import BaseClient
from kortex_api.autogen.messages import Base_pb2

MAX_LINEAR = 0.10    # m/s at scale 1.0
MAX_ANGULAR = 20.0   # deg/s at scale 1.0
GRIPPER_SPEED = 0.3  # fraction of max finger speed; positive opens, negative closes
SCALES = [0.1, 0.25, 0.5, 0.75, 1.0]

# key -> (twist index, sign); twist index 0-2 linear x/y/z, 3-5 angular x/y/z
KEYMAP = {
    pygame.K_w: (0, +1), pygame.K_s: (0, -1),
    pygame.K_a: (1, +1), pygame.K_d: (1, -1),
    pygame.K_r: (2, +1), pygame.K_f: (2, -1),
    pygame.K_u: (3, +1), pygame.K_o: (3, -1),
    pygame.K_i: (4, +1), pygame.K_k: (4, -1),
    pygame.K_j: (5, +1), pygame.K_l: (5, -1),
}
FRAMES = {"base": Base_pb2.CARTESIAN_REFERENCE_FRAME_BASE, "tool": Base_pb2.CARTESIAN_REFERENCE_FRAME_TOOL}


def send_twist(base, frame, v):
    command = Base_pb2.TwistCommand()
    command.reference_frame = FRAMES[frame]
    command.duration = 0
    t = command.twist
    t.linear_x, t.linear_y, t.linear_z, t.angular_x, t.angular_y, t.angular_z = v
    base.SendTwistCommand(command)


def send_gripper_speed(base, speed):
    command = Base_pb2.GripperCommand()
    command.mode = Base_pb2.GRIPPER_SPEED
    finger = command.gripper.finger.add()
    finger.finger_identifier = 1
    finger.value = speed
    base.SendGripperCommand(command)


def draw(screen, font, lines):
    screen.fill((25, 25, 30))
    for i, line in enumerate(lines):
        screen.blit(font.render(line, True, (230, 230, 230)), (12, 10 + 22 * i))
    pygame.display.flip()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    args = utilities.parseConnectionArguments(parser)

    pygame.init()
    screen = pygame.display.set_mode((560, 330))
    pygame.display.set_caption("Kinova Gen3 teleop")
    font = pygame.font.SysFont("monospace", 16)
    clock = pygame.time.Clock()
    help_lines = [l for l in __doc__.strip().splitlines()[5:] if l.strip()]

    with utilities.DeviceConnection.createTcpConnection(args) as router:
        base = BaseClient(router)
        teach.set_single_level_servoing(base)

        frame, scale_idx = "base", 2
        last_twist, last_grip = None, 0.0
        status = "ready"
        try:
            running = True
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            running = False
                        elif event.key == pygame.K_SPACE:
                            base.Stop()
                            last_twist, status = None, "stopped"
                        elif event.key == pygame.K_t:
                            frame = "tool" if frame == "base" else "base"
                        elif event.key == pygame.K_LEFTBRACKET:
                            scale_idx = max(0, scale_idx - 1)
                        elif event.key == pygame.K_RIGHTBRACKET:
                            scale_idx = min(len(SCALES) - 1, scale_idx + 1)
                        elif event.key == pygame.K_h:
                            base.ExecuteAction(teach.joint_action(home.load_home(), "workspace_home"))
                            last_twist, status = None, "going home (any move key / SPACE interrupts)"

                keys = pygame.key.get_pressed()
                focused = pygame.key.get_focused()
                scale = SCALES[scale_idx]

                v = [0.0] * 6
                if focused:
                    for key, (idx, sign) in KEYMAP.items():
                        if keys[key]:
                            v[idx] += sign * (MAX_LINEAR if idx < 3 else MAX_ANGULAR) * scale
                twist = (frame, tuple(v))
                if any(v):
                    if twist != last_twist:
                        send_twist(base, frame, v)
                        last_twist, status = twist, "moving"
                elif last_twist is not None:
                    base.Stop()  # all move keys released
                    last_twist, status = None, "stopped"

                grip = 0.0
                if focused and keys[pygame.K_e]:
                    grip = GRIPPER_SPEED
                elif focused and keys[pygame.K_q]:
                    grip = -GRIPPER_SPEED
                if grip != last_grip:
                    send_gripper_speed(base, grip)
                    last_grip = grip

                draw(screen, font, [
                    f"frame: {frame}   speed: {scale:.2f}  ({MAX_LINEAR * scale:.3f} m/s, "
                    f"{MAX_ANGULAR * scale:.0f} deg/s)",
                    f"status: {status}" + ("" if focused else "   [CLICK WINDOW TO FOCUS]"),
                    "",
                ] + help_lines)
                clock.tick(50)
        finally:
            base.Stop()
            send_gripper_speed(base, 0.0)
            pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
