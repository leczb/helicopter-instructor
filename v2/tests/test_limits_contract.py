"""Automated unit tests to verify consistency of limits and boundaries across modules."""

import os
import sys
import unittest
from unittest import mock

base_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(
    0,
    os.path.join(
        base_dir, '..', 'plugin', 'helicopter_instructor', 'autopilot'
    )
)
sys.path.insert(
    0, os.path.join(base_dir, '..', 'plugin', 'helicopter_instructor')
)
sys.path.insert(0, os.path.join(base_dir, '..', 'plugin'))

# Mock the modules conditionally to prevent process pollution across different test modules
if 'xp' not in sys.modules:
    mock_xp = mock.MagicMock()
    sys.modules['xp'] = mock_xp
else:
    mock_xp = sys.modules['xp']

if 'xp_imgui' not in sys.modules:
    mock_xp_imgui = mock.MagicMock()
    sys.modules['xp_imgui'] = mock_xp_imgui
else:
    mock_xp_imgui = sys.modules['xp_imgui']

if 'imgui' not in sys.modules:
    mock_imgui = mock.MagicMock()
    sys.modules['imgui'] = mock_imgui
else:
    mock_imgui = sys.modules['imgui']

from helicopter_instructor import envelope_limits
from helicopter_instructor import metrics
from helicopter_instructor import virtual_instructor


class TestLimitsContract(unittest.TestCase):
    """Verifies all safety and scoring zones match between submodules."""

    def test_precision_scoring_limits_match_instructor_safety_limits(self):
        """Ensures telemetry limits, visual rings, and metrics remain strictly synchronized."""
        # 1. Heading Scoring zones must equal State Machine safety boundaries
        self.assertEqual(metrics.GREEN_ZONE_HDG_DEG, envelope_limits.LIMIT_HDG_GREEN_DEG)
        self.assertEqual(metrics.LIMIT_HDG_DEG, envelope_limits.LIMIT_HDG_ORANGE_DEG)
        
        # 2. Drift scoring boundaries must equal 3D disc ring properties and safety takeover radius
        vfi = virtual_instructor.VirtualInstructor()
        self.assertEqual(metrics.LIMIT_DRIFT_M, vfi.hover_safety_radius)
        self.assertEqual(metrics.LIMIT_DRIFT_M, envelope_limits.LIMIT_DRIFT_RED_M)
        self.assertEqual(metrics.GREEN_ZONE_DRIFT_M, envelope_limits.LIMIT_DRIFT_GREEN_M)
        
        # 3. Altitude scoring boundaries must equal HUD altitude color bands and AGL safety limits
        self.assertEqual(metrics.GREEN_ZONE_ALT_M, envelope_limits.LIMIT_ALT_GREEN_M)
        self.assertEqual(metrics.LIMIT_ALT_M, envelope_limits.LIMIT_ALT_ORANGE_M)

        # 4. Drift speed scoring boundaries must equal centralized envelope limits
        self.assertEqual(metrics.GREEN_ZONE_DRIFT_SPEED_M_S, envelope_limits.LIMIT_DRIFT_SPEED_GREEN_M_S)
        self.assertEqual(metrics.LIMIT_DRIFT_SPEED_M_S, envelope_limits.LIMIT_DRIFT_SPEED_ORANGE_M_S)

        # 5. Vertical speed scoring boundaries must equal centralized envelope limits
        self.assertEqual(metrics.GREEN_ZONE_VERT_SPEED_M_S, envelope_limits.LIMIT_VERT_SPEED_GREEN_M_S)
        self.assertEqual(metrics.LIMIT_VERT_SPEED_M_S, envelope_limits.LIMIT_VERT_SPEED_ORANGE_M_S)


if __name__ == '__main__':
    unittest.main()
