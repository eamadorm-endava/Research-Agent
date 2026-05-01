from loguru import logger
from pathlib import Path
from google.adk.skills import load_skill_from_dir, Skill


def get_skill(skill_name: str) -> Skill:
    """Dynamically loads an ADK skill from the agent/skills/ directory.

    Args:
        skill_name: str -> The name of the skill directory to load.

    Returns:
        Skill -> The loaded ADK Skill object.
    """
    skills_base_path = Path(__file__).parent.parent.parent / "skills"
    logger.info(f"Initializing ADK Skill: {skill_name}")
    target_skill_path = skills_base_path / skill_name

    if not target_skill_path.exists() or not target_skill_path.is_dir():
        raise FileNotFoundError(f"Skill directory not found at: {target_skill_path}")

    logger.info(f"Loading ADK Skill from: {target_skill_path}")
    agent_skill = load_skill_from_dir(target_skill_path)
    logger.info(f"Successfully loaded skill: {skill_name}")

    return agent_skill
