# CLAUDE.md

Guidance for Claude Code sessions working in this repository.

## What this is

A Home Assistant custom integration (`custom_components/early/`) for
[EARLY](https://early.app) (formerly Timeular), a time-tracking app. It has
two independent, optionally-combined data sources per config entry:

- **Cloud API** (`sensor.py`, `switch.py`): polls `api.timeular.com/api/v3`
  for the currently tracked activity and exposes a switch per activity to
  start/stop tracking.
- **Bluetooth** (`bluetooth.py`, `bluetooth_sensor.py`): connects directly to
  a Timeular ZEI physical tracker over BLE and reads its orientation
  (0-8, which side is face-up). A Bluetooth entry can *optionally* also
  carry API credentials (in `config_entry.options`, not `.data`), in which
  case it maps orientation -> activity name/switches using the same API.

A config entry is identified as Bluetooth if `"address" in config_entry.data`.
Plain Cloud API entries carry credentials in `config_entry.data`; Bluetooth
entries carry optional API credentials in `config_entry.options` (see
`config_flow.py`'s `async_step_bluetooth_api`) — this asymmetry trips people
up, check which one you're reading before assuming credentials are missing.

## Architecture notes worth knowing before changing `__init__.py` or `switch.py`

- `switch.py` depends on the `EarlyAPICoordinator` that `sensor.py` /
  `bluetooth_sensor.py` creates and stores in
  `hass.data[DOMAIN][entry_id]["coordinator"]`. `__init__.py` forwards the
  `SENSOR` platform and fully awaits it *before* forwarding `SWITCH`,
  specifically because `hass.config_entries.async_forward_entry_setups`
  runs the platforms it's given concurrently (`asyncio.gather`), not in
  list order — do not collapse this back into a single call with both
  platforms, it reintroduces a real race (switches silently not created
  for Bluetooth+API entries, since their coordinator setup does real
  awaited I/O — BLE connect, sign-in, activity fetch — before storing
  itself).
- `EarlyActivitySwitch.unique_id` is scoped by `config_entry.entry_id` for
  Bluetooth entries but *not* for plain Cloud API entries (kept unscoped
  for backwards compatibility with already-deployed entity registries).
  The README documents running a Cloud API entry and a Bluetooth entry for
  the same account simultaneously, which is why the scoping exists at all —
  don't remove it without checking that collision case.
- A missing `"coordinator"` key in `hass.data[DOMAIN][entry_id]` is a
  normal, expected state (no API credentials configured), not an error —
  it's logged at `debug`, not `error`. Don't "fix" that log level back
  without re-reading why in `switch.py`.

## Environment / testing gotcha

`requirements-test.txt` pins `homeassistant>=2026.7.0` (the first release
patched for a security advisory). Those releases require Python >=3.14.2 and
hard-pin `requests==2.34.2`, so the CI `test` job runs on Python 3.14 only
and `requests` / `bleak` floors must stay compatible with HA's own pins
(`bleak>=3.0,<4`). Older Python (3.11/3.12) can no longer install the test
requirements. `requirements-test.txt` also lists `aiousbwatcher`, `serialx`
and `aiohasupervisor`: HA doesn't install component requirements with the core
package, and importing `homeassistant.components.bluetooth` pulls in `usb` and
`hassio`, so a new HA release that adds a component dependency shows up as a
`ModuleNotFoundError` at test collection. Tests that build `ConfigEntry`
directly must pass every keyword-only argument the current HA requires
(`discovery_keys`, `options`, `subentries_data`).

If Dependabot can't open a PR for a bump, the usual cause is a
Python-version or transitive-pin mismatch like this one — verify with
`uv pip compile requirements-test.txt requirements.txt --python-version 3.14.2`.

## Commands

```bash
# Install
pip install -r requirements-test.txt -r requirements.txt

# Run the full test suite (188+ tests, mocked HA - no real HA install needed)
python -m pytest tests/ -v

# With coverage (CI requires >=80%)
python -m pytest tests/ --cov=custom_components/early --cov-fail-under=80

# Format / lint (must pass before pushing - CI enforces all of these)
black custom_components/early/ tests/
isort --profile=black custom_components/early/ tests/
flake8 custom_components/early/ tests/ --select=E9,F63,F7,F82   # hard errors
python -m py_compile custom_components/early/*.py
```

If the local Python is older than 3.14.2, the pinned `homeassistant` can't be
installed locally; the tests are fully mocked, so you can still run them with
an older interpreter after installing the other test requirements by hand,
and rely on CI for the real 3.14 run.

## Conventions

- Formatting is `black` + `isort --profile=black`, enforced in CI (`lint`
  job in `.github/workflows/ci.yml`) — run both before pushing.
- Bump `custom_components/early/manifest.json`'s `version` for any
  user-facing behavior change (new entities, changed entity behavior),
  matching past releases (e.g. 1.1.0 for Bluetooth activity mapping, 1.2.0
  for Bluetooth+API switches). Pure docs/CI/test changes don't need a bump.
- CI (`.github/workflows/ci.yml`): `test` job runs pytest + coverage on
  Python 3.14; `lint` job runs black/isort/flake8.
  `.github/workflows/validate.yml`: HACS validation + `hassfest` (Home
  Assistant's own manifest/structure checks) — these must live under
  `.github/workflows/`, not any other `.github/` subdirectory, or GitHub
  Actions silently won't run them.
- Tests are fully mocked (no real Home Assistant install required to run
  them) — see fixtures in `tests/conftest.py` and `tests/README.md` for
  what's available.
