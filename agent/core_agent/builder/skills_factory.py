from loguru import logger
from pathlib import Path
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset


def get_skill_toolset(skill_name: str) -> SkillToolset:
    """
    Dynamically loads an ADK skill from the `agent/skills/` directory.

    Args:
        skill_name (str): The name of the skill directory to load.

    Returns:
        SkillToolset: The configured ADK wrapper.
    """
    logger.info(f"Initializing ADK Skill: {skill_name}")
    skills_base_path = Path(__file__).parent.parent.parent / "skills"
    target_skill_path = skills_base_path / skill_name

    if not target_skill_path.exists() or not target_skill_path.is_dir():
        raise FileNotFoundError(f"Skill directory not found at: {target_skill_path}")

    logger.info(f"Loading ADK Skill from: {target_skill_path}")
    agent_skill = load_skill_from_dir(target_skill_path)

    logger.info(f"Successfully loaded skill: {skill_name}")
    return SkillToolset(skills=[agent_skill])
