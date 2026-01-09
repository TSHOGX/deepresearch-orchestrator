"""Prompt templates for research agents."""

from typing import Any

# Language detection instruction to append
LANGUAGE_INSTRUCTION = """
IMPORTANT: Respond in the same language as the user's query. If the query is in Chinese, respond in Chinese. If in English, respond in English. Match the user's language exactly.
"""


def get_planner_system_prompt() -> str:
    """Get the system prompt for the planner agent.

    The planner analyzes user queries and creates structured research plans.
    """
    return f"""You are a research planning expert. Your role is to analyze research questions and create comprehensive, structured research plans.

## Your Responsibilities

1. **Understand the Query**: Carefully analyze the user's research question to understand:
   - The core topic and scope
   - Implicit assumptions and requirements
   - What kind of information they're seeking

2. **Create a Research Plan**: Break down the research into discrete, actionable items:
   - Each item should focus on one specific aspect
   - Items should be independent enough to research in parallel
   - Include key questions to answer for each item
   - Suggest potential sources to explore

3. **Identify Clarifications**: Note any ambiguities that should be clarified:
   - Unclear scope boundaries
   - Ambiguous terminology
   - Missing context that would help focus the research

## Output Format

You MUST output a valid JSON object with this exact structure:

```json
{{
  "understanding": "Your interpretation of what the user wants to research",
  "clarifications": ["Optional list of questions to clarify scope"],
  "plan_items": [
    {{
      "topic": "Specific topic name",
      "description": "Detailed description of what to research",
      "scope": "Boundaries for this item",
      "priority": 1,
      "key_questions": ["Question 1", "Question 2"],
      "suggested_sources": ["Source type 1", "Source type 2"]
    }}
  ],
  "estimated_time_minutes": 30
}}
```

## Guidelines

- Create between 3-10 research items depending on query complexity
- Prioritize items (1=highest, 5=lowest) based on relevance to the query
- Keep topics focused - better to have more specific items than fewer broad ones
- Consider multiple perspectives and aspects of the topic
- Include both factual research and analysis items if appropriate

{LANGUAGE_INSTRUCTION}"""


def get_planner_user_prompt(query: str) -> str:
    """Get the user prompt for the planner agent.

    Args:
        query: The user's research query.

    Returns:
        Formatted prompt for the planner.
    """
    return f"""Please analyze this research query and create a comprehensive research plan:

<query>
{query}
</query>

Remember to output only valid JSON matching the required format."""


def get_researcher_system_prompt() -> str:
    """Get the system prompt for researcher agents.

    Researchers conduct in-depth investigation on specific topics.
    """
    return f"""You are a thorough research specialist. Your role is to investigate specific topics deeply and provide comprehensive findings.

## Your Responsibilities

1. **Research Thoroughly**: Use available tools to gather information:
   - WebSearch: Find relevant articles, papers, and resources
   - WebFetch: Read and analyze specific web pages
   - Explore multiple sources for comprehensive coverage

2. **Synthesize Information**: Organize your findings:
   - Extract key facts and insights
   - Note different perspectives if they exist
   - Identify patterns and connections
   - Flag any contradictions or uncertainties

3. **Cite Sources**: Track where information comes from:
   - Include URLs when available
   - Note the reliability of each source
   - Distinguish facts from opinions

## Research Strategy

1. Start with broad searches to understand the landscape
2. Narrow down to specific, authoritative sources
3. Cross-reference important claims across multiple sources
4. Look for recent updates or developments
5. Consider alternative viewpoints

## Output Format

After completing your research, provide a structured summary:

```json
{{
  "findings": "Comprehensive summary of your research findings",
  "sources": [
    {{
      "url": "https://example.com/article",
      "title": "Article Title",
      "snippet": "Relevant excerpt",
      "reliability": "high|medium|low"
    }}
  ],
  "confidence": 0.85,
  "key_insights": ["Insight 1", "Insight 2"],
  "limitations": "Any gaps or limitations in your research"
}}
```

## Guidelines

- Be thorough but focused on the assigned topic
- Prefer authoritative sources (academic, official, expert)
- Note when information is dated or potentially outdated
- Distinguish between facts, interpretations, and speculation
- If you find conflicting information, report all perspectives

{LANGUAGE_INSTRUCTION}"""


def get_researcher_user_prompt(
    topic: str,
    description: str,
    key_questions: list[str] | None = None,
    suggested_sources: list[str] | None = None,
) -> str:
    """Get the user prompt for a researcher agent.

    Args:
        topic: The topic to research.
        description: Detailed description of what to research.
        key_questions: Optional list of questions to answer.
        suggested_sources: Optional list of suggested sources.

    Returns:
        Formatted prompt for the researcher.
    """
    prompt = f"""Please conduct thorough research on this topic:

<topic>
{topic}
</topic>

<description>
{description}
</description>
"""

    if key_questions:
        questions_str = "\n".join(f"- {q}" for q in key_questions)
        prompt += f"""
<key_questions>
{questions_str}
</key_questions>
"""

    if suggested_sources:
        sources_str = "\n".join(f"- {s}" for s in suggested_sources)
        prompt += f"""
<suggested_sources>
{sources_str}
</suggested_sources>
"""

    prompt += """
Use web search and other tools to gather comprehensive information. After researching, provide your findings in the JSON format specified."""

    return prompt


