"""Test shared helpers in custom_components.early.util."""

from custom_components.early.util import (
    build_activity_display_name,
    get_current_activity_id,
)


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


class TestBuildActivityDisplayName:
    """Test build_activity_display_name."""

    def test_prefixes_with_space_name(self):
        """Test the common case: disambiguating same-named activities across spaces."""
        assert (
            build_activity_display_name("Administrivia", "Google")
            == "Google: Administrivia"
        )

    def test_no_space_name_returns_bare_activity_name(self):
        """Test the fallback when no space name is available at all."""
        assert build_activity_display_name("Meetings", None) == "Meetings"

    def test_empty_space_name_returns_bare_activity_name(self):
        """Test an empty string space name is treated like no space name.

        Guards against a broken-looking "Meetings" (blank prefix with
        colon) if the /space API ever returns an activity with an
        empty-string name for some space.
        """
        assert build_activity_display_name("Meetings", "") == "Meetings"
