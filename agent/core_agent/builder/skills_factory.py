from loguru import logger
from pathlib import Path
from google.adk.skills import load_skill_from_dir
from google.adk.tools.skill_toolset import SkillToolset


def get_skill_toolset(skill_names: list[str]) -> SkillToolset:
    """Dynamically loads multiple ADK skills from the agent/skills/ directory and wraps them in a single SkillToolset.

    Args:
        skill_names: list[str] -> The names of the skill directories to load.

    Returns:
        SkillToolset -> A single wrapper containing all loaded skills.
    """
    agent_skills = []
    skills_base_path = Path(__file__).parent.parent.parent / "skills"

    for skill_name in skill_names:
        logger.info(f"Initializing ADK Skill: {skill_name}")
        target_skill_path = skills_base_path / skill_name

        if not target_skill_path.exists() or not target_skill_path.is_dir():
            raise FileNotFoundError(
                f"Skill directory not found at: {target_skill_path}"
            )

        logger.info(f"Loading ADK Skill from: {target_skill_path}")
        agent_skill = load_skill_from_dir(target_skill_path)
        agent_skills.append(agent_skill)
        logger.info(f"Successfully loaded skill: {skill_name}")

    return SkillToolset(skills=agent_skills)
