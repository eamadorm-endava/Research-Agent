import pytest
from unittest.mock import patch, MagicMock
from agent.core_agent.builder.skills_factory import get_skill_toolset


def test_get_skill_toolset_success():
    """Test that a skill toolset is correctly loaded when the directory exists."""
    with (
        patch("agent.core_agent.builder.skills_factory.Path.exists", return_value=True),
        patch("agent.core_agent.builder.skills_factory.Path.is_dir", return_value=True),
        patch(
            "agent.core_agent.builder.skills_factory.load_skill_from_dir"
        ) as mock_load,
    ):
        mock_skill = MagicMock()
        mock_skill.name = "test-skill"
        mock_load.return_value = mock_skill

        toolset = get_skill_toolset("test-skill")

        skills = toolset._list_skills()
        assert len(skills) == 1
        assert skills[0] == mock_skill
        mock_load.assert_called_once()


def test_get_skill_toolset_not_found():
    """Test that get_skill_toolset raises FileNotFoundError if directory is missing."""
    with patch(
        "agent.core_agent.builder.skills_factory.Path.exists", return_value=False
    ):
        with pytest.raises(FileNotFoundError) as exc_info:
            get_skill_toolset("non-existent-skill")

        assert "Skill directory not found" in str(exc_info.value)
