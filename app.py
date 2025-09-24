import copy
import json
import os
import logging
import uuid
import httpx
import asyncio

import requests

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
import base64
from datetime import datetime
from hashlib import sha256

from requests.adapters import HTTPAdapter, Retry

from quart import (
    Blueprint,
    Quart,
    jsonify,
    make_response,
    request,
    send_from_directory,
    render_template,
    current_app,
)

from openai import AsyncAzureOpenAI
from azure.identity.aio import (
    DefaultAzureCredential,
    get_bearer_token_provider
)
from backend.auth.auth_utils import get_authenticated_user_details
from backend.security.ms_defender_utils import get_msdefender_user_json
from backend.history.cosmosdbservice import CosmosConversationClient
from backend.settings import (
    app_settings,
    MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION
)
from backend.utils import (
    format_as_ndjson,
    format_stream_response,
    format_non_streaming_response,
    convert_to_pf_format,
    format_pf_non_streaming_response,
)
from backend.document_processor import DocumentProcessor
from backend.llm_providers import LLMProviderFactory
from backend.speech_services import synthesize_speech_azure, clean_text_for_speech
from backend.pronunciation_dict import get_pronunciation_dict, add_pronunciation, remove_pronunciation
from backend.chat_commands import command_parser, ChatCommandExecutor
from backend.version import get_version_info, get_display_version
from backend.usage_service import init_usage_service, get_usage_service

# Global variable to store current provider instance for token counting
_current_provider_instance = None

bp = Blueprint("routes", __name__, static_folder="static", template_folder="static")

cosmos_db_ready = asyncio.Event()

# Dictionnaire global pour stocker les sessions utilisateur
user_sessions = {}


def create_app():
    app = Quart(__name__)
    app.register_blueprint(bp)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    
    @app.before_serving
    async def init():
        try:
            app.cosmos_conversation_client = await init_cosmosdb_client()

            # Initialize usage tracking service with same CosmosDB client
            if app.cosmos_conversation_client and hasattr(app.cosmos_conversation_client, 'cosmosdb_client'):
                init_usage_service(app.cosmos_conversation_client.cosmosdb_client)
                logging.info("Usage tracking service initialized with CosmosDB client")
            else:
                init_usage_service(None)
                logging.warning("Usage tracking service initialized without CosmosDB client")

            cosmos_db_ready.set()
        except Exception as e:
            logging.exception("Failed to initialize CosmosDB client")
            app.cosmos_conversation_client = None

            # Still try to initialize usage service even if CosmosDB fails
            init_usage_service(None)

            raise e
    
    return app


@bp.route("/")
async def index():
    response = await make_response(await render_template(
        "index.html",
        title=app_settings.ui.title,
        favicon=app_settings.ui.favicon
    ))
    # Allow microphone access in iframe
    response.headers['Permissions-Policy'] = 'microphone=*'
    return response


@bp.route("/favicon.ico")
async def favicon():
    return await bp.send_static_file("favicon.ico")


@bp.route("/assets/<path:path>")
async def assets(path):
    return await send_from_directory("static/assets", path)


# Debug settings
DEBUG = os.environ.get("DEBUG", "false")
if DEBUG.lower() == "true":
    logging.basicConfig(level=logging.DEBUG)
else:
    # Configure logging to show INFO level for debugging but suppress Azure SDK noise
    logging.basicConfig(level=logging.DEBUG)
    
    # Set specific loggers to appropriate levels
    logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)
    logging.getLogger('azure').setLevel(logging.DEBUG)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

USER_AGENT = "GitHubSampleWebApp/AsyncAzureOpenAI/1.0.0"


# Frontend Settings via Environment Variables
frontend_settings = {
    "auth_enabled": app_settings.base_settings.auth_enabled,
    "feedback_enabled": (
        app_settings.chat_history and
        app_settings.chat_history.enable_feedback
    ),
    "version": get_display_version(),
    "ui": {
        "title": app_settings.ui.title,
        "logo": app_settings.ui.logo,
        "chat_logo": app_settings.ui.chat_logo or app_settings.ui.logo,
        "chat_title": app_settings.ui.chat_title,
        "chat_description": app_settings.ui.chat_description,
        "show_share_button": app_settings.ui.show_share_button,
        "show_chat_history_button": app_settings.ui.show_chat_history_button,
        "show_export_button": app_settings.ui.show_export_button,
    },
    "sanitize_answer": app_settings.base_settings.sanitize_answer,
    "oyd_enabled": app_settings.base_settings.datasource_type,
    "available_llm_providers": app_settings.base_settings.available_llm_providers,
    "default_llm_provider": app_settings.base_settings.llm_provider,
    "voice_input_enabled": app_settings.base_settings.voice_input_enabled,
    "wake_word_enabled": app_settings.base_settings.wake_word_enabled,
    "wake_word_phrases": app_settings.base_settings.wake_word_phrases,
    "wake_word_variants": app_settings.base_settings.get_wake_word_variants_map(),
    "azure_speech_enabled": app_settings.base_settings.azure_speech_enabled,
    "azure_speech_voice_fr": app_settings.base_settings.azure_speech_voice_fr,
    "azure_speech_voice_en": app_settings.base_settings.azure_speech_voice_en,
    "image_max_size_mb": app_settings.base_settings.image_max_size_mb,
}


# Enable Microsoft Defender for Cloud Integration
MS_DEFENDER_ENABLED = os.environ.get("MS_DEFENDER_ENABLED", "true").lower() == "true"

azure_openai_tools = []
azure_openai_available_tools = []
 
# Initialize Azure OpenAI Client
async def init_openai_client():
    azure_openai_client = None
      
    try:
        # API version check
        if (
            app_settings.azure_openai.preview_api_version
            < MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION
        ):
            raise ValueError(
                f"The minimum supported Azure OpenAI preview API version is '{MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION}'"
            )

        # Endpoint
        if (
            not app_settings.azure_openai.endpoint and
            not app_settings.azure_openai.resource
        ):
            raise ValueError(
                "AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_RESOURCE is required"
            )

        endpoint = (
            app_settings.azure_openai.endpoint
            if app_settings.azure_openai.endpoint
            else f"https://{app_settings.azure_openai.resource}.openai.azure.com/"
        )

        # Authentication
        aoai_api_key = app_settings.azure_openai.key
        ad_token_provider = None
        if not aoai_api_key:
            logging.debug("No AZURE_OPENAI_KEY found, using Azure Entra ID auth")
            async with DefaultAzureCredential() as credential:
                ad_token_provider = get_bearer_token_provider(
                    credential,
                    "https://cognitiveservices.azure.com/.default"
                )

        # Deployment
        deployment = app_settings.azure_openai.model
        if not deployment:
            raise ValueError("AZURE_OPENAI_MODEL is required")

        # Default Headers
        default_headers = {"x-ms-useragent": USER_AGENT}

        # Remote function calls
        if app_settings.azure_openai.function_call_azure_functions_enabled:
            azure_functions_tools_url = f"{app_settings.azure_openai.function_call_azure_functions_tools_base_url}?code={app_settings.azure_openai.function_call_azure_functions_tools_key}"
            async with httpx.AsyncClient() as client:
                response = await client.get(azure_functions_tools_url)
            response_status_code = response.status_code
            if response_status_code == httpx.codes.OK:
                azure_openai_tools.extend(json.loads(response.text))
                for tool in azure_openai_tools:
                    azure_openai_available_tools.append(tool["function"]["name"])
            else:
                logging.error(f"An error occurred while getting OpenAI Function Call tools metadata: {response.status_code}")

        
        azure_openai_client = AsyncAzureOpenAI(
            api_version=app_settings.azure_openai.preview_api_version,
            api_key=aoai_api_key,
            azure_ad_token_provider=ad_token_provider,
            default_headers=default_headers,
            azure_endpoint=endpoint,
        )

        return azure_openai_client
    except Exception as e:
        logging.exception("Exception in Azure OpenAI initialization", e)
        azure_openai_client = None
        raise e

