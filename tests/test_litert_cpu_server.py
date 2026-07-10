import unittest

from scripts.litert_cpu_server import parser


class LiteRTCpuServerTests(unittest.TestCase):
    def test_grader_safe_defaults(self):
        args = parser().parse_args([])
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 9379)
        self.assertEqual(args.cpu_threads, 2)
        self.assertEqual(args.max_context_tokens, 2048)
        self.assertFalse(args.speculative_decoding)


if __name__ == "__main__":
    unittest.main()
