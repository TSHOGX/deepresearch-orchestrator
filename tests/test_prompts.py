"""Tests for agent prompts."""

import pytest

from deep_research.agents.prompts import (
    PromptBuilder,
    detect_language,
    get_planner_system_prompt,
    get_planner_user_prompt,
    get_researcher_system_prompt,
    get_researcher_user_prompt,
    get_synthesizer_system_prompt,
    get_synthesizer_user_prompt,
)


class TestLanguageDetection:
    """Test language detection."""

    def test_detect_english(self) -> None:
        """Test detecting English text."""
        text = "What are the latest developments in artificial intelligence?"
        assert detect_language(text) == "en"

    def test_detect_chinese(self) -> None:
        """Test detecting Chinese text."""
        text = "人工智能的最新发展是什么？"
        assert detect_language(text) == "zh"

    def test_detect_mixed_mostly_english(self) -> None:
        """Test mixed text that's mostly English."""
        text = "AI development in China 中国"
        assert detect_language(text) == "en"

    def test_detect_mixed_mostly_chinese(self) -> None:
        """Test mixed text that's mostly Chinese."""
        text = "人工智能在 AI 领域的应用非常广泛"
        assert detect_language(text) == "zh"


class TestPlannerPrompts:
    """Test planner prompt generation."""

    def test_system_prompt_contains_key_elements(self) -> None:
        """Test that system prompt contains key instructions."""
        prompt = get_planner_system_prompt()

        assert "research planning" in prompt.lower()
        assert "json" in prompt.lower()
        assert "understanding" in prompt.lower()
        assert "plan_items" in prompt.lower()
        assert "LANGUAGE" in prompt or "language" in prompt.lower()

    def test_user_prompt_includes_query(self) -> None:
        """Test that user prompt includes the query."""
        query = "What are the benefits of renewable energy?"
        prompt = get_planner_user_prompt(query)

        assert query in prompt
        assert "<query>" in prompt
        assert "JSON" in prompt


class TestResearcherPrompts:
    """Test researcher prompt generation."""

    def test_system_prompt_contains_key_elements(self) -> None:
        """Test that system prompt contains key instructions."""
        prompt = get_researcher_system_prompt()

        assert "research" in prompt.lower()
        assert "WebSearch" in prompt
        assert "sources" in prompt.lower()
        assert "json" in prompt.lower()
        assert "LANGUAGE" in prompt or "language" in prompt.lower()

    def test_user_prompt_basic(self) -> None:
        """Test basic user prompt generation."""
        prompt = get_researcher_user_prompt(
            topic="Renewable Energy Benefits",
            description="Research the environmental and economic benefits of renewable energy",
        )

        assert "Renewable Energy Benefits" in prompt
        assert "environmental and economic" in prompt
        assert "<topic>" in prompt

    def test_user_prompt_with_questions(self) -> None:
        """Test user prompt with key questions."""
        prompt = get_researcher_user_prompt(
            topic="Solar Power",
            description="Research solar power technology",
            key_questions=["What is the efficiency?", "What is the cost?"],
        )

        assert "What is the efficiency?" in prompt
        assert "What is the cost?" in prompt
        assert "<key_questions>" in prompt

    def test_user_prompt_with_sources(self) -> None:
        """Test user prompt with suggested sources."""
        prompt = get_researcher_user_prompt(
            topic="Climate Change",
            description="Research climate change impacts",
            suggested_sources=["IPCC reports", "NASA climate data"],
        )

        assert "IPCC reports" in prompt
        assert "NASA climate data" in prompt
        assert "<suggested_sources>" in prompt

    def test_user_prompt_with_all_options(self) -> None:
        """Test user prompt with all optional parameters."""
        prompt = get_researcher_user_prompt(
            topic="Electric Vehicles",
            description="Research EV adoption trends",
            key_questions=["Market share?", "Growth rate?"],
            suggested_sources=["Industry reports", "Government data"],
        )

        assert "Electric Vehicles" in prompt
        assert "Market share?" in prompt
        assert "Industry reports" in prompt


class TestSynthesizerPrompts:
    """Test synthesizer prompt generation."""

    def test_system_prompt_contains_key_elements(self) -> None:
        """Test that system prompt contains key instructions."""
        prompt = get_synthesizer_system_prompt()

        assert "synthesize" in prompt.lower()
        assert "report" in prompt.lower()
        assert "markdown" in prompt.lower()
        assert "Executive Summary" in prompt
        assert "LANGUAGE" in prompt or "language" in prompt.lower()

    def test_user_prompt_includes_query_and_results(self) -> None:
        """Test that user prompt includes query and research results."""
        research_results = [
            {
                "topic": "Solar Energy",
                "findings": "Solar energy has grown 20% annually",
                "confidence": 0.9,
                "sources": [
                    {"title": "Energy Report", "url": "https://example.com"}
                ],
            },
            {
                "topic": "Wind Energy",
                "findings": "Wind energy is cost competitive",
                "confidence": 0.85,
                "sources": [],
                "key_insights": ["Offshore wind is growing", "Costs declining"],
            },
        ]

        prompt = get_synthesizer_user_prompt(
            original_query="What are the prospects for renewable energy?",
            research_results=research_results,
        )

        assert "What are the prospects for renewable energy?" in prompt
        assert "Solar Energy" in prompt
        assert "grown 20% annually" in prompt
        assert "Wind Energy" in prompt
        assert "cost competitive" in prompt
        assert "Offshore wind is growing" in prompt

    def test_user_prompt_handles_empty_results(self) -> None:
        """Test that prompt handles empty results list."""
        prompt = get_synthesizer_user_prompt(
            original_query="Test query",
            research_results=[],
        )

        assert "Test query" in prompt
        assert "<research_findings>" in prompt


class TestPromptBuilder:
    """Test PromptBuilder class."""

    def test_build_planner_prompts(self) -> None:
        """Test building planner prompts."""
        builder = PromptBuilder()
        system, user = builder.build_planner_prompts("What is AI?")

        assert "research planning" in system.lower()
        assert "What is AI?" in user

    def test_build_planner_prompts_detects_language(self) -> None:
        """Test that planner prompts detect language."""
        builder = PromptBuilder()
        builder.build_planner_prompts("人工智能是什么？")

        assert builder.language == "zh"

    def test_build_planner_prompts_uses_provided_language(self) -> None:
        """Test that builder respects provided language."""
        builder = PromptBuilder(language="en")
        builder.build_planner_prompts("Test query")

        assert builder.language == "en"

    def test_build_researcher_prompts(self) -> None:
        """Test building researcher prompts."""
        builder = PromptBuilder()
        system, user = builder.build_researcher_prompts(
            topic="Machine Learning",
            description="Research ML algorithms",
            key_questions=["What are the types?"],
        )

        assert "research" in system.lower()
        assert "Machine Learning" in user
        assert "What are the types?" in user

    def test_build_synthesizer_prompts(self) -> None:
        """Test building synthesizer prompts."""
        builder = PromptBuilder()
        results = [{"topic": "Test", "findings": "Test findings"}]
        system, user = builder.build_synthesizer_prompts(
            original_query="Test query",
            research_results=results,
        )

        assert "synthesize" in system.lower()
        assert "Test query" in user
        assert "Test findings" in user
