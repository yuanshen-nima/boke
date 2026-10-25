"""paper_sync 离线测试套件入口：python -m paper_sync test"""

import unittest


def run_tests() -> int:
    from . import test_sync

    suite = unittest.defaultTestLoader.loadTestsFromModule(test_sync)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return 0 if result.wasSuccessful() else 1
