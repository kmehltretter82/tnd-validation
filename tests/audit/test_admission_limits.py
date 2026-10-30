"""Parser output, deadline and Linux resource-limit regression tests."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[2] / "audit" / "admission"
SPEC = importlib.util.spec_from_file_location("tnd_admission_limits", HERE / "admit.py")
admission = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admission)
LIMIT_SPEC = importlib.util.spec_from_file_location("tnd_resource_limits", HERE / "limited.py")
limits = importlib.util.module_from_spec(LIMIT_SPEC)
LIMIT_SPEC.loader.exec_module(limits)


class ParserLimitTests(unittest.TestCase):
    def run_child(self, script: str, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            return admission.run_parser(
                [sys.executable, "-c", script], cwd=Path(tmp), env=dict(os.environ), **kwargs
            )

    def test_success_and_failure_return_bounded_diagnostics(self):
        result = self.run_child("import sys; print('ok'); print('warning', file=sys.stderr)")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok\n")
        self.assertEqual(result.stderr, "warning\n")
        result = self.run_child("import sys; print('bad'); sys.exit(9)")
        self.assertEqual(result.returncode, 9)
        self.assertEqual(result.stdout, "bad\n")

    def test_combined_stdout_and_stderr_are_bounded(self):
        with self.assertRaisesRegex(ValueError, "output exceeded"):
            self.run_child(
                "import os; os.write(1,b'x'*7000); os.write(2,b'y'*7000)", output_limit=12000
            )

    def test_wall_clock_timeout_stops_parser_process_group(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_child("import time; time.sleep(10)", timeout=0.25)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux resource limits")
    def test_linux_hard_limits_are_inherited_by_parser(self):
        script = (
            "import json,resource; print(json.dumps({"
            "'as':resource.getrlimit(resource.RLIMIT_AS),"
            "'cpu':resource.getrlimit(resource.RLIMIT_CPU),"
            "'core':resource.getrlimit(resource.RLIMIT_CORE)}))"
        )
        result = self.run_child(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        actual = json.loads(result.stdout)
        self.assertEqual(actual["as"], [limits.ADDRESS_SPACE_BYTES, limits.ADDRESS_SPACE_BYTES])
        self.assertEqual(actual["cpu"], [limits.CPU_SECONDS, limits.CPU_SECONDS])
        self.assertEqual(actual["core"], [0, 0])

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux resource limits")
    def test_linux_address_space_cap_rejects_oversized_allocation(self):
        script = (
            f"import sys\ntry: bytearray({limits.ADDRESS_SPACE_BYTES + 1})\n"
            "except MemoryError: print('allocation denied')\n"
            "else: sys.exit(7)"
        )
        result = self.run_child(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "allocation denied\n")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux resource limits")
    def test_linux_cpu_limit_can_terminate_a_busy_child(self):
        script = (
            "import resource\nresource.setrlimit(resource.RLIMIT_CPU, (1, 1))\nwhile True: pass"
        )
        result = self.run_child(script, timeout=8)
        self.assertLess(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
