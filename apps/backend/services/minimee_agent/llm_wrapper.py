"""
LangChain LLM wrapper for Minimee's existing LLM system
Supports Ollama, vLLM, and OpenAI providers
"""
from typing import Optional, List, Iterator, AsyncIterator
from langchain_core.language_models.llms import BaseLLM
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.outputs import LLMResult
from sqlalchemy.orm import Session
from services.llm_router import get_llm_provider_from_db, generate_llm_response
from config import settings
import asyncio


class MinimeeLLM(BaseLLM):
    """
    LangChain LLM wrapper for Minimee's LLM router
    Supports Ollama, vLLM, and OpenAI
    """
    
    db: Optional[Session] = None
    user_id: Optional[int] = None
    model: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    
    @property
    def _llm_type(self) -> str:
        """Return type of LLM"""
        provider, _ = get_llm_provider_from_db(self.db)
        return f"minimee_{provider}"
    
    def _generate(
        self,
        prompts: List[str],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> LLMResult:
        """
        Generate LLM response (required by BaseLLM)
        """
        from langchain_core.outputs import Generation
        
        generations = []
        for prompt in prompts:
            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, use thread executor
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            asyncio.run,
                            generate_llm_response(
                                prompt=prompt,
                                model=self.model,
                                temperature=self.temperature,
                                max_tokens=self.max_tokens,
                                db=self.db,
                                user_id=self.user_id
                            )
                        )
                        text = future.result()
                else:
                    text = loop.run_until_complete(
                        generate_llm_response(
                            prompt=prompt,
                            model=self.model,
                            temperature=self.temperature,
                            max_tokens=self.max_tokens,
                            db=self.db,
                            user_id=self.user_id
                        )
                    )
            except RuntimeError:
                # No event loop, create one
                text = asyncio.run(
                    generate_llm_response(
                        prompt=prompt,
                        model=self.model,
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        db=self.db,
                        user_id=self.user_id
                    )
                )
            
            generations.append([Generation(text=text)])
        
        return LLMResult(generations=generations)
    
    async def _acall(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs
    ) -> str:
        """
        Call LLM asynchronously
        """
        return await generate_llm_response(
            prompt=prompt,
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            db=self.db,
            user_id=self.user_id
        )


def create_minimee_llm(
    db: Session,
    user_id: int,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: Optional[int] = None
) -> MinimeeLLM:
    """
    Create a MinimeeLLM instance
    
    Args:
        db: Database session
        user_id: User ID
        model: Optional model override
        temperature: Temperature for generation
        max_tokens: Maximum tokens to generate
    
    Returns:
        MinimeeLLM instance
    """
    return MinimeeLLM(
        db=db,
        user_id=user_id,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens
    )


