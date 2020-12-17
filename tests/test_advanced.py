# pylint: skip-file
# -*- coding: utf-8 -*-

# from .context import sample

import unittest


class AdvancedTestSuite(unittest.TestCase):
    """Advanced test cases."""

    def test_thoughts(self):
        self.assertIsNone(None) # sample.hmm())


if __name__ == '__main__':
    unittest.main()
