"""Test shared helpers in custom_components.early.util."""

from custom_components.early.util import get_current_activity_id


class TestGetCurrentActivityId:
    """Test get_current_activity_id."""

    def test_flat_activity_id_field(self):
        """Test the current, real-account response shape (no "activity" key).

        Confirmed via debug logs against a real EARLY account:
        {"id": 118278047, "activityId": "1752293", "startedAt": ...} -
        there is no "activity" key at all.
        """
        current_tracking = {
            "id": 118278047,
            "activityId": "1752293",
            "startedAt": "2026-09-15T22:20:01.367",
        }

        assert get_current_activity_id(current_tracking) == "1752293"

    def test_nested_activity_id_field(self):
        """Test the older nested activity.id shape this integration originally assumed."""
        current_tracking = {"activity": {"id": "activity_1"}}

        assert get_current_activity_id(current_tracking) == "activity_1"

    def test_flat_field_takes_priority_over_nested(self):
        """Test the flat activityId wins if both are somehow present."""
        current_tracking = {
            "activityId": "flat_id",
            "activity": {"id": "nested_id"},
        }

        assert get_current_activity_id(current_tracking) == "flat_id"

    def test_neither_shape_present_returns_none(self):
        """Test a currentTracking with no activity reference at all."""
        current_tracking = {"startedAt": "2026-09-15T22:20:01.367"}

        assert get_current_activity_id(current_tracking) is None

    def test_empty_nested_activity_returns_none(self):
        """Test an empty nested activity object doesn't raise."""
        current_tracking = {"activity": {}}

        assert get_current_activity_id(current_tracking) is None