async def openai_remote_azure_function_call(function_name, function_args):
    if app_settings.azure_openai.function_call_azure_functions_enabled is not True:
        return

    azure_functions_tool_url = f"{app_settings.azure_openai.function_call_azure_functions_tool_base_url}?code={app_settings.azure_openai.function_call_azure_functions_tool_key}"
    headers = {'content-type': 'application/json'}
    body = {
        "tool_name": function_name,
        "tool_arguments": json.loads(function_args)
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(azure_functions_tool_url, data=json.dumps(body), headers=headers)
    response.raise_for_status()

    return response.text

async def init_cosmosdb_client():
    cosmos_conversation_client = None
    if app_settings.chat_history:
        try:
            cosmos_endpoint = (
                f"https://{app_settings.chat_history.account}.documents.azure.com:443/"
            )

            if not app_settings.chat_history.account_key:
                # Utiliser la clé CosmosDB depuis le secret global askme-local-tokens
                cosmos_db_key = os.getenv('AZURE_COSMOSDB_ACCOUNT_KEY')
                if cosmos_db_key:
                    logging.debug("Using CosmosDB key from global secret askme-local-tokens (AZURE_COSMOSDB_ACCOUNT_KEY)")
                    credential = cosmos_db_key
                else:
                    logging.warning("No AZURE_COSMOSDB_ACCOUNT_KEY found in global secret, falling back to Azure AD")
                    async with DefaultAzureCredential() as cred:
                        credential = cred
            else:
                credential = app_settings.chat_history.account_key

            cosmos_conversation_client = CosmosConversationClient(
                cosmosdb_endpoint=cosmos_endpoint,
                credential=credential,
                database_name=app_settings.chat_history.database,
                container_name=app_settings.chat_history.conversations_container,
                enable_message_feedback=app_settings.chat_history.enable_feedback,
            )
        except Exception as e:
            logging.exception("Exception in CosmosDB initialization", e)
            cosmos_conversation_client = None
            raise e
    else:
        logging.debug("CosmosDB not configured")

    return cosmos_conversation_client


async def record_token_usage(
    response,
    user_id: str,
    conversation_id: str,
    message_id: str,
    provider_type: str
):
    """
    Record token usage from LLM response.

    Args:
        response: LLM response containing usage information
        user_id: User identifier
        conversation_id: Conversation identifier
        message_id: Message identifier
        provider_type: LLM provider type
    """
    try:
        usage_service = get_usage_service()
        logging.info(f"[USAGE_TRACKING] record_token_usage called for user {user_id[:8] if user_id else 'None'}...")
        logging.info(f"[USAGE_DEBUG] Provider: {provider_type}, Service enabled: {usage_service.enabled if usage_service else 'None'}")

        if not usage_service:
            logging.warning("[USAGE_TRACKING] Usage service not initialized")
            return

        if not usage_service.enabled:
            logging.info("[USAGE_TRACKING] Usage tracking disabled")
            return

        # Extract usage information from response
        usage_data = None

        if hasattr(response, 'usage') and response.usage:
            usage = response.usage

            # Get input tokens detail if available
            input_tokens = {}
            if hasattr(usage, 'input_tokens_detail') and usage.input_tokens_detail:
                input_tokens = usage.input_tokens_detail
            else:
                # Fallback to basic token counts
                input_tokens = {
                    "total": getattr(usage, 'prompt_tokens', 0),
                    "text": getattr(usage, 'prompt_tokens', 0),
                    "images": 0,
                    "search_context": 0
                }

            output_tokens = getattr(usage, 'completion_tokens', 0)

            # Get usage metadata if available
            metadata = {}
            if hasattr(usage, 'usage_metadata') and usage.usage_metadata:
                metadata = usage.usage_metadata

            # Record usage asynchronously (don't await to avoid blocking)
            logging.info(f"[USAGE_DEBUG] About to call record_usage with: input={input_tokens.get('total', 0)}, output={output_tokens}")

            asyncio.create_task(usage_service.record_usage(
                user_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                provider=provider_type,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                metadata=metadata
            ))

            logging.debug(f"Usage tracking recorded: {input_tokens.get('total', 0)} input + {output_tokens} output = {input_tokens.get('total', 0) + output_tokens} total tokens")

    except Exception as e:
        logging.warning(f"Failed to record token usage: {e}")


async def promptflow_request(request):
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {app_settings.promptflow.api_key}",
        }
        # Adding timeout for scenarios where response takes longer to come back
        logging.debug(f"Setting timeout to {app_settings.promptflow.response_timeout}")
        async with httpx.AsyncClient(
            timeout=float(app_settings.promptflow.response_timeout)
        ) as client:
            pf_formatted_obj = convert_to_pf_format(
                request,
                app_settings.promptflow.request_field_name,
                app_settings.promptflow.response_field_name
            )
            # NOTE: This only support question and chat_history parameters
            # If you need to add more parameters, you need to modify the request body
            response = await client.post(
                app_settings.promptflow.endpoint,
                json={
                    app_settings.promptflow.request_field_name: pf_formatted_obj[-1]["inputs"][app_settings.promptflow.request_field_name],
                    "chat_history": pf_formatted_obj[:-1],
                },
                headers=headers,
            )
        resp = response.json()
        resp["id"] = request["messages"][-1]["id"]
        return resp
    except Exception as e:
        logging.error(f"An error occurred while making promptflow_request: {e}")


async def process_function_call(response):
    response_message = response.choices[0].message
    messages = []

    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            # Check if function exists
            if tool_call.function.name not in azure_openai_available_tools:
                continue
            
            function_response = await openai_remote_azure_function_call(tool_call.function.name, tool_call.function.arguments)

            # adding assistant response to messages
            messages.append(
                {
                    "role": response_message.role,
                    "function_call": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                    "content": None,
                }
            )
            
            # adding function response to messages
            messages.append(
                {
                    "role": "function",
                    "name": tool_call.function.name,
                    "content": function_response,
                }
            )  # extend conversation with function response
        
        return messages
    
    return None

async def send_chat_request(request_body, request_headers, shouldStream = True):
    filtered_messages = []
    messages = request_body.get("messages", [])
    
    # DEBUG: Log incoming messages to see if images are present
    logging.info(f"DEBUG: Received {len(messages)} messages in send_chat_request")
    for i, msg in enumerate(messages):
        logging.info(f"DEBUG: Message {i} - role: {msg.get('role')}, content type: {type(msg.get('content'))}")
        if isinstance(msg.get('content'), list):
            for j, part in enumerate(msg['content']):
                logging.info(f"DEBUG: Message {i}, part {j} - type: {part.get('type')}")
                if part.get('type') == 'image_url':
                    image_url = part.get('image_url', {}).get('url', '')
                    logging.info(f"DEBUG: Found image_url in send_chat_request, length: {len(image_url)}, preview: {image_url[:50]}...")
    
    for message in messages:
        if message.get("role") != 'tool':
            filtered_messages.append(message)
            
    request_body['messages'] = filtered_messages
    
    # Get provider from request or customizationPreferences, fallback to default
    provider_type = request_body.get("provider")
    logging.info(f"DEBUG PROVIDER: Direct provider from request: {provider_type}")
    
    # If provider not directly specified, check customizationPreferences
    if not provider_type:
        customization_preferences = request_body.get("customizationPreferences", {})
        provider_type = customization_preferences.get("llmProvider")
        logging.info(f"DEBUG PROVIDER: Provider from customizationPreferences: {provider_type}")
        logging.info(f"DEBUG PROVIDER: Full customizationPreferences: {customization_preferences}")
    
    # Fallback to default if still not found
    if not provider_type:
        provider_type = LLMProviderFactory.get_default_provider()
        logging.info(f"DEBUG PROVIDER: Using default provider: {provider_type}")
    
    print(f"[LLM] LLM Provider utilisé: {provider_type}")
    logging.info(f"[LLM] LLM Provider utilisé: {provider_type}")
    logging.debug(f"send_chat_request: Using provider = {provider_type}")
    
    # Use the unified LLM provider abstraction for ALL providers
    try:
        logging.info(f"DEBUG APP: About to create provider: {provider_type}")
        provider = LLMProviderFactory.create_provider(provider_type)
        # Store the provider instance in a temporary global for token counting
        global _current_provider_instance
        _current_provider_instance = provider

        logging.info(f"DEBUG APP: Created provider instance: {provider.__class__.__name__}")
        logging.info(f"DEBUG APP: Provider module: {provider.__class__.__module__}")
        
        # Extract messages for all providers (they handle their own model args)
        request_messages = request_body.get("messages", [])
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in request_messages]
        
        # Send request to provider
        logging.debug(f"Sending request to {provider_type} with shouldStream={shouldStream}")
        
        # Extract customization preferences
        customization_preferences = request_body.get("customizationPreferences", {})
        documents_count = customization_preferences.get("documentsCount")
        response_size = customization_preferences.get("responseSize", "medium")
        
        print(f"[PARAMS] Paramètres de personnalisation:")
        print(f"   - Nombre de documents: {documents_count}")
        print(f"   - Taille de réponse: {response_size}")
        
        # Extract search filters and user permissions properly
        user_full_definition = request_body.get("userFullDefinition", "*")
        search_filters = None
        user_permissions = None
        
        if user_full_definition and user_full_definition != "*":
            # For Claude, we need to pass this as user permissions for rights management
            user_permissions = user_full_definition
            logging.debug(f"Setting user_permissions for {provider_type}: {user_permissions}")
        
        response, apim_request_id = await provider.send_request(
            messages=messages,
            stream=shouldStream,
            documents_count=documents_count,
            response_size=response_size,
            search_filters=search_filters,
            user_permissions=user_permissions
        )
        
        logging.debug(f"Response from {provider_type}: {type(response)} - {str(response)[:200]}...")
        
        return response, apim_request_id
    except Exception as e:
        from backend.llm_providers.errors import LLMProviderErrorHandler
        
        logging.exception(f"Exception in send_chat_request with provider {provider_type}")
        
        # Create user-friendly error and re-raise with enhanced message
        user_message, status_code = LLMProviderErrorHandler.handle_provider_error(
            exception=e,
            provider_name=provider_type,
            language="fr"  # Default to French for AskMe
        )
        
        # Create a new exception with user-friendly message but preserve original for debugging
        enhanced_error = Exception(user_message)
        enhanced_error.status_code = status_code
        enhanced_error.original_error = e
        raise enhanced_error


async def complete_chat_request(request_body, request_headers, user_id, provider_type):
    if app_settings.base_settings.use_promptflow:
        response = await promptflow_request(request_body)
        history_metadata = request_body.get("history_metadata", {})
        return format_pf_non_streaming_response(
            response,
            history_metadata,
            app_settings.promptflow.response_field_name,
            app_settings.promptflow.citations_field_name
        )
    else:
        logging.debug("Calling send_chat_request with shouldStream=False")
        response, apim_request_id = await send_chat_request(request_body, request_headers, False)
        logging.debug(f"send_chat_request response type: {type(response)}, apim_request_id: {apim_request_id}")
        history_metadata = request_body.get("history_metadata", {})

        # Record token usage for non-streaming response
        logging.info(f"[USAGE_TRACKING] About to record usage for {provider_type}")
        await record_token_usage(
            response=response,
            user_id=user_id or "anonymous",
            conversation_id=history_metadata.get("conversation_id", "unknown"),
            message_id=str(uuid.uuid4()),  # Generate unique message ID
            provider_type=provider_type
        )

        non_streaming_response = format_non_streaming_response(response, history_metadata, apim_request_id)
        logging.debug(f"non_streaming_response: {type(non_streaming_response)} - {str(non_streaming_response)[:200]}...")

        if app_settings.azure_openai.function_call_azure_functions_enabled:
            function_response = await process_function_call(response)  # Add await here

            if function_response:
                request_body["messages"].extend(function_response)

                response, apim_request_id = await send_chat_request(request_body, request_headers)
                history_metadata = request_body.get("history_metadata", {})
                non_streaming_response = format_non_streaming_response(response, history_metadata, apim_request_id)

    return non_streaming_response

class AzureOpenaiFunctionCallStreamState():
    def __init__(self):
        self.tool_calls = []                # All tool calls detected in the stream
        self.tool_name = ""                 # Tool name being streamed
        self.tool_arguments_stream = ""     # Tool arguments being streamed
        self.current_tool_call = None       # JSON with the tool name and arguments currently being streamed
        self.function_messages = []         # All function messages to be appended to the chat history
        self.streaming_state = "INITIAL"    # Streaming state (INITIAL, STREAMING, COMPLETED)


