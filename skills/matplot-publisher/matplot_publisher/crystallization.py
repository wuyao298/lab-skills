# -*- coding: utf-8 -*-
"""第六层：固化与复用层。"""

from typing import Optional

from .models import DataProfile, DecisionChain
from .profile_manager import ProfileManager

__all__ = ["crystallize", "match_profile"]


def crystallize(chain: DecisionChain, profile_dir: str = "profiles") -> str:
    """把成功决策链归档为 YAML，返回 profile_id。"""
    manager = ProfileManager(profile_dir)
    chain.profile_id = manager.save(chain)
    return chain.profile_id


def match_profile(profile: DataProfile, profile_dir: str = "profiles") -> Optional[str]:
    """匹配历史档案；≥0.8 才建议复用。"""
    return ProfileManager(profile_dir).match(profile)
