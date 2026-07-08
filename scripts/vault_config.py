"""
Portable vault path helpers for video-knowledge.

Priority:
1. --vault passed by the caller
2. VIDEO_KNOWLEDGE_VAULT environment variable
3. config.json stored in the skill directory
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

DOMAIN_DIR = "图文视频知识库"
ENV_VAR = "VIDEO_KNOWLEDGE_VAULT"
CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


def normalize_vault_path(path_text: str | os.PathLike[str]) -> Path:
    """Return the vault root, accepting either the root or 图文视频知识库 path."""
    path = Path(path_text).expanduser()
    if path.name == DOMAIN_DIR:
        path = path.parent
    return path


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_vault_path(vault_path: str | os.PathLike[str]) -> None:
    """Persist the selected vault path next to the skill for later runs."""
    vault = normalize_vault_path(vault_path)
    data = load_config()
    data["vault_path"] = str(vault)
    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def resolve_vault_path(vault_arg: str | None = None) -> Path:
    """Resolve a vault path without hardcoded machine-specific defaults."""
    if vault_arg:
        return normalize_vault_path(vault_arg).resolve()

    env_path = os.environ.get(ENV_VAR)
    if env_path:
        return normalize_vault_path(env_path).resolve()

    configured = load_config().get("vault_path")
    if configured:
        vault = normalize_vault_path(configured).resolve()
        if vault.exists():
            return vault
        raise SystemExit(
            "已配置的知识库路径不存在："
            f"{vault}\n请重新传入 --vault，或运行 scripts/configure_vault.py 更新路径。"
        )

    raise SystemExit(
        "还没有配置知识库路径。\n"
        "请先询问用户是否已有本地知识库，并取得知识库根目录路径；"
        "然后在命令中传入 --vault <路径>，或运行 scripts/configure_vault.py <路径>。"
    )
