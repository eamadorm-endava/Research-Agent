import pytest
from unittest.mock import patch, MagicMock
from agent.core_agent.builder.skills_factory import get_skill


def test_get_skill_success():
    """Test that a skill is correctly loaded when the directory exists."""
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

        skill = get_skill("test-skill")

        assert skill == mock_skill
        mock_load.assert_called_once()


def test_get_skill_not_found():
    """Test that get_skill raises FileNotFoundError if directory is missing."""
    with patch(
        "agent.core_agent.builder.skills_factory.Path.exists", return_value=False
    ):
        with pytest.raises(FileNotFoundError) as exc_info:
            get_skill("non-existent-skill")

        assert "Skill directory not found" in str(exc_info.value)