async def process_function_call_stream(completionChunk, function_call_stream_state, request_body, request_headers, history_metadata, apim_request_id):
    if hasattr(completionChunk, "choices") and len(completionChunk.choices) > 0:
        response_message = completionChunk.choices[0].delta
        
        # Function calling stream processing
        if response_message.tool_calls and function_call_stream_state.streaming_state in ["INITIAL", "STREAMING"]:
            function_call_stream_state.streaming_state = "STREAMING"
            for tool_call_chunk in response_message.tool_calls:
                # New tool call
                if tool_call_chunk.id:
                    if function_call_stream_state.current_tool_call:
                        function_call_stream_state.tool_arguments_stream += tool_call_chunk.function.arguments if tool_call_chunk.function.arguments else ""
                        function_call_stream_state.current_tool_call["tool_arguments"] = function_call_stream_state.tool_arguments_stream
                        function_call_stream_state.tool_arguments_stream = ""
                        function_call_stream_state.tool_name = ""
                        function_call_stream_state.tool_calls.append(function_call_stream_state.current_tool_call)

                    function_call_stream_state.current_tool_call = {
                        "tool_id": tool_call_chunk.id,
                        "tool_name": tool_call_chunk.function.name if function_call_stream_state.tool_name == "" else function_call_stream_state.tool_name
                    }
                else:
                    function_call_stream_state.tool_arguments_stream += tool_call_chunk.function.arguments if tool_call_chunk.function.arguments else ""
                
        # Function call - Streaming completed
        elif response_message.tool_calls is None and function_call_stream_state.streaming_state == "STREAMING":
            function_call_stream_state.current_tool_call["tool_arguments"] = function_call_stream_state.tool_arguments_stream
            function_call_stream_state.tool_calls.append(function_call_stream_state.current_tool_call)
            
            for tool_call in function_call_stream_state.tool_calls:
                tool_response = await openai_remote_azure_function_call(tool_call["tool_name"], tool_call["tool_arguments"])

                function_call_stream_state.function_messages.append({
                    "role": "assistant",
                    "function_call": {
                        "name" : tool_call["tool_name"],
                        "arguments": tool_call["tool_arguments"]
                    },
                    "content": None
                })
                function_call_stream_state.function_messages.append({
                    "tool_call_id": tool_call["tool_id"],
                    "role": "function",
                    "name": tool_call["tool_name"],
                    "content": tool_response,
                })
            
            function_call_stream_state.streaming_state = "COMPLETED"
            return function_call_stream_state.streaming_state
        
        else:
            return function_call_stream_state.streaming_state


