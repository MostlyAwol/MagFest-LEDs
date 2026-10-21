import json
import os
from pathlib import Path
import queue
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

import magfest_led as led


class Strip(list):
    def __init__(self):
        super().__init__([(0, 0, 0)] * 300)

    def show(self):
        pass


class ControllerTests(unittest.TestCase):
    def setUp(self):
        led.running = True
        led.stop_threads = False
        led.exit_event.clear()
        led.strip = Strip()
        led.LED_thread = None
        led.last_percent = -1
        led.last_scale = 0
        led.snmp_community = "public"
        led.allow_power_commands = False
        led.worker_errors = queue.Queue()
        led.commands = queue.Queue(maxsize=64)
        led.health.update(state="starting", mode="BANDWIDTH", snmp_failures=0)

    def tearDown(self):
        led.StopLED()

    def test_command_validation(self):
        self.assertEqual(led.parse_command(b" wipe 00ff00 25\n"),
                         ("WIPE", (0, 255, 0), 25))
        for packet in (b"", b"\xff", b"FILL ff0000 -1", b"BEAT ff0000 0",
                       b"FILL ff0000 61", b"WIPE ff0000 251", b"FF xyzxyz",
                       b"RAINBOW garbage", b"UNKNOWN", b"RBBEAT nope"):
            with self.subTest(packet=packet), self.assertRaises((ValueError, UnicodeError)):
                led.parse_command(packet)

    def test_rate_uses_elapsed_time_and_correct_wrap(self):
        self.assertEqual(led.counter_rate(100, 300, 2, 32), 800)
        self.assertEqual(led.counter_rate((1 << 32) - 10, 10, 1, 32), 160)
        self.assertIsNone(led.counter_rate(500, 10, 1, 64))
        self.assertIsNone(led.counter_rate(None, 100, 1, 32))
        self.assertIsNone(led.counter_rate(0, 100, 0, 32))

    def test_all_effects_can_stop_and_respect_pixel_bounds(self):
        for command in (b"RAINBOW", b"FF ff0000", b"WIPE ff0000 250",
                        b"CHASE ff0000", b"BEAT ff0000", b"RBEAT ff0000", b"RBBEAT"):
            with self.subTest(command=command):
                led.apply_command(led.parse_command(command))
                time.sleep(0.03)
                led.StopLED()
                self.assertTrue(led.worker_errors.empty())
                self.assertFalse(led.LED_thread.is_alive())
                self.assertEqual(led.strip, [(0, 0, 0)] * 300)

    def test_snmp_failure_is_interruptible(self):
        with patch.object(led, "Session", side_effect=RuntimeError("offline")):
            with self.assertLogs("magfest", level="ERROR"):
                led.start_led(led.MonitorBandwidth, "192.0.2.1", led.switch_mib)
                deadline = time.monotonic() + 2
                while led.health["state"] != "snmp_error" and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertEqual(led.health["state"], "snmp_error")
                led.StopLED()
                self.assertFalse(led.LED_thread.is_alive())

    def test_effects_complete_full_cycles_without_out_of_bounds(self):
        effects = ((led.rainbowCycle, ()), (led.FlipFlop, ((255, 0, 0),)),
                   (led.colorWipe, ((255, 0, 0),)), (led.theaterChase, ((255, 0, 0),)),
                   (led.Beat, ((255, 0, 0),)), (led.RBeat, ((255, 0, 0),)), (led.RBBeat, ()))
        for effect, arguments in effects:
            led.stop_threads = False
            frames = []
            def advance(seconds):
                frames.append(seconds)
                if len(frames) >= 300:
                    led.stop_threads = True
            with self.subTest(effect=effect.__name__), patch.object(led, "pause", side_effect=advance):
                effect(led.strip, *arguments)
                self.assertGreaterEqual(len(frames), 300)

    def test_snmp_recovers_and_rebaselines(self):
        session = Mock()
        session.get.side_effect = [RuntimeError("offline"),
                                   Mock(value="100", snmp_type="COUNTER64"),
                                   Mock(value="300", snmp_type="COUNTER64")]
        waits = []
        def advance(seconds):
            waits.append(seconds)
            if len(waits) == 3:
                led.stop_threads = True
        with patch.object(led, "Session", return_value=session), \
                patch.object(led, "pause", side_effect=advance), \
                patch.object(led, "LEDBandWidth") as display, \
                self.assertLogs("magfest"):
            led.MonitorBandwidth("192.0.2.1", led.switch_mib)
        self.assertEqual(led.health["state"], "monitoring")
        self.assertEqual(led.health["snmp_failures"], 0)
        self.assertEqual(display.call_count, 2)

    def test_led_failure_reaches_supervisor(self):
        def fail():
            raise OSError("LED backend failed")
        with self.assertLogs("magfest", level="ERROR"):
            led.start_led(fail)
            led.LED_thread.join(1)
        self.assertIsInstance(led.worker_errors.get_nowait(), OSError)

    def test_stalled_worker_is_detected(self):
        with patch.object(led, "LED_thread", Mock(is_alive=Mock(return_value=True))), \
                patch.object(led, "last_led_progress", time.monotonic() - 20):
            with self.assertRaisesRegex(RuntimeError, "no progress"):
                led.check_workers()

    def test_steady_bandwidth_still_updates_progress(self):
        session = Mock()
        session.get.return_value = Mock(value="100", snmp_type="COUNTER64")
        waits = []
        def advance(seconds):
            waits.append(seconds)
            if len(waits) == 3:
                led.stop_threads = True
        led.last_led_progress = 0
        with patch.object(led, "Session", return_value=session), \
                patch.object(led, "pause", side_effect=advance), \
                patch.object(led, "LEDBandWidth"):
            led.MonitorBandwidth("192.0.2.1", led.switch_mib)
        self.assertEqual(len(waits), 3)
        self.assertGreater(led.last_led_progress, 0)

    def test_sigterm_handler_stops_an_animation(self):
        led.start_led(led.FlipFlop, led.strip, (255, 0, 0))
        led.shutdown(signal.SIGTERM, None)
        led.StopLED()
        self.assertFalse(led.running)
        self.assertFalse(led.LED_thread.is_alive())

    def test_discovery_timeout_and_interface(self):
        with patch.object(led.subprocess, "run", side_effect=subprocess.TimeoutExpired("lldpctl", 3)), \
                self.assertLogs("magfest"):
            self.assertIsNone(led.get_switch_ip())
        result = Mock(stdout="lldp.eth1.chassis.mgmt-ip=2001:db8::1\nlldp.eth1.chassis.mgmt-ip=192.0.2.42\n")
        with patch.object(led.subprocess, "run", return_value=result) as run:
            self.assertEqual(led.get_switch_ip("eth1"), "192.0.2.42")
            self.assertEqual(run.call_args.kwargs["timeout"], 3)

    def test_scale_change_repaints_same_height(self):
        # The monitor resets last_percent when changing scale. Check rendering
        # behavior when a reconnect or scale change requests a fresh frame.
        led.LEDBandWidth(led.strip, 20, 45, 0)
        led.last_percent = -1
        led.LEDBandWidth(led.strip, 20, 45, 1)
        self.assertGreater(led.strip[50][1], 0)
        self.assertEqual(led.strip[50][0], 0)

    def test_fill_amount_and_power_command_default(self):
        led.apply_command(led.parse_command(b"FILL 00ff00 2"))
        self.assertEqual(led.strip[:10], [(0, 255, 0)] * 10)
        self.assertEqual(led.strip[10:], [(0, 0, 0)] * 290)
        with patch.object(led.subprocess, "run") as run, self.assertLogs("magfest"):
            led.apply_command(led.parse_command(b"REBOOT"))
            run.assert_not_called()

    def test_atomic_status_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "status.json"
            led.write_status(path)
            self.assertEqual(json.loads(path.read_text())["version"], led.version)
            self.assertFalse(path.with_suffix(".tmp").exists())

    def test_udp_receiver_survives_invalid_packets(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server:
            server.bind(("127.0.0.1", 0))
            server.settimeout(0.1)
            led.serversocket = server
            receiver = threading.Thread(target=led.SocketThread)
            receiver.start()
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                    client.settimeout(2)
                    for packet in (b"\xff", b"WIPE bad", b"FILL ff0000 -1", b"x" * 5000, b"STATUS"):
                        client.sendto(packet, server.getsockname())
                    reply, _ = client.recvfrom(8192)
                    self.assertEqual(json.loads(reply)["version"], led.version)
                    client.sendto(b"FILL ff0000 2", server.getsockname())
                    self.assertEqual(led.commands.get(timeout=2), ("FILL", (255, 0, 0), 2))
            finally:
                led.running = False
                receiver.join(1)
            self.assertFalse(receiver.is_alive())

    def test_process_accepts_commands_with_offline_switch(self):
        # Exercise the real main loop/socket/signal cleanup with fake Pi modules.
        harness = '''
import sys, types
from unittest.mock import Mock
import magfest_led as led
class Strip(list):
    def __init__(self, *args, **kwargs): super().__init__([(0,0,0)] * 300)
    def show(self): pass
    def deinit(self): pass
sys.modules['board'] = types.SimpleNamespace(D18=18)
sys.modules['neopixel'] = types.SimpleNamespace(GRB='GRB', NeoPixel=Strip)
sys.modules['easysnmp'] = types.SimpleNamespace(Session=Mock(side_effect=RuntimeError('offline')))
led.main()
'''
        with tempfile.TemporaryDirectory() as folder, \
                socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
            reservation.close()
            process = subprocess.Popen([sys.executable, "-c", harness, "--switch", "192.0.2.1",
                                        "--port", str(port), "--status-file", str(Path(folder) / "status.json")],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                       text=True)
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client:
                    client.settimeout(0.2)
                    deadline = time.monotonic() + 5
                    reply = None
                    while time.monotonic() < deadline:
                        client.sendto(b"STATUS", ("127.0.0.1", port))
                        try:
                            reply = json.loads(client.recvfrom(8192)[0])
                            break
                        except OSError:
                            pass
                    self.assertIsNotNone(reply)
                    client.sendto(b"FILL 00ff00 2", ("127.0.0.1", port))
                    deadline = time.monotonic() + 3
                    while time.monotonic() < deadline:
                        client.sendto(b"STATUS", ("127.0.0.1", port))
                        reply = json.loads(client.recvfrom(8192)[0])
                        if reply['mode'] == 'FILL':
                            break
                        time.sleep(0.05)
                    self.assertEqual(reply['mode'], 'FILL')
                if os.name == "nt":
                    # Windows terminate does not deliver SIGTERM to Python.
                    process.terminate()
                else:
                    process.send_signal(signal.SIGTERM)
                process.communicate(timeout=5)
                if os.name != "nt":
                    self.assertEqual(process.returncode, 0)
                    self.assertEqual(json.loads((Path(folder) / "status.json").read_text())['state'], 'exited')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()


if __name__ == "__main__":
    unittest.main()
