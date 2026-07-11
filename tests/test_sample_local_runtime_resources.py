import tempfile
import unittest
from pathlib import Path
import sys

from scripts.sample_local_runtime_resources import alive, read_pid


class ResourceSamplerTests(unittest.TestCase):
    def test_read_pid_requires_integer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pid"
            path.write_text("123\n")
            self.assertEqual(read_pid(path), 123)

    @unittest.skipUnless(sys.platform.startswith("linux"), "procfs is Linux-specific")
    def test_current_process_is_alive(self) -> None:
        import os
        self.assertTrue(alive(os.getpid()))


if __name__ == "__main__":
    unittest.main()
