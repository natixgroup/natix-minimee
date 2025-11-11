"""
ReAct prompts for Minimee agents
Personalized prompts based on agent role, style, and approval rules
"""
from typing import Optional, Dict, Any
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from models import Agent


def create_agent_prompt(
    agent: Agent,
    user_context: Optional[str] = None,
    relation_type_id: Optional[int] = None
) -> ChatPromptTemplate:
    """
    Create a personalized ReAct prompt for an agent
    
    Args:
        agent: Agent model with role, prompt, style, and approval_rules
        user_context: Optional user identity context (filtered by visibility rules)
        relation_type_id: Optional relation type ID for filtering user context
    
    Returns:
        ChatPromptTemplate for ReAct agent
    """
    # Build system message from agent configuration
    # Escape curly braces in agent prompt to prevent LangChain from treating them as template variables
    escaped_prompt = agent.prompt.replace("{", "{{").replace("}", "}}")
    # But we need to keep actual template variables, so restore them
    # Common template variables that should remain: {input}, {tools}, {tool_names}, {agent_scratchpad}, {chat_history}
    # For now, we'll escape everything and let LangChain handle the template variables in the prompt structure
    
    system_parts = [
        f"You are {agent.name}, {agent.role}.",
        escaped_prompt,
    ]
    
    if agent.style:
        # Escape style too
        escaped_style = agent.style.replace("{", "{{").replace("}", "}}")
        system_parts.append(f"Communication style: {escaped_style}")
    
    # Add user identity context if available
    if user_context:
        escaped_user_context = user_context.replace("{", "{{").replace("}", "}}")
        system_parts.append(f"\nUser Identity Information:\n{escaped_user_context}\n")
        system_parts.append("Use this information to personalize your responses and understand the user's context. "
                           "Some information may be marked as '[Context only - do not mention]' - use it to inform your responses but do not explicitly state it.")
    
    # Add approval rules context if available
    if agent.approval_rules:
        approval_context = _format_approval_rules(agent.approval_rules)
        if approval_context:
            system_parts.append(f"\nApproval Rules:\n{approval_context}")
    
    # Add RAG context placeholder instruction
    system_parts.append("\nRelevant context from conversation history will be provided below. Use this context to inform your responses.")
    
    system_message = "\n".join(system_parts)
    
    # ReAct prompt template with RAG context
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_message),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", """Relevant Context from Conversation History:
{context}

You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

When responding:
- Use the provided context above to inform your responses
- Use tools to search conversation history when you need additional context beyond what's provided
- Use tools to send WhatsApp messages when appropriate
- Use get_current_date tool when asked about today's date or current time
- Use calculate tool for mathematical calculations
- Use get_weather tool for weather information (when available)
- Be concise but helpful
- Maintain the conversation flow naturally
- If you need approval for a message, indicate it clearly

Begin!

Question: {input}
Thought: {agent_scratchpad}"""),
    ])
    
    return prompt


def _format_approval_rules(rules: Dict[str, Any]) -> str:
    """
    Format approval rules into a readable string
    
    Args:
        rules: Approval rules dictionary
    
    Returns:
        Formatted string
    """
    if not rules:
        return ""
    
    parts = []
    
    if "auto_approve_confidence_threshold" in rules:
        threshold = rules["auto_approve_confidence_threshold"]
        parts.append(f"- Auto-approve if confidence > {threshold}")
    
    if rules.get("auto_approve_simple_messages", False):
        parts.append("- Auto-approve simple, straightforward messages")
    
    if "require_approval_keywords" in rules:
        keywords = rules["require_approval_keywords"]
        if keywords:
            parts.append(f"- Always require approval for messages containing: {', '.join(keywords)}")
    
    if "max_auto_approve_length" in rules:
        max_len = rules["max_auto_approve_length"]
        parts.append(f"- Auto-approve messages shorter than {max_len} characters")
    
    return "\n".join(parts) if parts else ""


def create_history_aware_prompt() -> ChatPromptTemplate:
    """
    Create prompt for history-aware retriever
    Helps reformulate queries based on conversation context
    
    Returns:
        ChatPromptTemplate for history-aware retrieval
    """
    return ChatPromptTemplate.from_messages([
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        ("user", "Given the above conversation, generate a search query to find relevant information from the conversation history. "
         "The query should be optimized for semantic search in past messages.")
    ])


