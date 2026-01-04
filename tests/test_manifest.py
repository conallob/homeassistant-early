"""Test the EARLY integration manifest."""
import json
import pytest
from pathlib import Path


class TestManifest:
    """Test the manifest.json file."""

    @pytest.fixture
    def manifest(self):
        """Load the manifest file."""
        manifest_path = Path(__file__).parent.parent / "custom_components" / "early" / "manifest.json"
        with open(manifest_path) as f:
            return json.load(f)

    def test_manifest_exists(self):
        """Test that manifest file exists."""
        manifest_path = Path(__file__).parent.parent / "custom_components" / "early" / "manifest.json"
        assert manifest_path.exists()

    def test_manifest_valid_json(self, manifest):
        """Test that manifest is valid JSON."""
        assert manifest is not None
        assert isinstance(manifest, dict)

    def test_manifest_required_fields(self, manifest):
        """Test that manifest contains all required fields."""
        required_fields = [
            "domain",
            "name",
            "documentation",
            "requirements",
            "codeowners",
            "version",
            "config_flow",
            "iot_class",
        ]

        for field in required_fields:
            assert field in manifest, f"Missing required field: {field}"

    def test_manifest_domain(self, manifest):
        """Test manifest domain field."""
        assert manifest["domain"] == "early"
        assert isinstance(manifest["domain"], str)

    def test_manifest_name(self, manifest):
        """Test manifest name field."""
        assert manifest["name"] == "EARLY (Timeular)"
        assert isinstance(manifest["name"], str)

    def test_manifest_version(self, manifest):
        """Test manifest version field."""
        assert "version" in manifest
        assert isinstance(manifest["version"], str)
        # Version should be in format X.Y.Z
        parts = manifest["version"].split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()

    def test_manifest_documentation(self, manifest):
        """Test manifest documentation field."""
        assert isinstance(manifest["documentation"], str)
        assert manifest["documentation"].startswith("http")

    def test_manifest_requirements(self, manifest):
        """Test manifest requirements field."""
        assert isinstance(manifest["requirements"], list)
        assert len(manifest["requirements"]) > 0
        assert "requests>=2.31.0" in manifest["requirements"]

    def test_manifest_codeowners(self, manifest):
        """Test manifest codeowners field."""
        assert isinstance(manifest["codeowners"], list)
        assert len(manifest["codeowners"]) > 0
        for owner in manifest["codeowners"]:
            assert owner.startswith("@")

    def test_manifest_config_flow(self, manifest):
        """Test manifest config_flow field."""
        assert manifest["config_flow"] is True
        assert isinstance(manifest["config_flow"], bool)

    def test_manifest_iot_class(self, manifest):
        """Test manifest iot_class field."""
        valid_iot_classes = [
            "assumed_state",
            "cloud_polling",
            "cloud_push",
            "local_polling",
            "local_push",
        ]
        assert manifest["iot_class"] in valid_iot_classes

    def test_manifest_dependencies(self, manifest):
        """Test manifest dependencies field."""
        assert "dependencies" in manifest
        assert isinstance(manifest["dependencies"], list)
        assert "bluetooth" in manifest["dependencies"]

    def test_manifest_bluetooth_config(self, manifest):
        """Test manifest bluetooth configuration."""
        assert "bluetooth" in manifest
        assert isinstance(manifest["bluetooth"], list)
        assert len(manifest["bluetooth"]) > 0

        bt_config = manifest["bluetooth"][0]
        assert "local_name" in bt_config
        assert bt_config["local_name"] == "Timeular ZEI*"

    def test_manifest_no_extra_fields(self, manifest):
        """Test that manifest doesn't have unexpected fields."""
        allowed_fields = [
            "domain",
            "name",
            "documentation",
            "requirements",
            "codeowners",
            "version",
            "config_flow",
            "iot_class",
            "dependencies",
            "bluetooth",
            "after_dependencies",
            "integration_type",
        ]

        for field in manifest.keys():
            assert field in allowed_fields, f"Unexpected field in manifest: {field}"

    def test_requirements_versions_specified(self, manifest):
        """Test that all requirements have version specifications."""
        for req in manifest["requirements"]:
            # Should have version spec like >= or ==
            assert any(op in req for op in [">=", "==", "~=", ">", "<"])


class TestManifestConsistency:
    """Test manifest consistency with code."""

    @pytest.fixture
    def manifest(self):
        """Load the manifest file."""
        manifest_path = Path(__file__).parent.parent / "custom_components" / "early" / "manifest.json"
        with open(manifest_path) as f:
            return json.load(f)

    def test_domain_matches_const(self, manifest):
        """Test that domain in manifest matches DOMAIN constant."""
        from custom_components.early.const import DOMAIN
        assert manifest["domain"] == DOMAIN

    def test_device_name_prefix_matches_bluetooth_config(self, manifest):
        """Test that device name prefix matches Bluetooth config."""
        from custom_components.early.const import DEVICE_NAME_PREFIX
        bt_config = manifest["bluetooth"][0]
        assert DEVICE_NAME_PREFIX in bt_config["local_name"]

    def test_strings_file_exists(self, manifest):
        """Test that strings.json exists."""
        strings_path = Path(__file__).parent.parent / "custom_components" / "early" / "strings.json"
        assert strings_path.exists()

    def test_strings_file_valid_json(self):
        """Test that strings.json is valid JSON."""
        strings_path = Path(__file__).parent.parent / "custom_components" / "early" / "strings.json"
        with open(strings_path) as f:
            strings = json.load(f)
        assert strings is not None
        assert isinstance(strings, dict)

    def test_translations_dir_exists(self):
        """Test that translations directory exists."""
        translations_path = Path(__file__).parent.parent / "custom_components" / "early" / "translations"
        assert translations_path.exists()
        assert translations_path.is_dir()