async def stream_chat_request(request_body, request_headers):
    # Get provider from request or customizationPreferences, fallback to default
    provider_type = request_body.get("provider")
    
    # If provider not directly specified, check customizationPreferences
    if not provider_type:
        customization_preferences = request_body.get("customizationPreferences", {})
        provider_type = customization_preferences.get("llmProvider")
    
    # Fallback to default if still not found
    if not provider_type:
        provider_type = LLMProviderFactory.get_default_provider()
    
    logging.debug(f"stream_chat_request: Using provider = {provider_type}")
    
    # Enable streaming for both providers
    shouldStream = True
    
    response, apim_request_id = await send_chat_request(request_body, request_headers, shouldStream)
    history_metadata = request_body.get("history_metadata", {})
    
    async def generate(apim_request_id, history_metadata, provider_type):
        # Variables to capture usage information for token tracking
        final_usage_response = None

        # Variable to collect complete response text for real token counting
        complete_response_text = ""

        # DEBUG: Log pour tracer l'usage tracking
        logging.info(f"[USAGE_DEBUG] generate() called with provider_type={provider_type}")

        # Azure OpenAI specific function calling logic
        if provider_type == "AZURE_OPENAI" and app_settings.azure_openai.function_call_azure_functions_enabled:
            # Maintain state during function call streaming
            function_call_stream_state = AzureOpenaiFunctionCallStreamState()

            async for completionChunk in response:
                stream_state = await process_function_call_stream(completionChunk, function_call_stream_state, request_body, request_headers, history_metadata, apim_request_id)

                # No function call, asistant response
                if stream_state == "INITIAL":
                    # Collect response text for real token counting
                    if hasattr(completionChunk, 'choices') and completionChunk.choices:
                        delta = completionChunk.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            complete_response_text += delta.content

                    yield format_stream_response(completionChunk, history_metadata, apim_request_id, provider_type)
                    # Capture usage information from each chunk
                    if hasattr(completionChunk, 'usage') and completionChunk.usage:
                        final_usage_response = completionChunk

                # Function call stream completed, functions were executed.
                # Append function calls and results to history and send to OpenAI, to stream the final answer.
                if stream_state == "COMPLETED":
                    request_body["messages"].extend(function_call_stream_state.function_messages)
                    function_response, apim_request_id = await send_chat_request(request_body, request_headers)
                    async for functionCompletionChunk in function_response:
                        # Collect response text from function calls too
                        if hasattr(functionCompletionChunk, 'choices') and functionCompletionChunk.choices:
                            delta = functionCompletionChunk.choices[0].delta
                            if hasattr(delta, 'content') and delta.content:
                                complete_response_text += delta.content

                        yield format_stream_response(functionCompletionChunk, history_metadata, apim_request_id, provider_type)
                        # Capture usage from function response
                        if hasattr(functionCompletionChunk, 'usage') and functionCompletionChunk.usage:
                            final_usage_response = functionCompletionChunk

        else:
            # For Claude and non-function Azure OpenAI requests
            if hasattr(response, '__aiter__'):
                # Response is already an async generator (streaming)
                async for completionChunk in response:
                    # Collect response text for real token counting (Claude, Mistral, etc.)
                    if hasattr(completionChunk, 'choices') and completionChunk.choices:
                        delta = completionChunk.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            complete_response_text += delta.content
                    # For providers that put content directly in the chunk
                    elif hasattr(completionChunk, 'content') and completionChunk.content:
                        complete_response_text += completionChunk.content

                    yield format_stream_response(completionChunk, history_metadata, apim_request_id, provider_type)
                    # Capture usage information from each chunk
                    if hasattr(completionChunk, 'usage') and completionChunk.usage:
                        final_usage_response = completionChunk
            elif isinstance(response, dict):
                # Response is a single completion object (non-streaming) - but this shouldn't happen for Claude
                logging.warning(f"Received dict response in stream_chat_request: {type(response)}")
                # Extract content for non-streaming response
                if response.get('choices') and response['choices'][0].get('message', {}).get('content'):
                    complete_response_text += response['choices'][0]['message']['content']
                yield format_stream_response(response, history_metadata, apim_request_id, provider_type)
                final_usage_response = response
            elif hasattr(response, 'id'):
                # Response is a single completion object (MockAzureOpenAIResponse for Claude)
                # Extract content from single response
                if hasattr(response, 'choices') and response.choices and hasattr(response.choices[0], 'message'):
                    message = response.choices[0].message
                    if hasattr(message, 'content') and message.content:
                        complete_response_text += message.content
                elif hasattr(response, 'content') and response.content:
                    complete_response_text += response.content

                formatted_response = format_stream_response(response, history_metadata, apim_request_id, provider_type)
                yield formatted_response
                final_usage_response = response
            else:
                # Response is a regular iterable (fallback)
                for completionChunk in response:
                    # Collect text from regular iterable too
                    if hasattr(completionChunk, 'choices') and completionChunk.choices:
                        delta = completionChunk.choices[0].delta
                        if hasattr(delta, 'content') and delta.content:
                            complete_response_text += delta.content
                    elif hasattr(completionChunk, 'content') and completionChunk.content:
                        complete_response_text += completionChunk.content

                    yield format_stream_response(completionChunk, history_metadata, apim_request_id, provider_type)
                    if hasattr(completionChunk, 'usage') and completionChunk.usage:
                        final_usage_response = completionChunk

        # Record token usage after streaming is complete
        logging.info(f"[USAGE_DEBUG] Streaming finished. final_usage_response = {final_usage_response is not None}")

        # ALWAYS estimate tokens for all LLM providers (fallback if no usage, or supplement existing usage)
        estimated_usage_response = None
        try:
            from backend.token_counter import token_counter
            logging.info("[USAGE_DEBUG] Estimating tokens for ALL LLM providers")

            # Estimate input tokens from original request
            messages = request_body.get("messages", [])

            # Get search context for token counting
            # For Azure OpenAI: uses native "On Your Data" (search_context in request_body)
            # For other providers: search context is built by the provider and stored internally

            search_context = ""
            logging.debug(f"[TOKEN_COUNT_FLOW] About to check provider_type: '{provider_type}'")
            if provider_type == "AZURE_OPENAI":
                logging.debug(f"[TOKEN_COUNT_FLOW] AZURE_OPENAI condition matched!")
                # Azure OpenAI uses native "On Your Data" integration
                # IMPORTANT: request_body doesn't contain search_context, so we simulate the search
                # to get accurate token counting without interfering with Azure OpenAI's native behavior
                logging.info(f"[TOKEN_COUNT] Azure OpenAI detected - starting search simulation")
                try:
                    logging.info(f"[TOKEN_COUNT] Azure OpenAI: Performing parallel search for token counting")

                    # Import Azure Search service to simulate the search
                    from backend.llm_providers.utils import AzureSearchService, build_search_context
                    logging.debug(f"[TOKEN_COUNT] Azure OpenAI: Imports successful")

                    # Get the user query from messages
                    user_query = ""
                    for msg in list(reversed(messages)):
                        if msg.get("role") == "user":
                            content = msg.get("content", "")
                            if isinstance(content, str):
                                user_query = content
                                break
                            elif isinstance(content, list):
                                # Handle multimodal content
                                text_parts = []
                                for part in content:
                                    if isinstance(part, dict) and part.get("type") == "text":
                                        text_parts.append(part.get("text", ""))
                                user_query = " ".join(text_parts)
                                break

                    if user_query:
                        # Create search service and perform search for token counting only
                        search_service = AzureSearchService()
                        search_results = await search_service.search_documents(
                            query=user_query,
                            top_k=request_body.get("documents_count"),
                            filters=request_body.get("search_filters"),
                            user_permissions=request_body.get("user_permissions")
                        )

                        # Build search context for token counting
                        search_context, _ = build_search_context(
                            search_results,
                            app_settings.base_settings.citation_content_max_length
                        )

                        logging.debug(f"[TOKEN_COUNT] Azure OpenAI: Simulated search returned {len(search_context)} chars for token counting")
                    else:
                        logging.warning(f"[TOKEN_COUNT] Azure OpenAI: No user query found for search simulation")
                        search_context = ""

                except Exception as e:
                    logging.warning(f"[TOKEN_COUNT] Azure OpenAI: Failed to simulate search for token counting: {e}")
                    search_context = ""
            else:
                # Other providers store search context in the provider instance
                try:
                    global _current_provider_instance
                    search_context = _current_provider_instance.current_search_context
                    logging.debug(f"[TOKEN_COUNT] Retrieved search_context from {provider_type}: {len(search_context)} chars")
                except Exception as e:
                    logging.warning(f"[TOKEN_COUNT] Could not retrieve search_context from {provider_type}: {e}")
                    search_context = ""

            # Extract system message from processed messages for accurate token counting
            provider_system_message = ""
            logging.debug(f"[TOKEN_COUNT] Provider type: {provider_type}")

            # Try to extract system message from the messages sent to the provider
            try:
                if messages:
                    # Debug: log message structure for non-Azure providers
                    if provider_type != "AZURE_OPENAI":
                        logging.debug(f"[TOKEN_COUNT_DEBUG] {provider_type} messages structure: {len(messages)} messages")
                        for i, msg in enumerate(messages[:3]):  # Show first 3 messages only
                            msg_role = msg.get("role", "no-role")
                            msg_content_len = len(str(msg.get("content", "")))
                            logging.debug(f"[TOKEN_COUNT_DEBUG] Message {i}: role='{msg_role}', content_length={msg_content_len}")

                    # Look for system message in processed messages
                    for msg in messages:
                        if msg.get("role") == "system":
                            provider_system_message = msg.get("content", "")
                            logging.info(f"[TOKEN_COUNT] Found {provider_type} system message: {len(provider_system_message)} characters")
                            break

                    # For Azure OpenAI with datasource, also try to get role_information from last request
                    if provider_type == "AZURE_OPENAI" and not provider_system_message:
                        # Get Azure OpenAI system message from environment as fallback
                        import os
                        system_msg = os.getenv('AZURE_OPENAI_SYSTEM_MESSAGE', '')
                        if system_msg:
                            provider_system_message = system_msg

                    # For Claude, get system message from configuration since Claude handles it differently
                    elif provider_type == "CLAUDE" and not provider_system_message:
                        try:
                            # Claude's system message is configured separately, not in messages array
                            import backend.settings
                            claude_system_msg = backend.settings.app_settings.claude.system_message
                            if claude_system_msg:
                                provider_system_message = claude_system_msg
                                logging.debug(f"[TOKEN_COUNT] Retrieved Claude system message from config: {len(provider_system_message)} chars")
                        except Exception as e:
                            logging.debug(f"[TOKEN_COUNT] Could not retrieve Claude system message from config: {e}")

                    # For other providers, get from their respective configurations
                    elif provider_type in ["MISTRAL", "GEMINI", "OPENAI_DIRECT"] and not provider_system_message:
                        try:
                            import backend.settings
                            if provider_type == "MISTRAL":
                                mistral_system_msg = backend.settings.app_settings.mistral.system_message
                                if mistral_system_msg:
                                    provider_system_message = mistral_system_msg
                            elif provider_type == "GEMINI":
                                gemini_system_msg = backend.settings.app_settings.gemini.system_message
                                if gemini_system_msg:
                                    provider_system_message = gemini_system_msg
                            elif provider_type == "OPENAI_DIRECT":
                                openai_system_msg = backend.settings.app_settings.openai_direct.system_message
                                if openai_system_msg:
                                    provider_system_message = openai_system_msg
                        except Exception as e:
                            logging.debug(f"[TOKEN_COUNT] Could not retrieve {provider_type} system message from config: {e}")

                    if provider_system_message:
                        logging.info(f"[TOKEN_COUNT] Extracted {provider_type} system message: {len(provider_system_message)} characters")
                    else:
                        logging.warning(f"[TOKEN_COUNT] No system message found for {provider_type}")
                else:
                    logging.warning(f"[TOKEN_COUNT] No messages found for {provider_type}")
            except Exception as e:
                logging.error(f"[TOKEN_COUNT] Failed to extract {provider_type} system message: {e}")
                provider_system_message = ""

            # Use a model approximation based on provider
            model_for_counting = "gpt-4"  # Default fallback
            if provider_type == "CLAUDE":
                model_for_counting = "gpt-4"  # Claude tokens similar to GPT-4
            elif provider_type == "MISTRAL":
                model_for_counting = "gpt-3.5-turbo"  # Mistral similar to GPT-3.5

            # Debug: Log what we're passing to the token counter
            logging.debug(f"[TOKEN_COUNT_DEBUG] Calling analyze_input_tokens for {provider_type}:")
            logging.debug(f"[TOKEN_COUNT_DEBUG] - messages: {len(messages)} items")
            logging.debug(f"[TOKEN_COUNT_DEBUG] - search_context: {len(search_context)} chars")
            logging.debug(f"[TOKEN_COUNT_DEBUG] - model_for_counting: {model_for_counting}")
            logging.debug(f"[TOKEN_COUNT_DEBUG] - provider_system_message: {len(provider_system_message)} chars")

            input_token_details = token_counter.analyze_input_tokens(messages, search_context, model_for_counting, provider_system_message)

            # Count actual output tokens from the complete response
            estimated_output_tokens = token_counter.count_text_tokens(
                complete_response_text, model_for_counting
            ) if complete_response_text else 100

            # Create a mock usage object for recording
            class MockUsage:
                def __init__(self, input_tokens, output_tokens, is_estimated=True):
                    self.prompt_tokens = input_tokens.get('total', 0)
                    self.completion_tokens = output_tokens
                    self.total_tokens = self.prompt_tokens + self.completion_tokens
                    self.input_tokens_detail = input_tokens
                    self.usage_metadata = {"estimated": is_estimated, "provider": provider_type.lower()}

            # Output tokens are real if we captured the complete response text
            output_tokens_are_real = bool(complete_response_text)
            estimated_usage_response = type('MockResponse', (), {
                'usage': MockUsage(input_token_details, estimated_output_tokens, not output_tokens_are_real),
                'model': model_for_counting
            })()

            actual_or_estimated = "actual" if complete_response_text else "estimated"
            logging.info(f"[USAGE_DEBUG] Counted tokens ({actual_or_estimated}): input={input_token_details.get('total', 0)}, output={estimated_output_tokens}, provider={provider_type}")

        except Exception as e:
            import traceback
            logging.warning(f"[USAGE_DEBUG] Failed to estimate tokens: {e}")
            logging.debug(f"[USAGE_DEBUG] Full traceback: {traceback.format_exc()}")

        # Use estimated usage if no real usage available, otherwise prefer real usage
        usage_to_record = final_usage_response if final_usage_response else estimated_usage_response

        if usage_to_record:
            try:
                # Get user information for usage tracking
                user_id = GetDecryptedUsername(MockRequest(request_headers)) or "anonymous"
                conversation_id = history_metadata.get("conversation_id", "unknown")
                message_id = str(uuid.uuid4())  # Generate unique message ID for streaming

                logging.info(f"[STREAMING_USAGE] Recording usage for {provider_type} stream response")
                logging.info(f"[USAGE_DEBUG] User: {user_id}, Usage object type: {type(usage_to_record)}")

                # Record usage asynchronously (don't await to avoid blocking)
                asyncio.create_task(record_token_usage(
                    response=usage_to_record,
                    user_id=user_id,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    provider_type=provider_type
                ))

                logging.debug(f"[STREAMING_USAGE] Usage tracking initiated for stream response")

            except Exception as e:
                logging.warning(f"[STREAMING_USAGE] Failed to record streaming usage: {e}")
        else:
            logging.warning(f"[STREAMING_USAGE] No usage information could be recorded (neither real nor estimated)")

    # Helper class for request headers
    class MockRequest:
        def __init__(self, headers):
            self.headers = headers

    return generate(apim_request_id=apim_request_id, history_metadata=history_metadata, provider_type=provider_type)

def LogCallToAiManager(request_body):
    
    try:
        if (app_settings.custom_avanteam_settings.licencehub_key is None or app_settings.custom_avanteam_settings.licencehub_key == ""):
            return jsonify({"status":"ERR", "details":"AVANTEAM_LICENCEHUB_KEY n'est pas défini"}), 200

        logContent = {
            'licenceHubKey' : app_settings.custom_avanteam_settings.licencehub_key,
            'who' : request_body.get("currentUser", "-"),
            'messages' : json.dumps(request_body.get("messages", [])) 
        }

        query_params = {
            'q': 'LogAskMeCall',
            'logContent': encrypt_string(json.dumps(logContent))
        }

        response = requests.get(app_settings.custom_avanteam_settings.licencehub_handlerurl, params=query_params)
        response.raise_for_status()  # raise an exception for HTTP errors

    except Exception as e:
        return jsonify({"status":"ERR", "details":str(e)}), 200
    


