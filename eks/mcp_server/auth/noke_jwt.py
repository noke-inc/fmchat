"""
mcp_server/auth/noke_jwt.py

Single-source JWT validation for MCP: this module reuses the Agent validator
implementation to avoid divergence between Agent and MCP auth behavior.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import Callable


def _load_agent_validator() -> Callable[[str], dict]:
    """Load validate_noke_token from app/NokeAgent/auth/noke_jwt.py."""
    repo_root = Path(__file__).resolve().parents[3]
    agent_jwt_path = repo_root / "app" / "NokeAgent" / "auth" / "noke_jwt.py"

    if not agent_jwt_path.exists():
        raise RuntimeError(
            f"Agent JWT validator not found at {agent_jwt_path}. "
            "MCP expects Agent auth validator as the single source of truth."
        )

    spec = spec_from_file_location("noke_agent_jwt", str(agent_jwt_path))
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load Agent JWT validator module.")

    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    validate = getattr(module, "validate_noke_token", None)
    if not callable(validate):
        raise RuntimeError("Agent JWT validator module does not define validate_noke_token(token).")

    return validate


validate_noke_token = _load_agent_validator()

