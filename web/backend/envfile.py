"""Minimal `.env` loader so the backend has no third-party dependencies.

Supports `KEY=value`, optional `export ` prefix, `#` comments and single
or double quoted values. Existing environment variables win, so values
set in the shell are never overwritten by the file.
"""

import os


def load_env_file(path):
    """Load variables from `path` into os.environ. Returns the keys set."""
    loaded = []
    if not os.path.isfile(path):
        return loaded
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export "):].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if key and key not in os.environ:
                os.environ[key] = value
                loaded.append(key)
    return loaded