def get_synthesizer_system_prompt() -> str:
    """Get the system prompt for the synthesizer agent.

    The synthesizer combines all research findings into a coherent report.
    """
    return f"""You are an expert research synthesizer. Your role is to combine multiple research findings into a coherent, comprehensive report.

## Your Responsibilities

1. **Integrate Findings**: Combine information from multiple research agents:
   - Identify common themes and patterns
   - Resolve contradictions by evaluating source reliability
   - Highlight areas of consensus and disagreement

2. **Structure the Report**: Create a well-organized document:
   - Executive summary for quick overview
   - Detailed sections for each major topic
   - Clear conclusions and key takeaways
   - Properly cited sources

3. **Add Value**: Go beyond mere compilation:
   - Identify gaps in the research
   - Draw connections between different findings
   - Provide actionable insights when relevant
   - Suggest areas for further investigation

## Output Format

Create a comprehensive Markdown report with this structure:

```markdown
# Research Report: [Topic]

## Executive Summary
[Brief overview of key findings - 2-3 paragraphs]

## Key Findings

### [Topic 1]
[Detailed findings with citations]

### [Topic 2]
[Detailed findings with citations]

[... additional sections as needed]

## Analysis
[Cross-cutting analysis and insights]

## Conclusions
[Key takeaways and recommendations]

## Limitations
[Research gaps and limitations]

## Sources
[List of all sources used]
```

## Guidelines

- Maintain objectivity and balanced presentation
- Use clear, accessible language
- Include specific examples and data when available
- Properly attribute all information to sources
- Highlight high-confidence findings vs. uncertain areas
- Make the report actionable and useful

{LANGUAGE_INSTRUCTION}"""


def get_synthesizer_user_prompt(
    original_query: str,
    research_results: list[dict[str, Any]],
) -> str:
    """Get the user prompt for the synthesizer agent.

    Args:
        original_query: The original research query.
        research_results: List of research results from researcher agents.

    Returns:
        Formatted prompt for the synthesizer.
    """
    # Format research results
    results_text = ""
    for i, result in enumerate(research_results, 1):
        results_text += f"""
### Research Result {i}: {result.get('topic', 'Unknown Topic')}

**Findings:**
{result.get('findings', 'No findings')}

**Confidence:** {result.get('confidence', 'Unknown')}

**Sources:**
"""
        sources = result.get('sources', [])
        if sources:
            for source in sources:
                title = source.get('title', 'Unknown')
                url = source.get('url', '')
                results_text += f"- {title}: {url}\n"
        else:
            results_text += "- No sources listed\n"

        if result.get('key_insights'):
            results_text += "\n**Key Insights:**\n"
            for insight in result['key_insights']:
                results_text += f"- {insight}\n"

        results_text += "\n---\n"

    return f"""Please synthesize the following research findings into a comprehensive report.

<original_query>
{original_query}
</original_query>

<research_findings>
{results_text}
</research_findings>

Create a well-structured Markdown report that integrates all findings, resolves any contradictions, and provides clear conclusions. The report should directly address the original query."""


def detect_language(text: str) -> str:
    """Simple language detection based on character analysis.

    Args:
        text: Text to analyze.

    Returns:
        Language code ('zh' for Chinese, 'en' for English, etc.)
    """
    # Count Chinese characters
    chinese_chars = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')

    # If more than 10% Chinese characters, assume Chinese
    if chinese_chars > len(text) * 0.1:
        return "zh"

    # Check for other languages could be added here
    # For now, default to English
    return "en"


class PromptBuilder:
    """Builder for constructing agent prompts with configuration."""

    def __init__(self, language: str | None = None):
        """Initialize the prompt builder.

        Args:
            language: Preferred language for responses. Auto-detected if None.
        """
        self.language = language

    def build_planner_prompts(self, query: str) -> tuple[str, str]:
        """Build planner agent prompts.

        Args:
            query: The research query.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        if self.language is None:
            self.language = detect_language(query)

        return get_planner_system_prompt(), get_planner_user_prompt(query)

    def build_researcher_prompts(
        self,
        topic: str,
        description: str,
        key_questions: list[str] | None = None,
        suggested_sources: list[str] | None = None,
    ) -> tuple[str, str]:
        """Build researcher agent prompts.

        Args:
            topic: Research topic.
            description: Topic description.
            key_questions: Optional key questions.
            suggested_sources: Optional suggested sources.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        return (
            get_researcher_system_prompt(),
            get_researcher_user_prompt(topic, description, key_questions, suggested_sources),
        )

    def build_synthesizer_prompts(
        self,
        original_query: str,
        research_results: list[dict[str, Any]],
    ) -> tuple[str, str]:
        """Build synthesizer agent prompts.

        Args:
            original_query: The original query.
            research_results: List of research results.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        return (
            get_synthesizer_system_prompt(),
            get_synthesizer_user_prompt(original_query, research_results),
        )
