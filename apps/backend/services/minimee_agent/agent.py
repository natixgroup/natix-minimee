"""
Minimee Agent - LangChain-based agent with tools and RAG
"""
from typing import Optional, List, Dict, Any, Tuple
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import BaseMessage
from sqlalchemy.orm import Session
from models import Agent
from .llm_wrapper import create_minimee_llm
from .retriever import create_advanced_retriever
from .memory import create_conversation_memory
from .prompts import create_agent_prompt
from .tools.conversation_tools import (
    create_search_conversation_tool,
    create_get_recent_messages_tool,
    create_summarize_conversation_tool
)
from .tools.whatsapp_tools import (
    create_send_whatsapp_message_tool,
    create_get_whatsapp_status_tool
)
from .tools.gmail_tools import (
    create_search_gmail_tool,
    create_get_gmail_thread_tool,
    create_draft_gmail_reply_tool
)
from .tools.user_tools import (
    create_get_user_preferences_tool,
    create_get_user_settings_tool
)
from .tools.calculation_tools import calculate
from .tools.utility_tools import (
    get_current_date,
    get_current_time,
    calculate_date_difference,
    get_weather,
    search_web,
    convert_currency,
    get_timezone_info
)
from services.logs_service import log_to_db
# Import generate_response_options locally to avoid circular import
# from services.approval_flow import generate_response_options
from models import PendingApproval


