"""
OVH AI Endpoints provider implementation.

This module implements the LLM provider for OVH AI Endpoints, which offers 40+ open-source AI models
through a unified OpenAI-compatible API. The provider supports automatic model selection based on
query type and context, providing optimal model routing for different use cases.

Key Features:
- Unified API endpoint for all 40+ OVH models
- Automatic model selection (conversation, coding, reasoning, vision)
- Manual model switching via chat commands
- Reasoning content display for GPT-OSS-20B and DeepSeek models
- European data sovereignty (Gravelines datacenter)
- Production-ready rate limiting and error handling
- Full Azure Search RAG integration
- Multimodal support (text, images, vision models)

Supported Model Categories:
- Conversation: Llama 3.3 70B, Mixtral 8x7B, Qwen 3 32B, Llama 3.1 8B, Mistral Nemo
- Reasoning: GPT-OSS-20B (with reasoning_content), DeepSeek-R1-Distill-Llama-70B
- Coding: Qwen 2.5 Coder 32B, Codestral Mamba
- Vision: Qwen 2.5 VL 72B (multimodal)

Configuration:
Set OVH_AI_ENDPOINTS_ACCESS_TOKEN and other OVH_* environment variables.
The provider uses the unified endpoint for seamless model switching.

Architecture:
This provider inherits from LLMProvider and reuses much of the OpenAI-compatible infrastructure,
adding OVH-specific features like automatic model selection and reasoning content handling.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from backend.settings import app_settings
from .base import LLMProvider, LLMProviderInitializationError, LLMProviderRequestError, handle_provider_errors
from .models import StandardResponse, StandardResponseAdapter, StandardChoice, StandardMessage, StandardUsage
from .utils import AzureSearchService, build_search_context
from .language_detection import get_system_message_for_language
from .i18n import get_documents_header, get_default_system_message, get_emergency_keywords


class OvhProvider(LLMProvider):
    """
    OVH AI Endpoints provider with automatic model selection and multi-model support.

    This provider handles communication with OVH's unified AI Endpoints API, supporting
    40+ open-source models through a single interface. It provides intelligent model
    selection based on query type and context.

    Key Features:
    - Automatic model selection based on query analysis
    - Manual model switching via chat commands
    - Reasoning content display for reasoning models
    - Full multimodal support for vision models
    - Production-ready rate limiting and retry logic
    - Complete Azure Search RAG integration
    - European data sovereignty compliance

    Model Categories:
    - Conversation Models: General purpose chat (Llama 3.3 70B, Mixtral 8x7B, Qwen 3 32B)
    - Reasoning Models: Advanced reasoning with visible thought process (GPT-OSS-20B, DeepSeek-R1)
    - Coding Models: Specialized for code generation (Qwen 2.5 Coder 32B, Codestral Mamba)
    - Vision Models: Multimodal with image understanding (Qwen 2.5 VL 72B)

    The provider automatically selects the optimal model based on:
    - Query content analysis (coding keywords, reasoning complexity, etc.)
    - Multimodal content detection (presence of images)
    - User preferences and manual overrides
    - Model availability and performance characteristics
    """

    def __init__(self):
        """Initialize the OVH AI Endpoints provider."""
        super().__init__()
        self.client = None
        self.search_service = AzureSearchService()
        self.logger = logging.getLogger("OvhProvider")

        # Model management
        self.current_model = None
        self.model_capabilities = {}
        self.available_models = []

        # Rate limiting
        self.request_semaphore = None
        self.last_request_time = 0
        self.request_count = 0

    async def init_client(self):
        """
        Initialize OVH AI Endpoints client with authentication and model discovery.

        This method:
        1. Validates the OVH access token
        2. Initializes the OpenAI-compatible client
        3. Discovers available models from the API
        4. Sets up rate limiting controls
        5. Configures the default model

        Raises:
            LLMProviderInitializationError: If initialization fails
        """
        if self.initialized:
            return

        try:
            self.logger.info("Initializing OVH AI Endpoints provider...")

            # Check OVH configuration
            if not hasattr(app_settings, 'ovh') or not app_settings.ovh.ai_endpoints_access_token:
                raise ValueError(
                    "OVH AI Endpoints access token not configured. "
                    "Please set OVH_AI_ENDPOINTS_ACCESS_TOKEN environment variable."
                )

            # Initialize the OpenAI-compatible client
            self.client = AsyncOpenAI(
                api_key=app_settings.ovh.ai_endpoints_access_token,
                base_url=app_settings.ovh.base_url
            )

            # Initialize rate limiting semaphore
            max_concurrent = min(app_settings.ovh.max_requests_per_minute // 4, 20)  # Conservative concurrency
            self.request_semaphore = asyncio.Semaphore(max_concurrent)

            # Load available models and capabilities
            await self._discover_available_models()

            # Set up the current model
            self.current_model = app_settings.ovh.model
            self._validate_current_model()

            self.initialized = True
            self.logger.info(f"OVH AI Endpoints provider initialized successfully with model: {self.current_model}")
            self.logger.info(f"Available models: {len(self.available_models)} discovered")

        except Exception as e:
            self.logger.error(f"Failed to initialize OVH AI Endpoints provider: {e}")
            raise LLMProviderInitializationError(f"OVH initialization failed: {e}")

    async def _discover_available_models(self):
        """
        Discover available models from OVH API and build capability map.

        This method queries the OVH models endpoint to get the current list of available models
        and builds a capability map for intelligent model selection.
        """
        try:
            self.logger.debug("Discovering available OVH models...")

            # Try to get models from API
            models_response = await self.client.models.list()
            api_models = [model.id for model in models_response.data] if hasattr(models_response, 'data') else []

            if api_models:
                self.available_models = api_models
                self.logger.info(f"Discovered {len(api_models)} models from OVH API: {api_models}")
            else:
                # Fallback to configured models if API call fails
                self._use_configured_models()

        except Exception as e:
            self.logger.warning(f"Failed to discover models from API: {e}. Using configured models.")
            self._use_configured_models()

        # Build capability map for all available models
        self._build_model_capabilities()

    def _use_configured_models(self):
        """Use models from configuration when API discovery fails."""
        all_configured_models = (
            app_settings.ovh.conversation_models +
            app_settings.ovh.reasoning_models +
            app_settings.ovh.coding_models +
            app_settings.ovh.vision_models
        )

        # Remove duplicates while preserving order
        self.available_models = list(dict.fromkeys(all_configured_models))

        if app_settings.ovh.available_models:
            # Filter to only include explicitly configured models
            self.available_models = [
                model for model in self.available_models
                if model in app_settings.ovh.available_models
            ]

        self.logger.info(f"Using configured models: {self.available_models}")

    def _build_model_capabilities(self):
        """Build a comprehensive capability map for all available models."""
        self.model_capabilities = {}

        for model in self.available_models:
            model_lower = model.lower()

            # Determine model category
            category = app_settings.ovh.get_model_category(model)

            # Build capability profile
            capabilities = {
                'category': category,
                'supports_reasoning': app_settings.ovh.supports_reasoning(model),
                'supports_multimodal': app_settings.ovh.supports_multimodal(model),
                'supports_function_calls': True,  # All OVH models support function calls
                'supports_streaming': True,       # All OVH models support streaming
                'context_length': self._estimate_context_length(model_lower),
                'specialties': self._get_model_specialties(model_lower)
            }

            self.model_capabilities[model] = capabilities

        self.logger.debug(f"Built capabilities for {len(self.model_capabilities)} models")

        # Log available conversation models for debugging
        conversation_models = [model for model, caps in self.model_capabilities.items()
                             if caps.get('category') == 'conversation']
        self.logger.debug(f"Available conversation models: {conversation_models}")

    def _estimate_context_length(self, model_name: str) -> int:
        """Estimate context length based on model name patterns."""
        if 'llama-3.3' in model_name or 'qwen-2.5-coder' in model_name:
            return 128000  # Latest models tend to have larger contexts
        elif 'qwen' in model_name or 'mixtral' in model_name:
            return 32000
        elif 'codestral' in model_name:
            return 256000  # Code models often have very large contexts
        else:
            return 32000   # Conservative default

    def _get_model_specialties(self, model_name: str) -> List[str]:
        """Get specialty tags for a model based on its name."""
        specialties = []

        if 'coder' in model_name or 'codestral' in model_name:
            specialties.extend(['coding', 'programming', 'software_development'])
        if 'vl' in model_name or 'vision' in model_name:
            specialties.extend(['vision', 'image_analysis', 'multimodal'])
        if 'gpt-oss' in model_name or 'deepseek' in model_name:
            specialties.extend(['reasoning', 'analysis', 'problem_solving'])
        if 'qwen' in model_name:
            specialties.extend(['multilingual', 'chinese', 'international'])
        if 'llama' in model_name or 'mixtral' in model_name:
            specialties.extend(['conversation', 'general_purpose'])

        return specialties

    def _validate_current_model(self):
        """Validate and adjust the current model selection."""
        if self.current_model not in self.available_models:
            if self.available_models:
                old_model = self.current_model
                # Choose a good conversation model as fallback instead of first model
                fallback_model = self._choose_fallback_conversation_model()
                self.current_model = fallback_model
                self.logger.warning(
                    f"Configured model '{old_model}' not available. "
                    f"Using '{self.current_model}' instead."
                )
            else:
                raise LLMProviderInitializationError("No available models found")

    def _choose_fallback_conversation_model(self) -> str:
        """Choose the best fallback conversation model from available models."""
        # Priority order for conversation models
        preferred_models = [
            "Meta-Llama-3_3-70B-Instruct",
            "Qwen3-32B",
            "Mixtral-8x7B-Instruct-v0_1",
            "Meta-Llama-3_1-8B-Instruct",
            "Mistral-Nemo-Instruct-2407"
        ]

        # Try to find a preferred conversation model
        for model in preferred_models:
            if model in self.available_models:
                return model

        # If none found, look for models with conversation capability
        for model in self.available_models:
            if self.model_capabilities.get(model, {}).get('category') == 'conversation':
                return model

        # If no conversation models found, exclude image generation models
        for model in self.available_models:
            model_lower = model.lower()
            if not any(keyword in model_lower for keyword in ['diffusion', 'stable-diffusion', 'image', 'vision']):
                return model

        # Last resort - return first model (shouldn't happen in normal operation)
        return self.available_models[0]

    def _analyze_query_for_optimal_model(self, messages: List[Dict[str, Any]]) -> Optional[str]:
        """
        Analyze the query to determine the optimal model for the task.

        This method examines the conversation context to intelligently select
        the best model based on content analysis and multimodal detection.

        Args:
            messages: The conversation messages

        Returns:
            Optimal model name or None if current model should be kept
        """
        if not app_settings.ovh.auto_model_selection:
            return None  # Auto-selection disabled

        if not messages:
            return None

        # Get the last user message for analysis
        last_message = messages[-1]
        content = last_message.get("content", "")

        # Handle multimodal content
        text_content = ""
        has_images = False

        if isinstance(content, list):
            # Multimodal content
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        text_content += part.get("text", "")
                    elif part.get("type") == "image_url":
                        has_images = True
        else:
            # Text-only content
            text_content = str(content)

        text_lower = text_content.lower()

        # Priority 1: Vision models for image content
        if has_images:
            vision_models = [m for m in self.available_models if m in app_settings.ovh.vision_models]
            if vision_models:
                self.logger.debug(f"Selecting vision model for image content: {vision_models[0]}")
                return vision_models[0]

        # Priority 2: Coding models for programming tasks
        coding_keywords = [
            'code', 'programming', 'python', 'javascript', 'java', 'c++', 'html', 'css',
            'sql', 'algorithm', 'function', 'debug', 'error', 'syntax', 'compile',
            'développement', 'programmation', 'algorithme', 'fonction', 'débogage',
            'erreur', 'syntaxe', 'compiler', 'script', 'api', 'framework'
        ]

        if any(keyword in text_lower for keyword in coding_keywords):
            coding_models = [m for m in self.available_models if m in app_settings.ovh.coding_models]
            if coding_models:
                self.logger.debug(f"Selecting coding model for programming task: {coding_models[0]}")
                return coding_models[0]

        # Priority 3: Reasoning models for complex analysis
        reasoning_keywords = [
            'analyze', 'reason', 'logic', 'problem', 'solve', 'complex', 'step by step',
            'explain why', 'reasoning', 'think through', 'analyser', 'raisonne',
            'logique', 'problème', 'résoudre', 'complexe', 'étape par étape',
            'explique pourquoi', 'raisonnement', 'réfléchir'
        ]

        reasoning_patterns = [
            r'pourquoi\s+(?:est-ce que|fait-on|dit-on)',  # "pourquoi est-ce que/fait-on/dit-on"
            r'comment\s+(?:faire|résoudre|analyser)',     # "comment faire/résoudre/analyser"
            r'quelle?\s+(?:est|sont)\s+(?:la|les)\s+(?:raison|cause)',  # "quelle est la raison"
            r'step\s+by\s+step',                          # "step by step"
            r'étape\s+par\s+étape',                       # "étape par étape"
        ]

        if (any(keyword in text_lower for keyword in reasoning_keywords) or
            any(re.search(pattern, text_lower) for pattern in reasoning_patterns) or
            len(text_content.split()) > 50):  # Long queries often need reasoning

            reasoning_models = [m for m in self.available_models if m in app_settings.ovh.reasoning_models]
            if reasoning_models:
                self.logger.debug(f"Selecting reasoning model for complex analysis: {reasoning_models[0]}")
                return reasoning_models[0]

        # Priority 4: Multilingual models for non-English content
        if self._detect_non_english_content(text_content):
            multilingual_models = [m for m in self.available_models if 'qwen' in m.lower()]
            if multilingual_models:
                self.logger.debug(f"Selecting multilingual model for non-English content: {multilingual_models[0]}")
                return multilingual_models[0]

        # Default: Keep current model if it's suitable for conversation
        current_category = self.model_capabilities.get(self.current_model, {}).get('category', 'conversation')
        if current_category == 'conversation':
            return None  # Keep current model

        # Fallback: Select best conversation model
        conversation_models = [m for m in self.available_models if m in app_settings.ovh.conversation_models]
        if conversation_models:
            return conversation_models[0]

        return None  # Keep current model as last resort

    def _detect_non_english_content(self, text: str) -> bool:
        """Detect if text contains significant non-English content."""
        if not text:
            return False

        # Simple heuristic: check for non-ASCII characters or common non-English words
        non_english_indicators = [
            'ç', 'é', 'è', 'à', 'ù', 'ê', 'ô', 'î', 'â', 'û',  # French
            '你', '我', '是', '的', '了', '在', '有', '和', '人',      # Chinese
            'ñ', 'á', 'í', 'ó', 'ú', 'ü',                      # Spanish
            'ä', 'ö', 'ü', 'ß',                                # German
        ]

        non_english_words = [
            'bonjour', 'merci', 'français', 'oui', 'non', 'comment', 'quoi', 'pourquoi',
            'hola', 'gracias', 'español', 'sí', 'no', 'cómo', 'qué', 'por qué',
            'hallo', 'danke', 'deutsch', 'ja', 'nein', 'wie', 'was', 'warum',
        ]

        text_lower = text.lower()

        # Check for non-English characters
        non_ascii_ratio = sum(1 for char in text if ord(char) > 127) / len(text)
        if non_ascii_ratio > 0.1:  # More than 10% non-ASCII
            return True

        # Check for non-English indicators
        if any(indicator in text for indicator in non_english_indicators):
            return True

        # Check for non-English words
        words = text_lower.split()
        non_english_word_count = sum(1 for word in words if word in non_english_words)
        if non_english_word_count > len(words) * 0.1:  # More than 10% non-English words
            return True

        return False

    @handle_provider_errors("OVH")
    async def send_request(
        self,
        messages: List[Dict[str, Any]],
        stream: bool = True,
        **kwargs
    ) -> Tuple[Any, Optional[str]]:
        """
        Send request to OVH AI Endpoints with intelligent model selection and rate limiting.

        This method handles:
        - Automatic model selection based on query analysis
        - Rate limiting compliance with OVH's 400/min limit
        - Retry logic for 429 errors
        - Azure Search RAG integration
        - Language detection and localization
        - Reasoning content handling for reasoning models

        Args:
            messages: List of messages in OpenAI chat format
            stream: Whether to return a streaming response
            **kwargs: Additional parameters including model override, response_size, etc.

        Returns:
            Tuple of (response, request_id)

        Raises:
            LLMProviderRequestError: If the request fails after retries
        """
        await self.init_client()

        # Rate limiting with semaphore
        async with self.request_semaphore:
            # Apply rate limiting delay if needed
            await self._apply_rate_limiting()

            # Detect language from user's last message
            if kwargs.get("_skip_language_detection", False):
                detected_language = "en"  # Default for internal calls
                self.logger.debug("Skipping language detection for internal call")
            else:
                user_message = messages[-1]["content"] if messages else ""
                detected_language = await self.detect_language_with_llm(user_message)
                self.logger.debug(f"Detected language: {detected_language}")

            # Intelligent model selection
            optimal_model = self._select_optimal_model_for_request(messages, **kwargs)

            # Convert OpenAI messages and enhance with Azure Search if configured
            enhanced_messages = await self._enhance_with_search_context(
                messages,
                detected_language=detected_language,
                **kwargs
            )

            # Build request parameters
            request_params = await self._build_request_parameters(
                enhanced_messages,
                stream,
                optimal_model,
                **kwargs
            )

            # Log the model being used for this request
            self.logger.info(f"[OVH MODEL] Using model: {optimal_model}")

            # Execute request with retry logic
            response = await self._execute_request_with_retry(request_params)

            # Handle citations for streaming responses
            if stream and hasattr(self, '_current_search_citations') and self._current_search_citations:
                response = self._inject_citations_in_stream(response)

            # Generate request ID
            request_id = f"ovh-{response.id}" if hasattr(response, 'id') else f"ovh-{id(response)}"

            return response, request_id

    async def _apply_rate_limiting(self):
        """Apply intelligent rate limiting to respect OVH's 400 requests/minute limit."""
        import time

        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        # Reset counter every minute
        if time_since_last > 60:
            self.request_count = 0

        # Apply delay if we're approaching the limit
        if self.request_count >= app_settings.ovh.max_requests_per_minute:
            delay = 60 - time_since_last + 1  # Wait until next minute
            if delay > 0:
                self.logger.info(f"Rate limiting: waiting {delay:.1f} seconds")
                await asyncio.sleep(delay)
                self.request_count = 0

        self.request_count += 1
        self.last_request_time = current_time

    def _select_optimal_model_for_request(self, messages: List[Dict[str, Any]], **kwargs) -> str:
        """Select the optimal model for this specific request."""
        # Check for manual model override
        if "model" in kwargs:
            override_model = kwargs["model"]
            if override_model in self.available_models:
                if override_model != self.current_model:
                    self.logger.info(f"Using manual model override: {override_model}")
                return override_model
            else:
                self.logger.warning(f"Requested model '{override_model}' not available, using auto-selection")

        # Try automatic model selection
        optimal_model = self._analyze_query_for_optimal_model(messages)

        if optimal_model and optimal_model != self.current_model:
            self.logger.info(f"Auto-selected optimal model: {optimal_model} (was: {self.current_model})")
            return optimal_model

        return self.current_model

    async def _build_request_parameters(
        self,
        messages: List[Dict[str, Any]],
        stream: bool,
        model: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Build the complete request parameters for the OVH API call."""
        # Get max_tokens based on response size
        response_size = kwargs.get("response_size", "medium")
        max_tokens = self._get_max_tokens_for_response_size("ovh", response_size)

        # Base parameters
        request_params = {
            "messages": messages,
            "stream": stream,
            "model": model,
            "max_tokens": max_tokens,
            "temperature": kwargs.get("temperature", app_settings.ovh.temperature),
            "top_p": kwargs.get("top_p", app_settings.ovh.top_p),
        }

        # Add reasoning parameters for reasoning models
        # Note: reasoning_effort parameter temporarily disabled due to API compatibility issues
        # if app_settings.ovh.supports_reasoning(model):
        #     reasoning_effort = kwargs.get("reasoning_effort", app_settings.ovh.reasoning_effort)
        #     request_params["reasoning_effort"] = reasoning_effort
        #     self.logger.debug(f"Added reasoning_effort: {reasoning_effort} for model: {model}")

        # Add optional parameters if provided
        for param in ['user', 'stop', 'tools', 'tool_choice', 'frequency_penalty', 'presence_penalty']:
            if param in kwargs and kwargs[param] is not None:
                request_params[param] = kwargs[param]

        # Remove None values to avoid API errors
        request_params = {k: v for k, v in request_params.items() if v is not None}

        return request_params

    async def _execute_request_with_retry(self, request_params: Dict[str, Any]) -> Any:
        """Execute the API request with intelligent retry logic for rate limiting."""
        max_retries = 3
        base_delay = 1.0

        for attempt in range(max_retries):
            try:
                response = await self.client.chat.completions.create(**request_params)
                return response

            except Exception as e:
                # Check if this is a rate limit error
                if hasattr(e, 'status_code') and e.status_code == 429:
                    if attempt < max_retries - 1 and app_settings.ovh.retry_after_429:
                        # Extract retry-after header if available
                        retry_after = getattr(e, 'retry_after', None)
                        if retry_after:
                            delay = min(float(retry_after), 60)  # Cap at 1 minute
                        else:
                            delay = min(base_delay * (2 ** attempt), 30)  # Exponential backoff, cap at 30s

                        self.logger.warning(
                            f"Rate limited (attempt {attempt + 1}/{max_retries}), "
                            f"retrying after {delay:.1f} seconds"
                        )
                        await asyncio.sleep(delay)
                        continue

                # Re-raise non-rate-limit errors or final attempt
                raise e

        # This should not be reached, but just in case
        raise LLMProviderRequestError("Max retries exceeded")

    async def _enhance_with_search_context(
        self,
        messages: List[Dict[str, Any]],
        detected_language: str = "en",
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Enhance OVH messages with Azure Search context if configured, with multilingual support.

        This method reuses the Azure Search integration from the existing providers,
        ensuring consistent RAG functionality across all LLM providers.

        Args:
            messages: Messages in OpenAI format
            detected_language: Detected language code for response localization
            **kwargs: Additional parameters including search configuration

        Returns:
            Enhanced messages with search context and multilingual system message
        """
        # Start with a copy of messages
        enhanced_messages = messages.copy()

        # Build system message with language awareness and response size preference
        base_system_message = getattr(app_settings.ovh, 'system_message',
                                     get_default_system_message(detected_language))
        response_size = kwargs.get("response_size", "medium")
        system_message = get_system_message_for_language(detected_language, base_system_message, response_size)

        # Check if we need to perform Azure Search
        search_context = ""
        citations = []

        if app_settings.datasource and enhanced_messages:
            # Extract user query for search
            user_query = self._extract_user_query(enhanced_messages, detected_language)
            if user_query:
                self.logger.debug(f"Performing Azure Search for query: '{user_query}'")

                # Perform search using the shared search service
                search_results = await self.search_service.search_documents(
                    query=user_query,
                    top_k=kwargs.get("documents_count"),
                    filters=kwargs.get("search_filters"),
                    user_permissions=kwargs.get("user_permissions")
                )

                self.logger.debug(f"Azure Search returned {len(search_results) if search_results else 0} results")

                if search_results:
                    # Build context and citations
                    search_context, citations = build_search_context(
                        search_results,
                        app_settings.base_settings.citation_content_max_length
                    )

                    # Store search context for token counting
                    self._current_search_context = search_context
                    self._current_search_citations = citations

        # Build enhanced system message with localization
        if search_context:
            # Get localized documents header
            documents_header = get_documents_header(detected_language)

            enhanced_system_message = f"""{system_message}

{documents_header}
{search_context}"""
        else:
            enhanced_system_message = system_message

        # Insert system message at the beginning
        enhanced_messages.insert(0, {
            "role": "system",
            "content": enhanced_system_message
        })

        return enhanced_messages

    def _extract_user_query(self, messages: List[Dict[str, Any]], detected_language: str = 'fr') -> Optional[str]:
        """Extract the user's query from messages for search, handling multimodal content."""
        # Get the last user message as the search query
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")

                # Handle multimodal content (text + images)
                if isinstance(content, list):
                    text_parts = []
                    has_image = False

                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                            elif part.get("type") == "image_url":
                                has_image = True

                    base_query = " ".join(text_parts)

                    # Enrich query with image context if needed
                    if has_image and base_query:
                        # Check if this is a help/procedure question
                        is_help_question = any(word in base_query.lower() for word in
                                              ["que faire", "comment", "procédure", "aide", "urgence", "help", "how"])

                        if is_help_question:
                            emergency_keywords = get_emergency_keywords(detected_language)
                            return f"{base_query} {emergency_keywords}"

                    return base_query

                return content
        return None

    def _inject_citations_in_stream(self, stream_response):
        """
        Inject citations into OVH streaming response.

        This creates a wrapper around the OVH stream that first yields
        a citation chunk, then yields the actual content chunks.
        Compatible with the existing format_stream_response function.
        """
        import time

        async def citation_aware_stream():
            first_chunk = True
            async for chunk in stream_response:
                # Before the first content chunk, inject citations
                if first_chunk and hasattr(self, '_current_search_citations') and self._current_search_citations:
                    # Create a citation chunk similar to other providers
                    citation_chunk = {
                        'id': f'ovh-citations-{int(time.time())}',
                        'object': 'chat.completion.chunk',
                        'created': int(time.time()),
                        'model': self.current_model,
                        'choices': [{
                            'index': 0,
                            'delta': {
                                'role': 'assistant',
                                'context': {
                                    'citations': self._current_search_citations,
                                    'intent': 'Azure Search results'
                                }
                            },
                            'finish_reason': None
                        }]
                    }

                    # Create a proper mock response object
                    class MockCitationResponse:
                        def __init__(self, chunk_data):
                            self.id = chunk_data['id']
                            self.object = chunk_data['object']
                            self.created = chunk_data['created']
                            self.model = chunk_data['model']
                            self.choices = [MockChoice(chunk_data['choices'][0])]

                    class MockChoice:
                        def __init__(self, choice_data):
                            self.index = choice_data['index']
                            self.finish_reason = choice_data['finish_reason']
                            self.delta = MockDelta(choice_data['delta'])

                    class MockDelta:
                        def __init__(self, delta_data):
                            self.role = delta_data['role']
                            self.context = delta_data['context']

                    citation_response = MockCitationResponse(citation_chunk)
                    yield citation_response
                    first_chunk = False

                # Yield the actual content chunk
                yield chunk

        return citation_aware_stream()

    def format_response(
        self,
        raw_response: Any,
        stream: bool = True
    ) -> Union[StandardResponseAdapter, Any]:
        """
        Format OVH response to standard format.

        Since OVH uses OpenAI-compatible responses, minimal transformation is needed.
        We primarily handle reasoning content display and ensure compatibility.

        Args:
            raw_response: Tuple of (response, request_id) from send_request()
            stream: Whether this is a streaming response

        Returns:
            For streaming: The response object (already compatible)
            For non-streaming: StandardResponseAdapter wrapping the response
        """
        response, request_id = raw_response

        if stream:
            # For streaming responses, OVH format is OpenAI-compatible
            self.logger.debug("Returning OVH streaming response (OpenAI-compatible)")
            return response
        else:
            # For non-streaming responses, convert to our standard format
            self.logger.debug("Converting OVH non-streaming response to standard format")

            # Handle reasoning content for reasoning models
            if hasattr(response, 'choices') and response.choices:
                choice = response.choices[0]
                if hasattr(choice, 'message') and hasattr(choice.message, 'reasoning_content'):
                    reasoning_content = choice.message.reasoning_content
                    if reasoning_content and app_settings.ovh.show_reasoning_in_ui:
                        # Add reasoning to context for UI display
                        if not hasattr(choice.message, 'context'):
                            choice.message.context = {}
                        choice.message.context['reasoning_content'] = reasoning_content
                        choice.message.context['show_reasoning'] = True
                        self.logger.debug("Added reasoning content to response context")

            # Convert to standard format
            standard_response = self._convert_ovh_response(response)
            return StandardResponseAdapter(standard_response)

    def _convert_ovh_response(self, ovh_response) -> StandardResponse:
        """
        Convert OVH response to StandardResponse format.

        Args:
            ovh_response: Raw OVH response object (OpenAI-compatible)

        Returns:
            StandardResponse object
        """
        # Convert choices
        choices = []
        for choice in ovh_response.choices:
            # Convert message
            message = None
            if hasattr(choice, 'message') and choice.message:
                message = StandardMessage(
                    role=choice.message.role,
                    content=choice.message.content,
                    tool_calls=getattr(choice.message, 'tool_calls', None),
                    context=getattr(choice.message, 'context', None),
                    function_call=getattr(choice.message, 'function_call', None)
                )

            # Convert delta (for streaming compatibility)
            delta = None
            if hasattr(choice, 'delta') and choice.delta:
                delta = StandardMessage(
                    role=getattr(choice.delta, 'role', None),
                    content=getattr(choice.delta, 'content', None),
                    tool_calls=getattr(choice.delta, 'tool_calls', None),
                    context=getattr(choice.delta, 'context', None),
                    function_call=getattr(choice.delta, 'function_call', None)
                )

            standard_choice = StandardChoice(
                index=choice.index,
                message=message,
                delta=delta,
                finish_reason=choice.finish_reason
            )
            choices.append(standard_choice)

        # Convert usage if available
        usage = None
        if hasattr(ovh_response, 'usage') and ovh_response.usage:
            usage = StandardUsage(
                prompt_tokens=ovh_response.usage.prompt_tokens,
                completion_tokens=ovh_response.usage.completion_tokens,
                total_tokens=ovh_response.usage.total_tokens
            )

        return StandardResponse(
            id=ovh_response.id,
            object=ovh_response.object,
            created=ovh_response.created,
            model=ovh_response.model,
            choices=choices,
            usage=usage
        )

    def get_current_model(self) -> str:
        """Get the currently selected model."""
        return self.current_model

    def get_available_models(self) -> List[str]:
        """Get the list of available models."""
        return self.available_models.copy()

    def get_model_capabilities(self, model_name: str) -> Dict[str, Any]:
        """Get the capabilities of a specific model."""
        return self.model_capabilities.get(model_name, {}).copy()

    def switch_model(self, new_model: str) -> bool:
        """
        Switch to a different model.

        Args:
            new_model: Name of the new model to use

        Returns:
            True if switch was successful, False otherwise
        """
        if new_model not in self.available_models:
            self.logger.warning(f"Model '{new_model}' not available. Available: {self.available_models}")
            return False

        old_model = self.current_model
        self.current_model = new_model
        self.logger.info(f"Switched model from '{old_model}' to '{new_model}'")
        return True

    async def close(self):
        """Close the OVH client and clean up resources."""
        await super().close()
        if self.client:
            # OpenAI client cleanup
            await self.client.close()
            self.client = None
            self.logger.debug("OVH AI Endpoints client cleaned up")

        # Close search service
        if self.search_service:
            await self.search_service.close()

        # Clean up model state
        self.available_models = []
        self.model_capabilities = {}
        self.current_model = None