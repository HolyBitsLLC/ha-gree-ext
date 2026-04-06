# Contributing to Gree Climate Extended

## Development Setup

1. Clone the repo:
   ```bash
   git clone git@github.com:HolyBitsLLC/ha-gree-ext.git
   cd ha-gree-ext
   ```

2. Create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements-dev.txt
   ```

3. Run linting:
   ```bash
   ruff check .
   ```

4. Run tests:
   ```bash
   pytest tests/
   ```

## CI Requirements

All PRs must pass CI before merge:
- **Lint** — `ruff check .`
- **Test** — `pytest` with coverage
- **Validate** — JSON/YAML manifest validation

CI runs on self-hosted runners on the `main` branch and PRs targeting `main`.

## Code Style

- Python 3.12+
- async/await everywhere
- Type hints on all function signatures
- Follow Home Assistant integration conventions

## Testing with a Real Device

Enable debug logging in HA:
```yaml
logger:
  logs:
    custom_components.gree_ext: debug
    greeclimate: debug
```

Check `Extended properties for ...` log lines to verify which protocol
properties your firmware supports.

## Release Process

Releases are cut from `main` via GitHub Releases. Tag format: `vX.Y.Z`.