async def conversation_internal(request_body, request_headers, preventShouldStream = False):
    try:
        # LogCallToAiManager(request_body)
        logging.debug(f"conversation_internal: stream={app_settings.azure_openai.stream}, use_promptflow={app_settings.base_settings.use_promptflow}, preventShouldStream={preventShouldStream}")

        # Récupérer l'ID utilisateur pour gérer les sessions
        class MockRequest:
            def __init__(self, headers):
                self.headers = headers
        mock_request = MockRequest(request_headers)
        user_id = GetDecryptedUsername(mock_request)
        if user_id:
            # Initialiser la session utilisateur si elle n'existe pas
            if user_id not in user_sessions:
                user_sessions[user_id] = {}
        
        # Vérifier si c'est une commande
        messages = request_body.get("messages", [])
        if messages:
            last_message = messages[-1]
            if last_message.get("role") == "user":
                content = last_message.get("content", "")
                
                # Extraire le texte du contenu (peut être string ou list avec images)
                text_content = ""
                if isinstance(content, str):
                    text_content = content
                elif isinstance(content, list):
                    for part in content:
                        if part.get("type") == "text":
                            text_content = part.get("text", "")
                            break
                
                # Détecter les commandes
                if text_content:
                    commands = command_parser.parse_commands(text_content)
                    if commands:
                        # Exécuter les commandes
                        executor = ChatCommandExecutor(app_settings)
                        current_session = user_sessions.get(user_id, {})
                        result = await executor.execute_commands(commands, current_session)
                        
                        # Mettre à jour la session utilisateur
                        if 'user_session' in result:
                            user_sessions[user_id] = result['user_session']
                        
                        # Gérer les actions spéciales
                        if result.get('action') == 'new_conversation':
                            # Ajouter l'ID de nouvelle conversation
                            result['new_conversation_id'] = str(uuid.uuid4())
                        elif result.get('action') == 'clear_conversation':
                            # Ajouter l'action de nettoyage
                            result['clear_messages'] = True
                        
                        # Retourner la réponse de la commande directement
                        response_id = str(uuid.uuid4())
                        return jsonify({
                            "id": response_id,
                            "choices": [{
                                "messages": [{
                                    "id": response_id,
                                    "role": "assistant", 
                                    "content": result['message'],
                                    "date": datetime.now().isoformat()
                                }]
                            }],
                            "command_result": result
                        })

        # DEBUG: Log incoming messages to see if images are present BEFORE processing
        logging.info(f"DEBUG: conversation_internal received {len(messages)} messages")
        for i, msg in enumerate(messages):
            logging.info(f"DEBUG: Message {i} - role: {msg.get('role')}, content type: {type(msg.get('content'))}")
            if isinstance(msg.get('content'), list):
                for j, part in enumerate(msg['content']):
                    logging.info(f"DEBUG: Message {i}, part {j} - type: {part.get('type')}")
                    if part.get('type') == 'image_url':
                        image_url = part.get('image_url', {}).get('url', '')
                        logging.info(f"DEBUG: Found image_url in conversation_internal, length: {len(image_url)}, preview: {image_url[:50]}...")

        # Appliquer les préférences de session de l'utilisateur
        if user_id and user_id in user_sessions:
            session = user_sessions[user_id]
            logging.info(f"Application des préférences de session pour {user_id}: {session}")
            
            # Appliquer le provider LLM de la session
            if 'llm_provider' in session:
                request_body['customizationPreferences'] = request_body.get('customizationPreferences', {})
                request_body['customizationPreferences']['llmProvider'] = session['llm_provider']
                logging.info(f"Provider LLM appliqué: {session['llm_provider']}")
            
            # Appliquer le nombre de documents de la session
            if 'documents_count' in session:
                request_body['documents_count'] = session['documents_count']
            
            # Appliquer la longueur de réponse de la session
            if 'response_length' in session:
                request_body['customizationPreferences'] = request_body.get('customizationPreferences', {})
                # Mapper les valeurs du backend vers les valeurs du frontend
                response_mapping = {
                    'VERY_SHORT': 'veryShort',
                    'NORMAL': 'medium',
                    'COMPREHENSIVE': 'comprehensive'
                }
                mapped_size = response_mapping.get(session['response_length'], 'medium')
                request_body['customizationPreferences']['responseSize'] = mapped_size

        if app_settings.azure_openai.stream and not app_settings.base_settings.use_promptflow and not preventShouldStream:
            logging.info("[USAGE_DEBUG] Using streaming chat request - TOKENS SHOULD BE RECORDED")
            result = await stream_chat_request(request_body, request_headers)
            
            # Extract provider name for better error messages
            provider_type = request_body.get("provider") or \
                           request_body.get("customizationPreferences", {}).get("llmProvider") or \
                           "AZURE_OPENAI"
            
            response = await make_response(format_as_ndjson(result, provider_name=provider_type))
            response.timeout = None
            response.mimetype = "application/json-lines"
            return response
        else:
            logging.info("[USAGE_DEBUG] Using complete chat request - TOKENS WILL BE RECORDED!")
            logging.info(f"[USAGE_DEBUG] stream={app_settings.azure_openai.stream}, use_promptflow={app_settings.base_settings.use_promptflow}, preventShouldStream={preventShouldStream}")
            result = await complete_chat_request(request_body, request_headers, user_id, provider_type)
            logging.debug(f"complete_chat_request result: {type(result)} - {str(result)[:200]}...")
            return jsonify(result)

    except Exception as ex:
        from backend.llm_providers.errors import LLMProviderErrorHandler
        
        logging.exception(f"Exception in conversation_internal: {ex}")
        
        # Check if this is already an enhanced error with user-friendly message
        if hasattr(ex, 'original_error'):
            # Already processed by our error handler
            error_message = str(ex)
            status_code = getattr(ex, 'status_code', 500)
        else:
            # Process with our error handler
            error_message, status_code = LLMProviderErrorHandler.handle_provider_error(
                exception=ex,
                provider_name="SYSTEM",
                language="fr"
            )
         
        return jsonify({"error": error_message}), status_code

def CheckAuthenticate(request):
    # Si l'authentification est désactivée, autoriser tous les accès
    if not app_settings.base_settings.auth_enabled:
        return True

    # Effectuer la vérification d'authentification
    if "AuthToken" in request.headers:
        salt = datetime.now().strftime("%d%m%Y")
        fullchain = app_settings.custom_avanteam_settings.auth_token + salt
        shaEncoded = sha256(fullchain.encode('utf-8')).hexdigest()
        return request.headers["AuthToken"] == shaEncoded
    else:
        return False
    
def GetDecryptedUsername(request):
    # Si l'authentification est désactivée, utiliser un utilisateur par défaut
    if not app_settings.base_settings.auth_enabled:
        return "dev-user"

    if "EncodedUsername" in request.headers:
        return decrypt_string(request.headers["EncodedUsername"])
    else:
        return None
    

def GetRemainingTokens():
    # Si l'authentification est désactivée, autoriser un nombre illimité de tokens
    if not app_settings.base_settings.auth_enabled:
        return 100000  # Valeur élevée pour ne jamais être négative
        
    if (app_settings.custom_avanteam_settings.licencehub_key is None or app_settings.custom_avanteam_settings.licencehub_key == ""):
        return False

    query_params = {
        'q': 'GetTokensForKey',
        'key': app_settings.custom_avanteam_settings.licencehub_key
    }

    retries = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
    s = requests.Session()
    s.mount('https://', HTTPAdapter(max_retries=retries))

    try:
        response = s.get(app_settings.custom_avanteam_settings.licencehub_handlerurl, params=query_params)
        response.raise_for_status()  # raise an exception for HTTP errors
        nb = int(response.text)
        return nb
    except requests.exceptions.RequestException as e:
        logging.debug(f"Request failed: {e}")
        return False


@bp.route("/conversation", methods=["POST"])
async def conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401

    if GetRemainingTokens() < 0:
        return jsonify({"error": "No tokens left"}), 401
    
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()

    return await conversation_internal(request_json, request.headers)

@bp.route("/conversation-mobile", methods=["POST"])
async def conversation_mobile():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    
    if GetRemainingTokens() < 0:
        return jsonify({"error": "No tokens left"}), 401
    
    if not request.is_json:
        return jsonify({"error": "request must be json"}), 415
    request_json = await request.get_json()
    
    return await conversation_internal(request_json, request.headers, True)

@bp.route("/authenticate", methods=["POST"])
async def authenticate():
    if not(CheckAuthenticate(request)):
        return jsonify({"status": "ko"}), 200

    return jsonify({"status":"ok"}), 200

@bp.route("/frontend_settings", methods=["GET"])
def get_frontend_settings():
    try:
        return jsonify(frontend_settings), 200
    except Exception as e:
        logging.exception("Exception in /frontend_settings")
        return jsonify({"error": str(e)}), 500

@bp.route("/check-tokens", methods=["POST"])
async def check_tokens():

    try:
        if (app_settings.custom_avanteam_settings.licencehub_key is None or app_settings.custom_avanteam_settings.licencehub_key == ""):
            return jsonify({"status":"ERR", "details":"AVANTEAM_LICENCEHUB_KEY n'est pas défini"}), 200

        nb = GetRemainingTokens()
        logging.debug(f"Récupération des tokens : {nb}")
        if (nb <= 0):
            return jsonify({"status":"KO"}), 200
        elif (nb <= app_settings.custom_avanteam_settings.threshold_remaining_alert):
            return jsonify({"status":"WARN"}), 200
        else:
            return jsonify({"status":"OK"}), 200
        

    except Exception as e:
        return jsonify({"status":"ERR", "details":str(e)}), 200
    

