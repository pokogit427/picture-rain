import os
import unittest
from unittest.mock import patch

from app.ads import get_ad_slots


class AdPolicyTest(unittest.TestCase):
    def test_ads_are_disabled_by_default_and_send_no_slot_data(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            slots = get_ad_slots("dashboard")

        self.assertEqual(len(slots), 1)
        self.assertEqual(slots[0].mode, "OFF")
        self.assertFalse(slots[0].enabled)
        self.assertIsNone(slots[0].label)
        self.assertIsNone(slots[0].click_url)

    def test_mock_mode_is_local_and_non_clickable(self) -> None:
        with patch.dict(os.environ, {"PICTURE_RAIN_ADS_MODE": "MOCK"}, clear=True):
            slots = get_ad_slots("dashboard")

        self.assertEqual(slots[0].mode, "MOCK")
        self.assertTrue(slots[0].enabled)
        self.assertEqual(slots[0].label, "검토용 광고 영역")
        self.assertIsNone(slots[0].click_url)

    def test_unknown_mode_fails_closed(self) -> None:
        with patch.dict(os.environ, {"PICTURE_RAIN_ADS_MODE": "NETWORK"}, clear=True):
            slots = get_ad_slots("dashboard")

        self.assertEqual(slots[0].mode, "OFF")
        self.assertFalse(slots[0].enabled)


if __name__ == "__main__":
    unittest.main()
