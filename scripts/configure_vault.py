"""
Configure the local knowledge base path for video-knowledge.

Usage:
  python scripts/configure_vault.py "D:\\你的知识库"
"""
from __future__ import annotations

import argparse

from vault_config import DOMAIN_DIR, save_vault_path, normalize_vault_path, CONFIG_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="配置 video-knowledge 的本地知识库路径")
    parser.add_argument("vault", nargs="?", help="知识库根目录路径。也可传入 图文视频知识库 子目录路径")
    args = parser.parse_args()

    vault_text = args.vault
    if not vault_text:
        print("首次使用需要确认本地知识库路径。")
        print("如果已有知识库，请输入包含 index.html 的根目录；如果没有，请输入想创建的位置。")
        vault_text = input("知识库根目录路径: ").strip().strip('"')

    if not vault_text:
        raise SystemExit("未提供知识库路径，已取消。")

    vault = normalize_vault_path(vault_text).resolve()
    save_vault_path(vault)

    domain_dir = vault / DOMAIN_DIR
    status = "已存在" if domain_dir.exists() else "尚未创建，首次导出时会自动初始化"
    print(f"已保存知识库路径: {vault}")
    print(f"知识库内容目录: {domain_dir}（{status}）")
    print(f"配置文件: {CONFIG_PATH}")


if __name__ == "__main__":
    main()