class MinimeeAgent:
    """
    LangChain-based agent for Minimee with tools, RAG, and intelligent approval
    """
    
    def __init__(
        self,
        agent: Agent,
        db: Session,
        user_id: int,
        llm: Optional[BaseLanguageModel] = None,
        conversation_id: Optional[str] = None,
        included_sources: Optional[List[str]] = None,
        relation_type_id: Optional[int] = None,
        contact_id: Optional[int] = None
    ):
        """
        Initialize Minimee Agent
        
        Args:
            agent: Agent model from database
            db: Database session
            user_id: User ID
            llm: Optional LangChain LLM (will create MinimeeLLM if not provided)
            conversation_id: Optional conversation ID for memory
            included_sources: List of sources to include in RAG context (whatsapp, gmail). If None or empty, all sources included.
            relation_type_id: Optional relation type ID for filtering user context
            contact_id: Optional contact ID for filtering user context
        """
        # Store agent attributes to avoid detached instance errors
        # Access all needed attributes while agent is still attached
        self.agent_id = agent.id
        self.agent_name = agent.name
        self.agent_role = agent.role
        self.agent_prompt = agent.prompt
        self.agent_style = agent.style
        self.agent_enabled = agent.enabled
        self.agent_approval_rules = agent.approval_rules
        self.agent_whatsapp_display_name = agent.whatsapp_display_name
        
        # Keep reference to agent model for compatibility (but it may be detached)
        self.agent = agent
        
        self.db = db
        self.user_id = user_id
        self.conversation_id = conversation_id or f"agent-{self.agent_id}-{user_id}"
        self.included_sources = included_sources
        self.relation_type_id = relation_type_id
        self.contact_id = contact_id
        
        # Load user context (filtered by visibility rules)
        from services.user_identity_extractor import get_user_context_for_agent
        self.user_context = get_user_context_for_agent(
            db=db,
            user_id=user_id,
            relation_type_id=relation_type_id,
            contact_id=contact_id
        )
        
        # Create LLM if not provided
        if llm is None:
            llm = create_minimee_llm(db=db, user_id=user_id)
        self.llm = llm
        
        # Create retriever for RAG with source filtering
        self.retriever = create_advanced_retriever(
            llm=llm,
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            included_sources=included_sources
        )
        
        # Create RAG chain for automatic context injection
        from .rag_chain import create_rag_chain
        from .prompts import create_agent_prompt
        # Create a temporary agent-like object for prompt creation
        from types import SimpleNamespace
        agent_for_prompt = SimpleNamespace(
            name=self.agent_name,
            role=self.agent_role,
            prompt=self.agent_prompt,
            style=self.agent_style,
            approval_rules=self.agent_approval_rules
        )
        prompt_template = create_agent_prompt(
            agent_for_prompt,
            user_context=self.user_context,
            relation_type_id=self.relation_type_id
        )
        self.rag_chain = create_rag_chain(
            retriever=self.retriever,
            llm=llm,
            prompt_template=prompt_template,
            db=db,
            user_id=user_id,
            max_chunks=10,
            timeout_seconds=5.0
        )
        
        # Create conversation memory (for manual management, not for executor)
        self.memory = create_conversation_memory(
            llm=llm,
            db=db,
            conversation_id=self.conversation_id,
            user_id=user_id
        )
        
        # Create tools
        self.tools = self._create_tools()
        
        # Create agent prompt (use stored attributes to avoid detached instance)
        # Create a temporary agent-like object for prompt creation
        from types import SimpleNamespace
        agent_for_prompt = SimpleNamespace(
            name=self.agent_name,
            role=self.agent_role,
            prompt=self.agent_prompt,
            style=self.agent_style,
            approval_rules=self.agent_approval_rules
        )
        prompt = create_agent_prompt(
            agent_for_prompt,
            user_context=self.user_context,
            relation_type_id=self.relation_type_id
        )
        
        # Create ReAct agent
        react_agent = create_react_agent(
            llm=llm,
            tools=self.tools,
            prompt=prompt
        )
        
        # Create executor WITHOUT memory to avoid add_message errors
        # We'll manage memory manually in invoke()
        self.executor = AgentExecutor(
            agent=react_agent,
            tools=self.tools,
            verbose=True,
            handle_parsing_errors="Check your output and make sure it follows the format! Use tools when needed, then provide a Final Answer.",
            max_iterations=10,  # Increased further to allow tool usage
            return_intermediate_steps=True,
            max_execution_time=120  # Increased timeout to 120 seconds
            # Note: memory is NOT passed here to avoid add_message errors
        )
    
    def _create_tools(self) -> List:
        """Create all tools for the agent"""
        tools = []
        
        # Conversation tools
        tools.append(create_search_conversation_tool(self.db, self.llm, self.user_id))
        tools.append(create_get_recent_messages_tool(self.db, self.user_id))
        tools.append(create_summarize_conversation_tool(self.db, self.user_id))
        
        # WhatsApp tools
        tools.append(create_send_whatsapp_message_tool(self.db, self.agent))
        tools.append(create_get_whatsapp_status_tool(self.db, self.user_id))
        
        # Gmail tools
        tools.append(create_search_gmail_tool(self.db, self.user_id))
        tools.append(create_get_gmail_thread_tool(self.db, self.user_id))
        tools.append(create_draft_gmail_reply_tool(self.db, self.user_id))
        
        # User tools
        tools.append(create_get_user_preferences_tool(self.db, self.user_id))
        tools.append(create_get_user_settings_tool(self.db, self.user_id))
        
        # Calculation tool
        tools.append(calculate)
        
        # Utility tools (date, time, weather, etc.)
        tools.append(get_current_date)
        tools.append(get_current_time)
        tools.append(calculate_date_difference)
        tools.append(get_weather)
        tools.append(search_web)
        tools.append(convert_currency)
        tools.append(get_timezone_info)
        
        return tools
    
    def should_require_approval(
        self,
        response: str,
        confidence: Optional[float] = None
    ) -> bool:
        """
        Determine if response requires approval based on agent's approval_rules
        
        Args:
            response: Generated response text
            confidence: Optional confidence score (0-1)
        
        Returns:
            True if approval is required, False otherwise
        """
        rules = self.agent.approval_rules or {}
        
        # Check confidence threshold
        if confidence is not None and "auto_approve_confidence_threshold" in rules:
            threshold = rules["auto_approve_confidence_threshold"]
            if confidence >= threshold:
                return False  # Auto-approve if confidence is high enough
        
        # Check for keywords that require approval
        if "require_approval_keywords" in rules:
            keywords = rules["require_approval_keywords"]
            if keywords and any(keyword.lower() in response.lower() for keyword in keywords):
                return True  # Require approval
        
        # Check message length
        if "max_auto_approve_length" in rules:
            max_len = rules["max_auto_approve_length"]
            if len(response) > max_len:
                return True  # Require approval for long messages
        
        # Check if simple messages can be auto-approved
        if rules.get("auto_approve_simple_messages", False):
            # Simple heuristic: short messages without complex punctuation
            if len(response) < 100 and response.count("?") + response.count("!") < 2:
                return False  # Auto-approve simple messages
        
        # Default: require approval if no rules match
        return True
    
    async def invoke(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        chat_history: Optional[List[BaseMessage]] = None,
        require_approval: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Invoke agent with user message (async)
        
        Args:
            user_message: User's message
            conversation_id: Conversation ID (uses instance default if not provided)
            chat_history: Optional chat history
            require_approval: Override approval requirement (None = auto-decide)
        
        Returns:
            Dict with 'response', 'requires_approval', 'options' (if approval needed)
        """
        conv_id = conversation_id or self.conversation_id
        
        try:
            # Invoke agent (executor.invoke is sync, so we run it in a thread)
            import asyncio
            import concurrent.futures
            
            def run_invoke():
                # Retrieve RAG context first
                rag_result = self.rag_chain.invoke({"input": user_message})
                rag_context = rag_result.get("context", "")
                
                # Prepare input with chat history and RAG context
                input_data = {
                    "input": user_message,
                    "context": rag_context,  # Inject RAG context
                }
                # Add chat history if available
                if chat_history:
                    input_data["chat_history"] = chat_history
                elif hasattr(self.memory, 'chat_memory') and self.memory.chat_memory:
                    input_data["chat_history"] = self.memory.chat_memory.messages
                return self.executor.invoke(input_data)
            
            # Run sync invoke in thread pool
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(executor, run_invoke)
            
            response = result.get("output", "")
            
            # Manually save messages to memory (since we don't pass memory to executor)
            try:
                if hasattr(self.memory, 'chat_memory') and self.memory.chat_memory:
                    from langchain_core.messages import HumanMessage, AIMessage
                    # Add user message
                    self.memory.chat_memory.add_user_message(user_message)
                    # Add AI response
                    if response:
                        self.memory.chat_memory.add_ai_message(response)
            except Exception as mem_error:
                # Log but don't fail if memory save fails
                log_to_db(self.db, "WARNING", f"Failed to save to memory: {str(mem_error)}", service="minimee_agent")
            
            # Determine if approval is needed
            if require_approval is None:
                # Calculate confidence (simplified - could use actual similarity score)
                confidence = 0.8  # Default confidence
                requires_approval = self.should_require_approval(response, confidence)
            else:
                requires_approval = require_approval
            
            if requires_approval:
                # Generate multiple options for approval
                # For now, create a single option (can be enhanced)
                options = [response]
                
                # Try to generate more options if possible (async wrapper)
                try:
                    import asyncio
                    from models import Message
                    from datetime import datetime
                    
                    # Create a temporary message for approval flow
                    temp_message = Message(
                        content=user_message,
                        sender="User",
                        timestamp=datetime.utcnow(),
                        source="dashboard",
                        conversation_id=conv_id,
                        user_id=self.user_id
                    )
                    
                    # Generate options (sync wrapper for async function)
                    # Import locally to avoid circular import
                    from services.approval_flow import generate_response_options
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # If loop is running, use thread executor
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(
                                    asyncio.run,
                                    generate_response_options(
                                        db=self.db,
                                        message=temp_message,
                                        num_options=3
                                    )
                                )
                                message_options = future.result()
                        else:
                            message_options = loop.run_until_complete(
                                generate_response_options(
                                    db=self.db,
                                    message=temp_message,
                                    num_options=3
                                )
                            )
                    except RuntimeError:
                        message_options = asyncio.run(
                            generate_response_options(
                                db=self.db,
                                message=temp_message,
                                num_options=3
                            )
                        )
                    
                    options = message_options.options
                except Exception as e:
                    log_to_db(self.db, "WARNING", f"Failed to generate approval options: {str(e)}", service="minimee_agent")
                    # Use single response as option
                    options = [response]
                
                return {
                    "response": response,
                    "requires_approval": True,
                    "options": options
                }
            else:
                return {
                    "response": response,
                    "requires_approval": False,
                    "options": None
                }
        except Exception as e:
            log_to_db(self.db, "ERROR", f"Agent invoke failed: {str(e)}", service="minimee_agent")
            raise
    
    async def invoke_stream(
        self,
        user_message: str,
        conversation_id: Optional[str] = None,
        chat_history: Optional[List[BaseMessage]] = None
    ):
        """
        Invoke agent with streaming response
        
        Args:
            user_message: User's message
            conversation_id: Conversation ID
            chat_history: Optional chat history
        
        Yields:
            Token chunks as they are generated
        """
        # For streaming, we'll use the LLM directly with the agent's prompt
        # This is a simplified version - full streaming support would require more work
        conv_id = conversation_id or self.conversation_id
        
        try:
            # Retrieve RAG context first
            rag_result = self.rag_chain.invoke({"input": user_message})
            rag_context = rag_result.get("context", "")
            
            # Build prompt with tools context and RAG context
            # Create agent-like object for prompt
            from types import SimpleNamespace
            agent_for_prompt = SimpleNamespace(
                name=self.agent_name,
                role=self.agent_role,
                prompt=self.agent_prompt,
                style=self.agent_style,
                approval_rules=self.agent_approval_rules
            )
            prompt_template = create_agent_prompt(
                agent_for_prompt,
                user_context=self.user_context,
                relation_type_id=self.relation_type_id
            )
            formatted_prompt = prompt_template.format_messages(
                input=user_message,
                context=rag_context,  # Inject RAG context
                chat_history=chat_history or self.memory.chat_memory.messages,
                tools="\n".join([f"{tool.name}: {tool.description}" for tool in self.tools]),
                tool_names=", ".join([tool.name for tool in self.tools]),
                agent_scratchpad=""
            )
            
            # Stream from LLM
            from services.llm_router import generate_llm_response_stream
            async for token_data in generate_llm_response_stream(
                prompt=str(formatted_prompt[-1].content),
                db=self.db,
                user_id=self.user_id
            ):
                yield token_data
        except Exception as e:
            log_to_db(self.db, "ERROR", f"Agent stream failed: {str(e)}", service="minimee_agent")
            yield {"error": str(e), "done": True}