## Conversation History API ##
@bp.route("/history/generate", methods=["POST"])
async def add_conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()

    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400
    

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        # make sure cosmos is configured
        if not current_app.cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        # check for the conversation_id, if the conversation is not set, we will create a new one
        history_metadata = {}
        if not conversation_id:
            title = await generate_title(request_json["messages"])
            conversation_dict = await current_app.cosmos_conversation_client.create_conversation(
                user_id=user_id, title=title
            )
            conversation_id = conversation_dict["id"]
            history_metadata["conversation_id"] = conversation_id
            history_metadata["title"] = title
            history_metadata["date"] = conversation_dict["createdAt"]
        else:
            # For existing conversations, still add the conversation_id to metadata
            history_metadata["conversation_id"] = conversation_id

        ## Format the incoming message object in the "chat/completions" messages format
        ## then write it to the conversation history in cosmos
        messages = request_json["messages"]
        if len(messages) > 0 and messages[-1]["role"] == "user":
            createdMessageValue = await current_app.cosmos_conversation_client.create_message(
                uuid=str(uuid.uuid4()),
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
            if createdMessageValue == "Conversation not found":
                raise Exception(
                    "Conversation not found for the given conversation ID: "
                    + conversation_id
                    + "."
                )
        else:
            raise Exception("No user message found")

        # Submit request to Chat Completions for response
        # Use the already parsed request_json instead of parsing again
        request_json["history_metadata"] = history_metadata
        
        # Debug logging pour vérifier la transmission du provider
        provider_from_request = request_json.get('provider')
        provider_from_prefs = request_json.get('customizationPreferences', {}).get('llmProvider') if request_json.get('customizationPreferences') else None
        final_provider = provider_from_request or provider_from_prefs or "DEFAULT (AZURE_OPENAI)"
        print(f"[LLM] LLM Provider utilisé (history/generate): {final_provider}")
        logging.info(f"[LLM] LLM Provider utilisé (history/generate): {final_provider}")
        logging.debug(f"history/generate: provider in request = {request_json.get('provider', 'Not specified')}")
        logging.debug(f"history/generate: customizationPreferences = {request_json.get('customizationPreferences', 'None')}")
        
        return await conversation_internal(request_json, request.headers)

    except Exception as e:
        from backend.llm_providers.errors import LLMProviderErrorHandler
        
        logging.exception("Exception in /history/generate")
        
        # Create user-friendly error message
        error_message, status_code = LLMProviderErrorHandler.handle_provider_error(
            exception=e,
            provider_name="HISTORY_SERVICE",
            language="fr"
        )
        
        return jsonify({"error": error_message}), status_code


@bp.route("/history/update", methods=["POST"])
async def update_conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## check request for conversation_id
    request_json = await request.get_json()
    logging.debug(f"history/update received request: {request_json}")
    conversation_id = request_json.get("conversation_id", None)
    logging.debug(f"history/update conversation_id: {conversation_id}")

    try:
        # make sure cosmos is configured
        if not current_app.cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        # check for the conversation_id, if the conversation is not set, we will create a new one
        if not conversation_id:
            logging.error(f"No conversation_id found in request: {request_json}")
            raise Exception("No conversation_id found")

        ## Format the incoming message object in the "chat/completions" messages format
        ## then write it to the conversation history in cosmos
        messages = request_json["messages"]
        logging.info(f"DEBUG /history/update received {len(messages)} messages: {[{'role': m.get('role'), 'content_type': type(m.get('content')), 'content_preview': str(m.get('content'))[:50] if m.get('content') else 'None'} for m in messages]}")
        
        # Filter out invalid messages (empty objects, missing role, etc.)
        valid_messages = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("role") and msg.get("content") is not None:
                valid_messages.append(msg)
            else:
                logging.warning(f"Filtering out invalid message: {msg}")
        
        messages = valid_messages
        logging.info(f"DEBUG /history/update after filtering: {len(messages)} valid messages")
        
        if len(messages) > 0 and messages[-1]["role"] == "assistant":
            if len(messages) > 1 and messages[-2].get("role", None) == "tool":
                # write the tool message first
                await current_app.cosmos_conversation_client.create_message(
                    uuid=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    user_id=user_id,
                    input_message=messages[-2],
                )
            # write the assistant message
            await current_app.cosmos_conversation_client.create_message(
                uuid=messages[-1]["id"],
                conversation_id=conversation_id,
                user_id=user_id,
                input_message=messages[-1],
            )
        else:
            # Pas de messages valides à sauvegarder, retourner succès sans erreur
            logging.warning(f"No valid messages to save for conversation {conversation_id}, skipping history update")
            response = {"success": True}
            return jsonify(response), 200

        # Submit request to Chat Completions for response
        response = {"success": True}
        return jsonify(response), 200

    except Exception as e:
        logging.exception("Exception in /history/update")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/message_feedback", methods=["POST"])
async def update_message():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## check request for message_id
    request_json = await request.get_json()
    message_id = request_json.get("message_id", None)
    message_feedback = request_json.get("message_feedback", None)
    try:
        if not message_id:
            return jsonify({"error": "message_id is required"}), 400

        if not message_feedback:
            return jsonify({"error": "message_feedback is required"}), 400

        ## update the message in cosmos
        updated_message = await current_app.cosmos_conversation_client.update_message_feedback(
            user_id, message_id, message_feedback
        )
        if updated_message:
            return (
                jsonify(
                    {
                        "message": f"Successfully updated message with feedback {message_feedback}",
                        "message_id": message_id,
                    }
                ),
                200,
            )
        else:
            return (
                jsonify(
                    {
                        "error": f"Unable to update message {message_id}. It either does not exist or the user does not have access to it."
                    }
                ),
                404,
            )

    except Exception as e:
        logging.exception("Exception in /history/message_feedback")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/delete", methods=["DELETE"])
async def delete_conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    ## get the user id from the request headers
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400

        ## make sure cosmos is configured
        if not current_app.cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        ## delete the conversation messages from cosmos first
        deleted_messages = await current_app.cosmos_conversation_client.delete_messages(
            conversation_id, user_id
        )

        ## Now delete the conversation
        deleted_conversation = await current_app.cosmos_conversation_client.delete_conversation(
            user_id, conversation_id
        )

        return (
            jsonify(
                {
                    "message": "Successfully deleted conversation and messages",
                    "conversation_id": conversation_id,
                }
            ),
            200,
        )
    except Exception as e:
        logging.exception("Exception in /history/delete")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/list", methods=["GET"])
async def list_conversations():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    offset = request.args.get("offset", 0)
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## make sure cosmos is configured
    if not current_app.cosmos_conversation_client:
        raise Exception("CosmosDB is not configured or not working")

    ## get the conversations from cosmos
    conversations = await current_app.cosmos_conversation_client.get_conversations(
        user_id, offset=offset, limit=25
    )
    if not isinstance(conversations, list):
        return jsonify({"error": f"No conversations for {user_id} were found"}), 404

    ## return the conversation ids

    return jsonify(conversations), 200


@bp.route("/history/read", methods=["POST"])
async def get_conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400

    ## make sure cosmos is configured
    if not current_app.cosmos_conversation_client:
        raise Exception("CosmosDB is not configured or not working")

    ## get the conversation object and the related messages from cosmos
    conversation = await current_app.cosmos_conversation_client.get_conversation(
        user_id, conversation_id
    )
    ## return the conversation id and the messages in the bot frontend format
    if not conversation:
        return (
            jsonify(
                {
                    "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                }
            ),
            404,
        )

    # get the messages for the conversation from cosmos
    conversation_messages = await current_app.cosmos_conversation_client.get_messages(
        user_id, conversation_id
    )

    ## format the messages in the bot frontend format
    messages = [
        {
            "id": msg["id"],
            "role": msg["role"],
            "content": msg["content"],
            "createdAt": msg["createdAt"],
            "feedback": msg.get("feedback"),
        }
        for msg in conversation_messages
    ]

    return jsonify({"conversation_id": conversation_id, "messages": messages}), 200


@bp.route("/history/rename", methods=["POST"])
async def rename_conversation():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400

    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400

    ## make sure cosmos is configured
    if not current_app.cosmos_conversation_client:
        raise Exception("CosmosDB is not configured or not working")

    ## get the conversation from cosmos
    conversation = await current_app.cosmos_conversation_client.get_conversation(
        user_id, conversation_id
    )
    if not conversation:
        return (
            jsonify(
                {
                    "error": f"Conversation {conversation_id} was not found. It either does not exist or the logged in user does not have access to it."
                }
            ),
            404,
        )

    ## update the title
    title = request_json.get("title", None)
    if not title:
        return jsonify({"error": "title is required"}), 400
    conversation["title"] = title
    updated_conversation = await current_app.cosmos_conversation_client.upsert_conversation(
        conversation
    )

    return jsonify(updated_conversation), 200


@bp.route("/history/delete_all", methods=["DELETE"])
async def delete_all_conversations():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    ## get the user id from the request headers
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400
    

    # get conversations for user
    try:
        ## make sure cosmos is configured
        if not current_app.cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        conversations = await current_app.cosmos_conversation_client.get_conversations(
            user_id, offset=0, limit=None
        )
        if not conversations:
            return jsonify({"error": f"No conversations for {user_id} were found"}), 404

        # delete each conversation
        for conversation in conversations:
            ## delete the conversation messages from cosmos first
            deleted_messages = await current_app.cosmos_conversation_client.delete_messages(
                conversation["id"], user_id
            )

            ## Now delete the conversation
            deleted_conversation = await current_app.cosmos_conversation_client.delete_conversation(
                user_id, conversation["id"]
            )
        return (
            jsonify(
                {
                    "message": f"Successfully deleted conversation and messages for user {user_id}"
                }
            ),
            200,
        )

    except Exception as e:
        logging.exception("Exception in /history/delete_all")
        return jsonify({"error": str(e)}), 500


@bp.route("/history/clear", methods=["POST"])
async def clear_messages():
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    await cosmos_db_ready.wait()
    ## get the user id from the request headers
    # authenticated_user = get_authenticated_user_details(request_headers=request.headers)
    # user_id = authenticated_user["user_principal_id"]

    user_id = GetDecryptedUsername(request)
    if (user_id is None):
        return jsonify({"error": "User not found"}), 400
    ## check request for conversation_id
    request_json = await request.get_json()
    conversation_id = request_json.get("conversation_id", None)

    try:
        if not conversation_id:
            return jsonify({"error": "conversation_id is required"}), 400

        ## make sure cosmos is configured
        if not current_app.cosmos_conversation_client:
            raise Exception("CosmosDB is not configured or not working")

        ## delete the conversation messages from cosmos
        deleted_messages = await current_app.cosmos_conversation_client.delete_messages(
            conversation_id, user_id
        )

        return (
            jsonify(
                {
                    "message": "Successfully deleted messages in conversation",
                    "conversation_id": conversation_id,
                }
            ),
            200,
        )
    except Exception as e:
        logging.exception("Exception in /history/clear_messages")
        return jsonify({"error": str(e)}), 500



@bp.route("/history/ensure", methods=["GET"])
async def ensure_cosmos():
    # Test de santé CosmosDB - pas besoin d'authentification
    await cosmos_db_ready.wait()
    if not app_settings.chat_history:
        return jsonify({"error": "CosmosDB is not configured"}), 404

    try:
        success, err = await current_app.cosmos_conversation_client.ensure()
        if not current_app.cosmos_conversation_client or not success:
            if err:
                return jsonify({"error": err}), 422
            return jsonify({"error": "CosmosDB is not configured or not working"}), 500

        return jsonify({"message": "CosmosDB is configured and working"}), 200
    except Exception as e:
        logging.exception("Exception in /history/ensure")
        cosmos_exception = str(e)
        if "Invalid credentials" in cosmos_exception:
            return jsonify({"error": cosmos_exception}), 401
        elif "Invalid CosmosDB database name" in cosmos_exception:
            return (
                jsonify(
                    {
                        "error": f"{cosmos_exception} {app_settings.chat_history.database} for account {app_settings.chat_history.account}"
                    }
                ),
                422,
            )
        elif "Invalid CosmosDB container name" in cosmos_exception:
            return (
                jsonify(
                    {
                        "error": f"{cosmos_exception}: {app_settings.chat_history.conversations_container}"
                    }
                ),
                422,
            )
        else:
            return jsonify({"error": "CosmosDB is not working"}), 500


@bp.route("/help_content", methods=["GET"])
async def get_help_content():
    """
    Endpoint qui retourne le contenu d'aide à partir d'un fichier JSON.
    Supporte un paramètre de requête 'lang' pour la localisation.
    """
    try:
        language = request.args.get("lang", "FR")
        
        # Chemin vers le fichier de contenu d'aide
        help_content_path = os.path.join(os.path.dirname(__file__), "data", "help_content.json")
        
        # Vérifier si le fichier existe
        if not os.path.exists(help_content_path):
            return jsonify({"error": "Help content file not found"}), 404
            
        # Lire le fichier JSON
        with open(help_content_path, 'r', encoding='utf-8') as file:
            content = json.load(file)
            
        return jsonify(content), 200
        
    except Exception as e:
        logging.exception("Exception in /help_content")
        return jsonify({"error": str(e)}), 500


@bp.route("/upload-document", methods=["POST"])
async def upload_document():
    """
    Endpoint pour traiter l'upload de documents et extraire leur contenu textuel.
    Supporte les formats PDF, Word (.docx) et texte (.txt).
    """
    if not(CheckAuthenticate(request)):
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        # Vérifier qu'un fichier a été uploadé
        files = await request.files
        if 'file' not in files:
            return jsonify({
                "success": False,
                "error": "Aucun fichier fourni. Utilisez le champ 'file' pour l'upload."
            }), 400
        
        uploaded_file = files['file']
        if not uploaded_file.filename:
            return jsonify({
                "success": False,
                "error": "Nom de fichier manquant"
            }), 400
        
        # Lire le contenu du fichier
        file_content = uploaded_file.read()
        if not file_content:
            return jsonify({
                "success": False,
                "error": "Le fichier est vide"
            }), 400
        
        # Traiter le document
        result = DocumentProcessor.process_document(
            filename=uploaded_file.filename,
            file_content=file_content,
            mime_type=uploaded_file.content_type
        )
        
        if result["success"]:
            return jsonify({
                "success": True,
                "text": result["text"],
                "file_info": result["file_info"]
            })
        else:
            return jsonify({
                "success": False,
                "error": result["error"],
                "file_info": result.get("file_info", {})
            }), 400
            
    except Exception as e:
        logging.error(f"Error in upload_document endpoint: {e}")
        return jsonify({
            "success": False,
            "error": f"Erreur serveur lors du traitement du document: {str(e)}"
        }), 500


@bp.route("/api/usage/logs", methods=["GET"])
async def get_usage_logs():
    """Route pour récupérer les logs d'usage avec authentification et filtrage par dates"""
    # Vérification de l'authentification
    if not CheckAuthenticate(request):
        return jsonify({"error": "Authentication required"}), 401

    try:
        usage_service = get_usage_service()

        if not usage_service or not usage_service.enabled:
            return jsonify({"error": "Usage tracking not enabled"}), 503

        # Force l'initialisation du container (le créé s'il n'existe pas)
        await usage_service.init_container()

        if not usage_service.container:
            return jsonify({"error": "Container not available after initialization"}), 503

        # Récupération des paramètres de plage de dates (optionnels)
        start_date = request.args.get('start_date')  # Format: YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS
        end_date = request.args.get('end_date')      # Format: YYYY-MM-DD ou YYYY-MM-DDTHH:MM:SS

        # Construction de la requête avec filtrage par dates si spécifiées
        query = "SELECT * FROM c"
        query_params = []

        # Filtrage par plage de dates si spécifiée
        where_clauses = []
        if start_date:
            try:
                # Conversion de la date de début
                if 'T' not in start_date:
                    start_date += 'T00:00:00'  # Début de journée si pas d'heure spécifiée
                where_clauses.append("c.timestamp >= @start_date")
                query_params.append({"name": "@start_date", "value": start_date})
            except ValueError:
                return jsonify({"error": "Invalid start_date format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"}), 400

        if end_date:
            try:
                # Conversion de la date de fin
                if 'T' not in end_date:
                    end_date += 'T23:59:59'  # Fin de journée si pas d'heure spécifiée
                where_clauses.append("c.timestamp <= @end_date")
                query_params.append({"name": "@end_date", "value": end_date})
            except ValueError:
                return jsonify({"error": "Invalid end_date format. Use YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"}), 400

        # Ajout des clauses WHERE si nécessaires
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += " ORDER BY c.timestamp DESC"

        items = []
        # Exécution de la requête avec paramètres si spécifiés
        if query_params:
            async for item in usage_service.container.query_items(query=query, parameters=query_params):
                items.append({
                    'id': item.get('id'),
                    "timestamp": item.get('timestamp'),
                    "user_id": item.get('user_id'),
                    "provider": item.get('provider'),
                    "input_tokens": item.get('input_tokens', {}).get('total', 0),
                    "output_tokens": item.get('output_tokens', 0),
                    "total_tokens": item.get('total_tokens', 0),
                    "conversation_id": item.get('conversation_id')
                })
        else:
            async for item in usage_service.container.query_items(query=query):
                items.append({
                    'id': item.get('id'),
                    "timestamp": item.get('timestamp'),
                    "user_id": item.get('user_id'),
                    "provider": item.get('provider'),
                    "input_tokens": item.get('input_tokens', {}).get('total', 0),
                    "output_tokens": item.get('output_tokens', 0),
                    "total_tokens": item.get('total_tokens', 0),
                    "conversation_id": item.get('conversation_id')
                })

        # Construction de la réponse avec informations sur le filtrage
        response_data = {
            "success": True,
            "total_records": len(items),
            "records": items,
            "filters": {
                "start_date": start_date,
                "end_date": end_date
            }
        }

        return jsonify(response_data)

    except Exception as e:
        logging.error(f"Exception in /api/usage/logs: {e}")
        return jsonify({"error": f"Error retrieving usage logs: {str(e)}"}), 500


async def generate_title(conversation_messages) -> str:
    ## make sure the messages are sorted by _ts descending
    print("[TITLE GEN] LLM Provider utilisé (génération titre): AZURE_OPENAI (forcé)")
    logging.info("[TITLE GEN] LLM Provider utilisé (génération titre): AZURE_OPENAI (forcé)")
    title_prompt = "Résume la conversation précédente en un titre de 4 mots ou moins DANS LA LANGUE de cette même conversation. N'utilise pas de guillemets ni de ponctuation. N'inclus aucun autre commentaire ou description."

    messages = [
        {"role": msg["role"], "content": msg["content"]}
        for msg in conversation_messages
    ]
    messages.append({"role": "user", "content": title_prompt})

    try:
        azure_openai_client = await init_openai_client()
        response = await azure_openai_client.chat.completions.create(
            model=app_settings.azure_openai.model, messages=messages, temperature=1, max_tokens=64
        )

        title = response.choices[0].message.content
        return title
    except Exception as e:
        logging.exception("Exception while generating title", e)
        return messages[-2]["content"]


@bp.route("/user/session", methods=["GET", "POST"])
async def user_session():
    """Endpoint pour gérer les préférences de session utilisateur"""
    if not CheckAuthenticate(request):
        return jsonify({"error": "Unauthorized"}), 401
    
    user_id = GetDecryptedUsername(request)
    if not user_id:
        return jsonify({"error": "User not found"}), 400
    
    if request.method == "GET":
        # Récupérer les préférences de session
        session = user_sessions.get(user_id, {})
        return jsonify({
            "llm_provider": session.get('llm_provider'),
            "documents_count": session.get('documents_count'),
            "response_length": session.get('response_length')
        })
    
    elif request.method == "POST":
        # Mettre à jour les préférences de session
        try:
            data = await request.get_json()
            if user_id not in user_sessions:
                user_sessions[user_id] = {}
            
            if 'llm_provider' in data:
                user_sessions[user_id]['llm_provider'] = data['llm_provider']
            if 'documents_count' in data:
                user_sessions[user_id]['documents_count'] = data['documents_count']
            if 'response_length' in data:
                user_sessions[user_id]['response_length'] = data['response_length']
            
            return jsonify({
                "status": "success",
                "session": user_sessions[user_id]
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500


def get_encryption_key():
    # Cette fonction doit retourner la clé de chiffrement en base64, comme dans la version .NET
    # Exemple : 'your_base64_encoded_key'
    key_base64 = '+gSxYLZWesSFOppNJg1v7K7VvK4JzbxrLGPH+C6Ettc='
    return base64.b64decode(key_base64)


def encrypt_string(plain_text):
    key = get_encryption_key()
    iv = os.urandom(16)  # Générer un IV aléatoire de 16 octets (128 bits)
    
    # Créer le chiffreur AES avec la clé et l'IV
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Appliquer le padding PKCS7
    padder = padding.PKCS7(algorithms.AES.block_size).padder()
    padded_data = padder.update(plain_text.encode()) + padder.finalize()
    
    # Chiffrer les données
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    
    # Combiner l'IV et les données chiffrées
    combined_data = iv + encrypted_data
    
    # Convertir le résultat en base64
    encrypted_base64 = base64.b64encode(combined_data).decode('utf-8')
    
    return encrypted_base64

def decrypt_string(encrypted_base64):
    key = get_encryption_key()
    
    # Décoder les données en base64
    combined_data = base64.b64decode(encrypted_base64)
    
    # Extraire l'IV (les 16 premiers octets)
    iv = combined_data[:16]
    encrypted_data = combined_data[16:]
    
    # Créer le déchiffreur AES avec la clé et l'IV
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    
    # Déchiffrer les données
    padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
    
    # Retirer le padding PKCS7
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    plain_text = unpadder.update(padded_data) + unpadder.finalize()
    
    # Convertir les données en chaîne de caractères
    return plain_text.decode('utf-8')


@bp.route("/speech/synthesize", methods=["POST"])
async def azure_speech_synthesize():
    """Endpoint pour synthèse vocale Azure Speech Services"""
    try:
        request_json = await request.get_json()
        text = request_json.get("text", "")
        language = request_json.get("language", "FR")
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        # Utiliser le service de synthèse vocale
        result = synthesize_speech_azure(text, language)
        
        if result["success"]:
            return jsonify(result)
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logging.error(f"Error in speech endpoint: {str(e)}")
        return jsonify({"error": f"Speech synthesis failed: {str(e)}"}), 500


@bp.route("/speech/pronunciation", methods=["GET"])
async def get_pronunciations():
    """Récupère le dictionnaire de pronunciations"""
    try:
        return jsonify({"pronunciations": get_pronunciation_dict()})
    except Exception as e:
        logging.error(f"Error getting pronunciations: {str(e)}")
        return jsonify({"error": "Failed to get pronunciations"}), 500


@bp.route("/speech/pronunciation", methods=["POST"])
async def add_pronunciation_rule():
    """Ajoute une règle de pronunciation"""
    try:
        request_json = await request.get_json()
        original = request_json.get("original", "")
        phonetic = request_json.get("phonetic", "")
        
        if not original or not phonetic:
            return jsonify({"error": "Both 'original' and 'phonetic' are required"}), 400
        
        add_pronunciation(original, phonetic)
        return jsonify({"success": True, "message": f"Pronunciation added: {original} -> {phonetic}"})
        
    except Exception as e:
        logging.error(f"Error adding pronunciation: {str(e)}")
        return jsonify({"error": "Failed to add pronunciation"}), 500


@bp.route("/speech/pronunciation/<original>", methods=["DELETE"])
async def remove_pronunciation_rule(original: str):
    """Supprime une règle de pronunciation"""
    try:
        success = remove_pronunciation(original)
        if success:
            return jsonify({"success": True, "message": f"Pronunciation removed: {original}"})
        else:
            return jsonify({"error": f"Pronunciation not found: {original}"}), 404
            
    except Exception as e:
        logging.error(f"Error removing pronunciation: {str(e)}")
        return jsonify({"error": "Failed to remove pronunciation"}), 500


@bp.route("/speech/clean", methods=["POST"])
async def clean_text_for_browser():
    """Nettoie le texte pour la synthèse vocale du navigateur"""
    try:
        request_json = await request.get_json()
        text = request_json.get("text", "")
        
        if not text:
            return jsonify({"error": "Text is required"}), 400
        
        # Nettoyer le texte pour le navigateur
        cleaned_text = clean_text_for_speech(text, for_browser=True)
        
        return jsonify({"success": True, "cleaned_text": cleaned_text})
        
    except Exception as e:
        logging.error(f"Error cleaning text: {str(e)}")
        return jsonify({"error": f"Text cleaning failed: {str(e)}"}), 500


## Usage Tracking API Endpoints ##

@bp.route("/api/usage/current", methods=["GET"])
async def get_current_usage():
    """Get current session usage statistics."""
    if not CheckAuthenticate(request):
        return jsonify({"error": "Authentication required"}), 401

    try:
        # Get user details
        user_details = get_authenticated_user_details(request_headers=dict(request.headers))
        user_id = user_details.get("user_principal_id") if user_details else "anonymous"

        usage_service = get_usage_service()
        if not usage_service or not usage_service.enabled:
            return jsonify({"enabled": False, "message": "Usage tracking not enabled"}), 200

        # Get recent usage (last 1 day)
        summary = await usage_service.get_usage_summary(user_id, days=1)
        summary["period"] = "current_session"

        return jsonify(summary), 200

    except Exception as e:
        logging.exception("Exception in /api/usage/current")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/usage/history", methods=["GET"])
async def get_usage_history():
    """Get usage history with optional filters."""
    if not CheckAuthenticate(request):
        return jsonify({"error": "Authentication required"}), 401

    try:
        # Get user details
        user_details = get_authenticated_user_details(request_headers=dict(request.headers))
        user_id = user_details.get("user_principal_id") if user_details else "anonymous"

        usage_service = get_usage_service()
        if not usage_service or not usage_service.enabled:
            return jsonify({"enabled": False, "message": "Usage tracking not enabled"}), 200

        # Get query parameters
        days = int(request.args.get('days', 7))  # Default to 7 days
        provider = request.args.get('provider')  # Optional provider filter

        # Limit days to reasonable range
        days = min(days, 365)  # Max 1 year

        # Calculate date range from days parameter
        from datetime import datetime, timedelta
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Get usage records
        records = await usage_service.get_user_usage(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            provider=provider
        )

        return jsonify({
            "enabled": True,
            "days": days,
            "provider_filter": provider,
            "record_count": len(records),
            "records": records
        }), 200

    except Exception as e:
        logging.exception("Exception in /api/usage/history")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/usage/summary", methods=["GET"])
async def get_usage_summary():
    """Get usage summary for different time periods."""
    if not CheckAuthenticate(request):
        return jsonify({"error": "Authentication required"}), 401

    try:
        # Get user details
        user_details = get_authenticated_user_details(request_headers=dict(request.headers))
        user_id = user_details.get("user_principal_id") if user_details else "anonymous"

        usage_service = get_usage_service()
        if not usage_service or not usage_service.enabled:
            return jsonify({"enabled": False, "message": "Usage tracking not enabled"}), 200

        # Get summaries for different periods
        summary_today = await usage_service.get_usage_summary(user_id, days=1)
        summary_week = await usage_service.get_usage_summary(user_id, days=7)
        summary_month = await usage_service.get_usage_summary(user_id, days=30)

        return jsonify({
            "enabled": True,
            "user_id": user_id,
            "today": summary_today,
            "this_week": summary_week,
            "this_month": summary_month
        }), 200

    except Exception as e:
        logging.exception("Exception in /api/usage/summary")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/usage/conversation/<conversation_id>", methods=["GET"])
async def get_conversation_usage(conversation_id):
    """Get usage summary for a specific conversation."""
    if not CheckAuthenticate(request):
        return jsonify({"error": "Authentication required"}), 401

    try:
        usage_service = get_usage_service()
        if not usage_service or not usage_service.enabled:
            return jsonify({"enabled": False, "message": "Usage tracking not enabled"}), 200

        # Get conversation usage
        usage_summary = await usage_service.get_conversation_usage(conversation_id)

        return jsonify(usage_summary), 200

    except Exception as e:
        logging.exception(f"Exception in /api/usage/conversation/{conversation_id}")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/admin/usage/stats", methods=["GET"])
async def get_system_usage_stats():
    """Get system-wide usage statistics (admin only)."""
    if not CheckAuthenticate(request):
        return jsonify({"error": "Authentication required"}), 401

    try:
        # TODO: Add admin role check here when available
        # For now, any authenticated user can access this

        usage_service = get_usage_service()
        if not usage_service or not usage_service.enabled:
            return jsonify({"enabled": False, "message": "Usage tracking not enabled"}), 200

        # Get query parameters
        days = int(request.args.get('days', 7))  # Default to 7 days
        days = min(days, 365)  # Max 1 year

        # Get system stats
        stats = await usage_service.get_system_usage_stats(days=days)

        return jsonify(stats), 200

    except Exception as e:
        logging.exception("Exception in /api/admin/usage/stats")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/usage/settings", methods=["GET"])
async def get_usage_settings():
    """Get current usage tracking settings."""
    if not CheckAuthenticate(request):
        return jsonify({"error": "Authentication required"}), 401

    try:
        # Return current usage tracker settings (read-only)
        if hasattr(app_settings, 'usage_tracker'):
            settings = app_settings.usage_tracker
            return jsonify({
                "enabled": settings.enabled,
                "image_tokens_per_byte": settings.image_tokens_per_byte,
                "container_name": settings.cosmos_container_name,
                "providers_with_native_counting": settings.providers_with_native_counting
            }), 200
        else:
            return jsonify({"enabled": False, "message": "Usage tracking not configured"}), 200

    except Exception as e:
        logging.exception("Exception in /api/usage/settings")
        return jsonify({"error": str(e)}), 500


@bp.route("/api/usage/all", methods=["GET"])
async def get_all_usage_logs():
    """Get ALL token usage logs (all users, all providers) - Simple endpoint for debugging."""
    if not CheckAuthenticate(request):
        return jsonify({"error": "Authentication required"}), 401

    try:
        usage_service = get_usage_service()

        if not usage_service or not usage_service.enabled:
            return jsonify({"error": "Usage tracking not enabled"}), 503

        # Initialize container
        await usage_service.init_container()

        if not usage_service.container:
            return jsonify({"error": "Usage tracking container not available"}), 503

        # Query ALL records from CosmosDB (no user filter)
        query = "SELECT * FROM c ORDER BY c.timestamp DESC"

        items = []
        async for item in usage_service.container.query_items(query=query):
            # Format the record for easy viewing
            formatted_record = {
                "message_id": item.get('message_id'),
                "user_id": item.get('user_id'),
                "conversation_id": item.get('conversation_id'),
                "provider": item.get('provider'),
                "input_tokens": item.get('input_tokens', {}).get('total', 0),
                "output_tokens": item.get('output_tokens', 0),
                "total_tokens": item.get('total_tokens', 0),
                "timestamp": item.get('timestamp'),
                "metadata": item.get('metadata', {})
            }
            items.append(formatted_record)

        return jsonify({
            "success": True,
            "total_records": len(items),
            "records": items
        }), 200

    except Exception as e:
        logging.exception("Exception in /api/usage/all")
        return jsonify({"error": str(e)}), 500


app = create_app()