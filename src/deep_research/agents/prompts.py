"""Prompt templates for research agents."""

from typing import Any

# Language detection instruction to append
LANGUAGE_INSTRUCTION = """
IMPORTANT: Respond in the same language as the user's query. If the query is in Chinese, respond in Chinese. If in English, respond in English. Match the user's language exactly.
"""


def get_planner_thinking_prompt(batch_mode: bool = False) -> str:
    """Get the system prompt for planner's THINKING phase (Step 1).

    This prompt encourages free-form thinking and analysis without
    imposing JSON structure constraints.

    Args:
        batch_mode: If True, instruct LLM to make assumptions instead of asking clarifications.
    """
    batch_instruction = ""
    if batch_mode:
        batch_instruction = """
## BATCH MODE ACTIVE
You are running in non-interactive batch mode. DO NOT ask for clarifications.
Instead, make reasonable assumptions based on the query and document them.
"""

    return f"""You are a research planning expert. Your role is to deeply analyze research questions and think through how to approach them comprehensively.

## Your Task

Analyze the user's research query thoroughly. Think about:

1. **Core Intent**: What is the user really trying to understand?
2. **Scope & Boundaries**: What should be included vs excluded?
3. **Key Aspects**: What are the major dimensions to explore?
4. **Potential Challenges**: What might be unclear or ambiguous?
5. **Research Strategy**: How should this be broken down into researchable pieces?

{batch_instruction}
## Guidelines

- Think deeply and explore the problem space fully
- Consider multiple perspectives and angles
- Identify what information would be most valuable
- Note any ambiguities that might need clarification
- Don't worry about formatting - focus on thorough analysis

{LANGUAGE_INSTRUCTION}"""


def get_planner_extraction_prompt() -> str:
    """Get the system prompt for planner's EXTRACTION phase (Step 2).

    This prompt extracts structured data from the thinking analysis.
    Used with --json-schema to ensure valid output.
    """
    return """You are a research planning assistant. Based on the provided analysis, extract a structured research plan.

## Your Task

Convert the analysis into a structured format:

- If the analysis identifies ambiguities that need user clarification, set mode to "clarification"
- If the analysis is ready to proceed, set mode to "plan" and create specific research items

## Output Requirements

- Set "mode" to either "clarification" or "plan"
- Provide your "understanding" of the research goal
- If mode is "clarification": list questions in "clarifications"
- If mode is "plan": create "plan_items" with topic, description, scope, priority, key_questions

Be concise and precise. The schema will validate your output."""


def get_planner_system_prompt(batch_mode: bool = False) -> str:
    """Get the legacy system prompt for the planner agent.

    DEPRECATED: Use get_planner_thinking_prompt() and get_planner_extraction_prompt()
    for the Two-Step Pattern instead.

    Args:
        batch_mode: If True, instruct LLM to make assumptions instead of asking clarifications.
    """
    batch_instruction = ""
    if batch_mode:
        batch_instruction = """
## BATCH MODE ACTIVE
You are running in non-interactive batch mode. DO NOT ask for clarifications.
Instead, make reasonable assumptions based on the query and proceed directly to creating the plan.
State your assumptions in the "understanding" field.
"""

    return f"""You are a research planning expert. Your role is to analyze research questions and create comprehensive, structured research plans.

## Your Responsibilities

1. **Understand the Query**: Carefully analyze the user's research question to understand:
   - The core topic and scope
   - Implicit assumptions and requirements
   - What kind of information they're seeking

2. **Decide: Clarify or Plan**:
   - If the query is ambiguous or lacks critical context, ask clarification questions FIRST
   - If the query is clear enough, proceed directly to creating the plan
   - DO NOT output both clarifications and plan_items in the same response

3. **Create a Research Plan** (when ready): Break down the research into discrete, actionable items:
   - Each item should focus on one specific aspect
   - Items should be independent enough to research in parallel
   - Include key questions to answer for each item
   - Suggest potential sources to explore
{batch_instruction}
## Output Format

You MUST output ONLY a valid JSON object (no markdown code blocks, no extra text).

**Mode 1: Need Clarification** (use when query is ambiguous)
{{
  "mode": "clarification",
  "understanding": "Your current interpretation of the query",
  "clarifications": ["Question 1 to ask user", "Question 2 to ask user"]
}}

**Mode 2: Full Plan** (use when query is clear or after clarifications are resolved)
{{
  "mode": "plan",
  "understanding": "Your interpretation of what the user wants to research",
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

## Guidelines

- When asking clarifications, limit to 2-4 most important questions
- Create between 3-10 research items depending on query complexity
- Prioritize items (1=highest, 5=lowest) based on relevance to the query
- Keep topics focused - better to have more specific items than fewer broad ones
- Consider multiple perspectives and aspects of the topic
- Include both factual research and analysis items if appropriate

## CRITICAL REMINDER
Your response MUST be a raw JSON object only. Do NOT include:
- Markdown formatting (no ```json blocks)
- Explanatory text before or after the JSON
- Tables, bullet points, or other formatting
Start your response with {{ and end with }}. Any other format will cause a parsing error.

{LANGUAGE_INSTRUCTION}"""


def get_planner_thinking_user_prompt(
    query: str,
    clarification_context: list[tuple[str, str]] | None = None,
) -> str:
    """Get the user prompt for planner's THINKING phase.

    Args:
        query: The user's research query.
        clarification_context: Optional list of (question, answer) tuples.
    """
    context_str = ""
    if clarification_context:
        context_str = "\n\n<previous_clarifications>\n"
        for question, answer in clarification_context:
            context_str += f"Q: {question}\nA: {answer}\n\n"
        context_str += "</previous_clarifications>\n\nThe user has provided these clarifications."

    return f"""Please analyze this research query thoroughly:

<query>
{query}
</query>
{context_str}
Think deeply about:
1. What is the user really trying to understand?
2. What are the key aspects that need to be researched?
3. Are there any ambiguities that need clarification?
4. How should this be broken down into parallel research tasks?

Provide your complete analysis."""


def get_planner_extraction_user_prompt(thinking_result: str) -> str:
    """Get the user prompt for planner's EXTRACTION phase.

    Args:
        thinking_result: The output from the thinking phase.
    """
    return f"""Based on this analysis, extract a structured research plan:

<analysis>
{thinking_result}
</analysis>

Output the structured plan following the schema. If clarifications are needed, set mode to "clarification". Otherwise, set mode to "plan" and include all research items."""


def get_planner_user_prompt(
    query: str,
    clarification_context: list[tuple[str, str]] | None = None,
) -> str:
    """Get the user prompt for the planner agent.

    DEPRECATED: Use get_planner_thinking_user_prompt() and get_planner_extraction_user_prompt()
    for the Two-Step Pattern instead.

    Args:
        query: The user's research query.
        clarification_context: Optional list of (question, answer) tuples from previous clarifications.

    Returns:
        Formatted prompt for the planner.
    """
    context_str = ""
    if clarification_context:
        context_str = "\n\n<previous_clarifications>\n"
        for question, answer in clarification_context:
            context_str += f"Q: {question}\nA: {answer}\n\n"
        context_str += """</previous_clarifications>

The user has answered the clarification questions above. You now have enough information to create the research plan.
CRITICAL: You MUST now output a PLAN (mode: "plan") - do NOT ask more clarifications."""

    return f"""Please analyze this research query and create a comprehensive research plan:

<query>
{query}
</query>
{context_str}

CRITICAL OUTPUT REQUIREMENTS:
1. Output ONLY a raw JSON object - NO markdown formatting, NO code blocks, NO explanation text
2. Do NOT wrap JSON in ```json``` or any other formatting
3. The response must START with {{ and END with }}
4. Use "mode": "plan" and include "plan_items" array

Example of CORRECT output format:
{{"mode": "plan", "understanding": "...", "plan_items": [...], "estimated_time_minutes": 30}}"""


def get_researcher_system_prompt() -> str:
    """Get the system prompt for researcher agents.

    Researchers conduct in-depth investigation on specific topics.
    Output is free-form to maximize model intelligence and exploration depth.
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

After completing your research, provide a comprehensive summary including:

1. **Key Findings**: Main discoveries and insights
2. **Supporting Evidence**: Data points and quotes from sources
3. **Sources Used**: List URLs with brief descriptions and reliability assessment
4. **Confidence Level**: How confident you are in these findings (high/medium/low)
5. **Limitations**: Any gaps or areas that couldn't be fully researched

Focus on thorough, insightful research. Write naturally and comprehensively - don't worry about rigid formatting.

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
Use web search and other tools to gather comprehensive information. Focus on depth and insight over formatting. Provide your complete findings with sources."""

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

    def build_planner_prompts(
        self,
        query: str,
        batch_mode: bool = False,
        clarification_context: list[tuple[str, str]] | None = None,
    ) -> tuple[str, str]:
        """Build planner agent prompts (legacy single-step mode).

        DEPRECATED: Use build_planner_thinking_prompts() and build_planner_extraction_prompts()
        for the Two-Step Pattern instead.

        Args:
            query: The research query.
            batch_mode: If True, instruct LLM to make assumptions instead of asking.
            clarification_context: Optional history of clarification Q&As.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        if self.language is None:
            self.language = detect_language(query)

        return (
            get_planner_system_prompt(batch_mode=batch_mode),
            get_planner_user_prompt(query, clarification_context=clarification_context),
        )

    def build_planner_thinking_prompts(
        self,
        query: str,
        batch_mode: bool = False,
        clarification_context: list[tuple[str, str]] | None = None,
    ) -> tuple[str, str]:
        """Build planner THINKING phase prompts (Step 1 of Two-Step Pattern).

        Args:
            query: The research query.
            batch_mode: If True, instruct LLM to make assumptions.
            clarification_context: Optional history of clarification Q&As.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        if self.language is None:
            self.language = detect_language(query)

        return (
            get_planner_thinking_prompt(batch_mode=batch_mode),
            get_planner_thinking_user_prompt(query, clarification_context=clarification_context),
        )

    def build_planner_extraction_prompts(
        self,
        thinking_result: str,
    ) -> tuple[str, str]:
        """Build planner EXTRACTION phase prompts (Step 2 of Two-Step Pattern).

        Args:
            thinking_result: The output from the thinking phase.

        Returns:
            Tuple of (system_prompt, user_prompt).
        """
        return (
            get_planner_extraction_prompt(),
            get_planner_extraction_user_prompt(thinking_result),
        )


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
