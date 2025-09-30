import os
import json
import logging
from abc import ABC, abstractmethod
from pydantic import (
    BaseModel,
    confloat,
    conint,
    conlist,
    Field,
    field_validator,
    model_validator,
    PrivateAttr,
    ValidationError,
    ValidationInfo
)
from pydantic.alias_generators import to_snake
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Literal, Optional
from typing_extensions import Self
from quart import Request
from backend.utils import parse_multi_columns, generateFilterString,generateFilterStringFromFullDef

DOTENV_PATH = os.environ.get(
    "DOTENV_PATH",
    os.path.join(
        os.path.dirname(
            os.path.dirname(__file__)
        ),
        ".env"
    )
)
# Debug logs removed
MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION = "2024-05-01-preview"


class _UiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UI_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    title: str = "Contoso"
    logo: Optional[str] = None
    chat_logo: Optional[str] = None
    chat_title: str = "Start chatting"
    chat_description: str = "This chatbot is configured to answer your questions"
    favicon: str = "/favicon.ico"
    show_share_button: bool = True
    show_chat_history_button: bool = True
    show_export_button: bool = False
    


class _ChatHistorySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_COSMOSDB_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    database: str
    account: str
    account_key: Optional[str] = None
    conversations_container: str
    enable_feedback: bool = False


class _MongoHistorySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MONGODB_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    uri: str
    database: str
    enable_feedback: bool = False


class _PromptflowSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROMPTFLOW_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    endpoint: str
    api_key: str
    response_timeout: float = 30.0
    request_field_name: str = "query"
    response_field_name: str = "reply"
    citations_field_name: str = "documents"


class _AzureOpenAIFunction(BaseModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    parameters: Optional[dict] = None


class _AzureOpenAITool(BaseModel):
    type: Literal['function'] = 'function'
    function: _AzureOpenAIFunction
    

class _AzureOpenAISettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_OPENAI_",
        env_file=DOTENV_PATH,
        extra='ignore',
        env_ignore_empty=True,
        protected_namespaces=('settings_',)
    )
    
    model: str
    model_name: Optional[str] = None  # The actual model name (e.g. gpt-4o) vs deployment name
    key: Optional[str] = None
    resource: Optional[str] = None
    endpoint: Optional[str] = None
    temperature: float
    top_p: float
    stream: bool
    stop_sequence: Optional[List[str]] = None
    seed: Optional[int] = None
    choices_count: Optional[conint(ge=1, le=128)] = Field(default=1, serialization_alias="n")
    user: Optional[str] = None
    tools: Optional[conlist(_AzureOpenAITool, min_length=1)] = None
    tool_choice: Optional[str] = None
    logit_bias: Optional[dict] = None
    presence_penalty: Optional[confloat(ge=-2.0, le=2.0)] = None
    frequency_penalty: Optional[confloat(ge=-2.0, le=2.0)] = None
    system_message: str
    response_very_short_max_tokens: int
    response_normal_max_tokens: int
    response_comprehensive_max_tokens: int
    preview_api_version: str = MINIMUM_SUPPORTED_AZURE_OPENAI_PREVIEW_API_VERSION
    embedding_endpoint: Optional[str] = None
    embedding_key: Optional[str] = None
    embedding_name: Optional[str] = None
    function_call_azure_functions_enabled: Optional[bool] = False
    function_call_azure_functions_tools_key: Optional[str] = None
    function_call_azure_functions_tools_base_url: Optional[str] = None
    function_call_azure_functions_tool_key: Optional[str] = None
    function_call_azure_functions_tool_base_url: Optional[str] = None
    
    @field_validator('tools', mode='before')
    @classmethod
    def deserialize_tools(cls, tools_json_str: str) -> List[_AzureOpenAITool]:
        if isinstance(tools_json_str, str):
            try:
                tools_dict = json.loads(tools_json_str)
                return _AzureOpenAITool(**tools_dict)
            except json.JSONDecodeError:
                logging.warning("No valid tool definition found in the environment.  If you believe this to be in error, please check that the value of AZURE_OPENAI_TOOLS is a valid JSON string.")
            
            except ValidationError as e:
                logging.warning(f"An error occurred while deserializing the tool definition - {str(e)}")
            
        return None
    
    @field_validator('logit_bias', mode='before')
    @classmethod
    def deserialize_logit_bias(cls, logit_bias_json_str: str) -> dict:
        if isinstance(logit_bias_json_str, str):
            try:
                return json.loads(logit_bias_json_str)
            except json.JSONDecodeError as e:
                logging.warning(f"An error occurred while deserializing the logit bias string -- {str(e)}")
                
        return None
        
    @field_validator('stop_sequence', mode='before')
    @classmethod
    def split_contexts(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def ensure_endpoint(self) -> Self:
        if self.endpoint:
            return Self
        
        elif self.resource:
            self.endpoint = f"https://{self.resource}.openai.azure.com"
            return Self
        
        raise ValidationError("AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_RESOURCE is required")
        
    def extract_embedding_dependency(self) -> Optional[dict]:
        if self.embedding_name:
            return {
                "type": "deployment_name",
                "deployment_name": self.embedding_name
            }
        elif self.embedding_endpoint:
            if self.embedding_key:
                return {
                    "type": "endpoint",
                    "endpoint": self.embedding_endpoint,
                    "authentication": {
                        "type": "api_key",
                        "key": self.embedding_key
                    }
                }
            else:
                return {
                    "type": "endpoint",
                    "endpoint": self.embedding_endpoint,
                    "authentication": {
                        "type": "system_assigned_managed_identity"
                    }
                }
        else:   
            return None
    

class _SearchCommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SEARCH_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    max_search_queries: Optional[int] = None
    allow_partial_result: bool = True
    include_contexts: Optional[List[str]] = ["citations", "intent"]
    vectorization_dimensions: Optional[int] = None
    role_information: str = Field(
        default="You are an AI assistant that helps people find information.",
        validation_alias="AZURE_OPENAI_SYSTEM_MESSAGE"
    )

    @field_validator('include_contexts', mode='before')
    @classmethod
    def split_contexts(cls, comma_separated_string: str, info: ValidationInfo) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return cls.model_fields[info.field_name].get_default()


class DatasourcePayloadConstructor(BaseModel, ABC):
    _settings: '_AppSettings' = PrivateAttr()
    
    def __init__(self, settings: '_AppSettings', **data):
        super().__init__(**data)
        self._settings = settings
    
    @abstractmethod
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        pass


class _AzureSearchSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_SEARCH_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["azure_search"] = PrivateAttr(default="azure_search")
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    service: str = Field(exclude=True)
    endpoint_suffix: str = Field(default="search.windows.net", exclude=True)
    index: str = Field(serialization_alias="index_name")
    key: Optional[str] = Field(default=None, exclude=True)
    use_semantic_search: bool = Field(default=False, exclude=True)
    semantic_search_config: str = Field(default="", serialization_alias="semantic_configuration")
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    query_type: Literal[
        'simple',
        'vector',
        'semantic',
        'vector_simple_hybrid',
        'vectorSimpleHybrid',
        'vector_semantic_hybrid',
        'vectorSemanticHybrid'
    ] = "simple"
    permitted_groups_column: Optional[str] = Field(default=None, exclude=True)
    
    # Constructed fields
    endpoint: Optional[str] = None
    authentication: Optional[dict] = None
    embedding_dependency: Optional[dict] = None
    fields_mapping: Optional[dict] = None
    filter: Optional[str] = Field(default=None, exclude=False)
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def set_endpoint(self) -> Self:
        self.endpoint = f"https://{self.service}.{self.endpoint_suffix}"
        return self
    
    @model_validator(mode="after")
    def set_authentication(self) -> Self:
        if self.key:
            self.authentication = {"type": "api_key", "key": self.key}
        else:
            self.authentication = {"type": "system_assigned_managed_identity"}
            
        return self
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    @model_validator(mode="after")
    def set_query_type(self) -> Self:
        self.query_type = to_snake(self.query_type)

    def _set_filter_string(self, request: Request) -> str:
        if self.permitted_groups_column:
            user_token = request.headers.get("X-MS-TOKEN-AAD-ACCESS-TOKEN", "")
            logging.debug(f"USER TOKEN is {'present' if user_token else 'not present'}")
            if not user_token:
                raise ValueError(
                    "Document-level access control is enabled, but user access token could not be fetched."
                )

            filter_string = generateFilterString(user_token)
            logging.debug(f"FILTER: {filter_string}")
            return filter_string
        
        return None
    
    def _set_filter_string_from_fulldef(self, fulldef: str) -> str:
        if self.permitted_groups_column:
            filter_string = generateFilterStringFromFullDef(fulldef)
            logging.debug(f"FILTER: {filter_string}")
            return filter_string
        
        return None
            
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        fullDef = kwargs.pop('fullDefinition', "*")
        # Récupérer le nombre de documents, s'il est fourni
        documents_count = kwargs.pop('documents_count', None)
        
        if fullDef and self.permitted_groups_column:
            self.filter = self._set_filter_string_from_fulldef(fullDef)

        self.embedding_dependency = \
            self._settings.azure_openai.extract_embedding_dependency()
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        # Mettre à jour le nombre de documents si spécifié
        if documents_count is not None:
            parameters["top_n_documents"] = documents_count
        
        return {
            "type": self._type,
            "parameters": parameters
        }

class _AzureCosmosDbMongoVcoreSettings(
    BaseSettings,
    DatasourcePayloadConstructor
):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_COSMOSDB_MONGO_VCORE_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["azure_cosmosdb"] = PrivateAttr(default="azure_cosmosdb")
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    query_type: Literal['vector'] = "vector"
    connection_string: str = Field(exclude=True)
    index: str = Field(serialization_alias="index_name")
    database: str = Field(serialization_alias="database_name")
    container: str = Field(serialization_alias="container_name")
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    
    # Constructed fields
    authentication: Optional[dict] = None
    embedding_dependency: Optional[dict] = None
    fields_mapping: Optional[dict] = None
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def construct_authentication(self) -> Self:
        self.authentication = {
            "type": "connection_string",
            "connection_string": self.connection_string
        }
        return self
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        # Récupérer le nombre de documents, s'il est fourni
        documents_count = kwargs.pop('documents_count', None)
        
        self.embedding_dependency = \
            self._settings.azure_openai.extract_embedding_dependency()
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        # Mettre à jour le nombre de documents si spécifié
        if documents_count is not None:
            parameters["top_n_documents"] = documents_count
            
        return {
            "type": self._type,
            "parameters": parameters
        }


class _ElasticsearchSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="ELASTICSEARCH_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["elasticsearch"] = PrivateAttr(default="elasticsearch")
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    endpoint: str
    encoded_api_key: str = Field(exclude=True)
    index: str = Field(serialization_alias="index_name")
    query_type: Literal['simple', 'vector'] = "simple"
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    embedding_model_id: Optional[str] = Field(default=None, exclude=True)
    
    # Constructed fields
    authentication: Optional[dict] = None
    embedding_dependency: Optional[dict] = None
    fields_mapping: Optional[dict] = None
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def set_authentication(self) -> Self:
        self.authentication = {
            "type": "encoded_api_key",
            "encoded_api_key": self.encoded_api_key
        }
        
        return self
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        # Récupérer le nombre de documents, s'il est fourni
        documents_count = kwargs.pop('documents_count', None)
        
        self.embedding_dependency = \
            {"type": "model_id", "model_id": self.embedding_model_id} if self.embedding_model_id else \
            self._settings.azure_openai.extract_embedding_dependency() 
            
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        # Mettre à jour le nombre de documents si spécifié
        if documents_count is not None:
            parameters["top_n_documents"] = documents_count
                
        return {
            "type": self._type,
            "parameters": parameters
        }


class _PineconeSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="PINECONE_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["pinecone"] = PrivateAttr(default="pinecone")
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    environment: str
    api_key: str = Field(exclude=True)
    index_name: str
    query_type: Literal["vector"] = "vector"
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    
    # Constructed fields
    authentication: Optional[dict] = None
    embedding_dependency: Optional[dict] = None
    fields_mapping: Optional[dict] = None
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def set_authentication(self) -> Self:
        self.authentication = {
            "type": "api_key",
            "api_key": self.api_key
        }
        
        return self
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        # Récupérer le nombre de documents, s'il est fourni
        documents_count = kwargs.pop('documents_count', None)
        
        self.embedding_dependency = \
            self._settings.azure_openai.extract_embedding_dependency()
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        # Mettre à jour le nombre de documents si spécifié
        if documents_count is not None:
            parameters["top_n_documents"] = documents_count
        
        return {
            "type": self._type,
            "parameters": parameters
        }


class _AzureMLIndexSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_MLINDEX_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["azure_ml_index"] = PrivateAttr(default="azure_ml_index")
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    name: str
    version: str
    project_resource_id: str = Field(validation_alias="AZURE_ML_PROJECT_RESOURCE_ID")
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    
    # Constructed fields
    fields_mapping: Optional[dict] = None
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        # Récupérer le nombre de documents, s'il est fourni
        documents_count = kwargs.pop('documents_count', None)
        
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        # Mettre à jour le nombre de documents si spécifié
        if documents_count is not None:
            parameters["top_n_documents"] = documents_count
        
        return {
            "type": self._type,
            "parameters": parameters
        }


class _AzureSqlServerSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="AZURE_SQL_SERVER_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["azure_sql_server"] = PrivateAttr(default="azure_sql_server")
    
    connection_string: Optional[str] = Field(default=None, exclude=True)
    table_schema: Optional[str] = None
    schema_max_row: Optional[int] = None
    top_n_results: Optional[int] = None
    database_server: Optional[str] = None
    database_name: Optional[str] = None
    port: Optional[int] = None
    
    # Constructed fields
    authentication: Optional[dict] = None
    
    @model_validator(mode="after")
    def construct_authentication(self) -> Self:
        if self.connection_string:
            self.authentication = {
                "type": "connection_string",
                "connection_string": self.connection_string
            }
        elif self.database_server and self.database_name and self.port:
            self.authentication = {
                "type": "system_assigned_managed_identity"
            }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        #parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        return {
            "type": self._type,
            "parameters": parameters
        }
    

class _MongoDbSettings(BaseSettings, DatasourcePayloadConstructor):
    model_config = SettingsConfigDict(
        env_prefix="MONGODB_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    _type: Literal["mongo_db"] = PrivateAttr(default="mongo_db")
    
    endpoint: str
    username: str = Field(exclude=True)
    password: str = Field(exclude=True)
    database_name: str
    collection_name: str
    app_name: str
    index_name: str
    query_type: Literal["vector"] = "vector"
    top_k: int = Field(default=5, serialization_alias="top_n_documents")
    strictness: int = 3
    enable_in_domain: bool = Field(default=True, serialization_alias="in_scope")
    content_columns: Optional[List[str]] = Field(default=None, exclude=True)
    vector_columns: Optional[List[str]] = Field(default=None, exclude=True)
    title_column: Optional[str] = Field(default=None, exclude=True)
    url_column: Optional[str] = Field(default=None, exclude=True)
    filename_column: Optional[str] = Field(default=None, exclude=True)
    
    
    # Constructed fields
    authentication: Optional[dict] = None
    embedding_dependency: Optional[dict] = None
    fields_mapping: Optional[dict] = None
    
    @field_validator('content_columns', 'vector_columns', mode="before")
    @classmethod
    def split_columns(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        return None
    
    @model_validator(mode="after")
    def set_fields_mapping(self) -> Self:
        self.fields_mapping = {
            "content_fields": self.content_columns,
            "title_field": self.title_column,
            "url_field": self.url_column,
            "filepath_field": self.filename_column,
            "vector_fields": self.vector_columns
        }
        return self
    
    @model_validator(mode="after")
    def construct_authentication(self) -> Self:
        self.authentication = {
            "type": "username_and_password",
            "username": self.username,
            "password": self.password
        }
        return self
    
    def construct_payload_configuration(
        self,
        *args,
        **kwargs
    ):
        # Récupérer le nombre de documents, s'il est fourni
        documents_count = kwargs.pop('documents_count', None)
        
        self.embedding_dependency = \
            self._settings.azure_openai.extract_embedding_dependency()
            
        parameters = self.model_dump(exclude_none=True, by_alias=True)
        parameters.update(self._settings.search.model_dump(exclude_none=True, by_alias=True))
        
        # Mettre à jour le nombre de documents si spécifié
        if documents_count is not None:
            parameters["top_n_documents"] = documents_count
        
        return {
            "type": self._type,
            "parameters": parameters
        }
        

class _ClaudeSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="CLAUDE_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    
    api_key: Optional[str] = None
    model: str
    temperature: float
    top_p: float
    system_message: str
    response_very_short_max_tokens: int
    response_normal_max_tokens: int
    response_comprehensive_max_tokens: int


class _OpenAIDirectSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPENAI_DIRECT_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    
    api_key: Optional[str] = None
    model: str
    temperature: float
    top_p: float
    stop_sequence: Optional[str] = None
    base_url: Optional[str] = None
    system_message: str
    response_very_short_max_tokens: int
    response_normal_max_tokens: int
    response_comprehensive_max_tokens: int


class _MistralSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MISTRAL_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )
    
    api_key: Optional[str] = None
    model: str
    temperature: float
    top_p: float
    system_message: str
    response_very_short_max_tokens: int
    response_normal_max_tokens: int
    response_comprehensive_max_tokens: int


class _GeminiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GEMINI_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    api_key: Optional[str] = None
    model: str
    temperature: float
    top_p: float
    system_message: str
    response_very_short_max_tokens: int
    response_normal_max_tokens: int
    response_comprehensive_max_tokens: int


class _OvhSettings(BaseSettings):
    """
    Configuration settings for OVH AI Endpoints provider.

    OVH AI Endpoints offers 40+ open-source AI models through a unified OpenAI-compatible API.
    This provider supports automatic model selection based on query type and context.

    Features:
    - Unified API endpoint for all models
    - Automatic model selection (conversation, coding, reasoning, vision)
    - Manual model switching via chat commands
    - Reasoning content display for supported models
    - European data sovereignty (Gravelines datacenter)
    - Pay-as-you-go pricing with 400 requests/minute limit

    Environment Variables:
    - OVH_AI_ENDPOINTS_ACCESS_TOKEN: Your OVH AI Endpoints access token (required)
    - OVH_MODEL: Default model name (default: llama-3.3-70b)
    - OVH_AUTO_MODEL_SELECTION: Enable automatic model selection (default: true)
    - OVH_BASE_URL: API endpoint URL (default: unified endpoint)
    - OVH_TEMPERATURE: Response creativity (0.0-2.0)
    - OVH_TOP_P: Response diversity control (0.0-1.0)
    - OVH_REASONING_EFFORT: Reasoning intensity for reasoning models (low/medium/high)
    - OVH_SHOW_REASONING_IN_UI: Display reasoning content in interface
    """

    model_config = SettingsConfigDict(
        env_prefix="OVH_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    # Authentication
    ai_endpoints_access_token: Optional[str] = Field(
        default=None,
        description="OVH AI Endpoints access token. Get it from OVH Control Panel > Public Cloud > AI Endpoints"
    )

    # Model Configuration
    model: str = Field(
        default="Meta-Llama-3_3-70B-Instruct",
        description="Default model name. Available: Meta-Llama-3_3-70B-Instruct, Mixtral-8x7B-Instruct-v0_1, Qwen3-32B, gpt-oss-20b, etc."
    )

    auto_model_selection: bool = Field(
        default=True,
        description="Enable automatic model selection based on query type (coding, vision, reasoning, conversation)"
    )

    # API Configuration
    base_url: str = Field(
        default="https://oai.endpoints.kepler.ai.cloud.ovh.net/v1",
        description="OVH AI Endpoints API base URL. Use unified endpoint for best model switching support"
    )

    # Generation Parameters
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Controls response creativity and randomness (0.0 = deterministic, 2.0 = very creative)"
    )

    top_p: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Controls response diversity via nucleus sampling (0.1 = focused, 1.0 = diverse)"
    )

    # Response Length Configuration
    response_very_short_max_tokens: int = Field(
        default=150,
        ge=1,
        le=4096,
        description="Maximum tokens for very short responses"
    )

    response_normal_max_tokens: int = Field(
        default=1000,
        ge=1,
        le=32768,
        description="Maximum tokens for normal responses"
    )

    response_comprehensive_max_tokens: int = Field(
        default=2500,
        ge=1,
        le=32768,
        description="Maximum tokens for comprehensive responses"
    )

    # System Message
    system_message: str = Field(
        default="Tu es un assistant IA serviable, précis et détaillé. Tu réponds en français sauf si on te demande explicitement une autre langue.",
        description="Default system message for conversations"
    )

    # Reasoning Models Configuration (GPT-OSS-20B, DeepSeek-R1)
    reasoning_effort: Literal["low", "medium", "high"] = Field(
        default="medium",
        description="Reasoning intensity for reasoning models (gpt-oss-20b, deepseek-r1). Higher effort = more detailed reasoning"
    )

    show_reasoning_in_ui: bool = Field(
        default=True,
        description="Display reasoning content in the user interface for reasoning models"
    )

    # Rate Limiting Configuration
    max_requests_per_minute: int = Field(
        default=380,
        ge=1,
        le=400,
        description="Max requests per minute (OVH limit: 400/min with auth, 2/min anonymous)"
    )

    retry_after_429: bool = Field(
        default=True,
        description="Automatically retry after rate limit errors (429) with exponential backoff"
    )

    # Advanced Model Configuration
    available_models: Optional[List[str]] = Field(
        default=None,
        description="List of available models. Auto-detected from API if not specified"
    )

    conversation_models: List[str] = Field(
        default=["llama-3.3-70b", "mixtral-8x7b", "qwen-3-32b", "llama-3.1-8b", "mistral-nemo"],
        description="Models optimized for general conversation"
    )

    reasoning_models: List[str] = Field(
        default=["gpt-oss-20b", "deepseek-r1-distill-llama-70b"],
        description="Models with advanced reasoning capabilities"
    )

    coding_models: List[str] = Field(
        default=["qwen-2.5-coder-32b", "codestral-mamba"],
        description="Models specialized for code generation and programming"
    )

    vision_models: List[str] = Field(
        default=["qwen-2.5-vl-72b"],
        description="Models with vision and multimodal capabilities"
    )

    @field_validator('available_models', mode='before')
    @classmethod
    def split_available_models(cls, comma_separated_string: str) -> Optional[List[str]]:
        """Parse comma-separated model names from environment variable."""
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return [model.strip() for model in comma_separated_string.split(',') if model.strip()]
        return None

    @model_validator(mode="after")
    def validate_model_in_available_models(self) -> Self:
        """Ensure the default model is available."""
        if self.available_models and self.model not in self.available_models:
            logging.warning(
                f"OVH model '{self.model}' not in available models list {self.available_models}. "
                f"Using first available model: {self.available_models[0]}"
            )
            self.model = self.available_models[0]
        return self

    def get_model_category(self, model_name: str) -> str:
        """Determine the category of a given model."""
        model_lower = model_name.lower()

        if model_lower in [m.lower() for m in self.reasoning_models]:
            return "reasoning"
        elif model_lower in [m.lower() for m in self.coding_models]:
            return "coding"
        elif model_lower in [m.lower() for m in self.vision_models]:
            return "vision"
        elif model_lower in [m.lower() for m in self.conversation_models]:
            return "conversation"
        else:
            return "conversation"  # Default to conversation

    def supports_reasoning(self, model_name: str) -> bool:
        """Check if a model supports reasoning content."""
        return model_name.lower() in [m.lower() for m in self.reasoning_models]

    def supports_multimodal(self, model_name: str) -> bool:
        """Check if a model supports multimodal input (images, etc.)."""
        return model_name.lower() in [m.lower() for m in self.vision_models]


class _CustomAvanteamSettings(BaseSettings):

    model_config = SettingsConfigDict(
        env_prefix="AVANTEAM_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    auth_token: Optional[str] = None
    licencehub_handlerurl: Optional[str] = None
    licencehub_key: Optional[str] = None
    threshold_remaining_alert: Optional[int] = 100000



class _UsageTrackerSettings(BaseSettings):
    """Configuration for the Usage Tracker system with token counting."""

    model_config = SettingsConfigDict(
        env_prefix="USAGE_TRACKER_",
        env_file=DOTENV_PATH,
        extra="ignore",
        env_ignore_empty=True
    )

    # General settings
    enabled: bool = True

    # Image token counting settings - Simple rule: bytes × multiplier
    image_tokens_per_byte: float = 0.001

    # CosmosDB configuration for usage tracking
    cosmos_container_name: str = "token_usage"
    store_detailed_metrics: bool = True

    # Providers with native token counting (comma-separated string converted to list)
    providers_with_native_counting: Optional[List[str]] = None

    @field_validator('providers_with_native_counting', mode='before')
    @classmethod
    def split_providers(cls, value) -> List[str]:
        if value is None:
            # Use default from environment variable if available
            import os
            env_value = os.getenv("USAGE_TRACKER_PROVIDERS_WITH_NATIVE_COUNTING", "azure_openai,openai_direct,claude")
            return [provider.strip() for provider in env_value.split(',')]
        elif isinstance(value, str) and len(value) > 0:
            return [provider.strip() for provider in value.split(',')]
        elif isinstance(value, list):
            return value
        return ["azure_openai", "openai_direct", "claude"]  # Default providers


class _BaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DOTENV_PATH,
        extra="ignore",
        arbitrary_types_allowed=True,
        env_ignore_empty=True
    )
    datasource_type: Optional[str] = None
    history_provider: str = "COSMOSDB"  # History provider: COSMOSDB or MONGODB
    auth_enabled: bool = Field(default=False, alias="AUTH_ENABLED")  # Explicitly map AUTH_ENABLED env var
    sanitize_answer: bool = False
    use_promptflow: bool = False
    llm_provider: str = "CLAUDE"  # Default provider - can be overridden by env var
    available_llm_providers: Optional[List[str]] = None  # List of providers to expose in UI - loaded from env var
    citation_content_max_length: int = 1000  # Maximum length for citation content displayed in UI
    
    # Voice Features Configuration
    voice_input_enabled: bool = True  # Enable voice input functionality
    wake_word_enabled: bool = True    # Enable wake word detection
    wake_word_phrases: Optional[List[str]] = ["asmi", "askme", "askmi", "asqmi"]  # Wake word phrases
    wake_word_variants: Optional[str] = None  # Wake word phonetic variants (format: word|variant1|variant2,word2|variant3)
    
    # Image Upload Configuration
    image_max_size_mb: float = 10.0  # Maximum image size in MB for upload
    
    # Azure Speech Services Configuration
    azure_speech_enabled: bool = False  # Enable Azure Speech Services for TTS
    azure_speech_key: Optional[str] = None  # Azure Speech Services API key
    azure_speech_region: Optional[str] = "westeurope"  # Azure Speech Services region
    azure_speech_voice_fr: str = "fr-FR-DeniseNeural"  # French voice
    azure_speech_voice_en: str = "en-US-JennyNeural"   # English voice

    # External API Configuration
    external_api_enabled: bool = True  # Enable external REST API for document search
    external_api_keys: Optional[str] = Field(None, env="EXTERNAL_API_KEYS")  # API keys configuration (client:key:ips format)
    external_api_rate_limit_per_minute: int = 60  # Default rate limit per minute
    external_api_rate_limit_per_hour: int = 1000  # Default rate limit per hour
    external_api_max_results: int = 50  # Maximum results per search request
    external_api_request_timeout: int = 30  # Request timeout in seconds

    # Swagger/OpenAPI Documentation
    external_api_swagger_enabled: bool = True  # Enable Swagger UI interface
    external_api_title: str = "AskMe External API"  # API title in documentation
    external_api_description: str = "REST API for external document search integration"  # API description
    external_api_version: str = "1.0.0"  # API version
    
    @field_validator('wake_word_phrases', mode='before')
    @classmethod
    def split_wake_word_phrases(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return [phrase.strip() for phrase in comma_separated_string.split(',')]
        
        return ["asmi", "askme", "askmi", "asqmi"]
    
    def get_wake_word_variants_map(self) -> dict:
        """Parse wake_word_variants into a map of main_word -> [variants]"""
        variants_map = {}
        
        # D'abord, ajouter les phrases principales
        for phrase in self.wake_word_phrases:
            variants_map[phrase.lower()] = [phrase.lower()]
        
        # Ensuite, traiter les variantes si définies
        if self.wake_word_variants:
            for phrase_group in self.wake_word_variants.split(','):
                phrase_group = phrase_group.strip()
                if phrase_group:
                    variants = [variant.strip().lower() for variant in phrase_group.split('|')]
                    if variants:
                        main_word = variants[0]
                        # Ajouter toutes les variantes pour ce mot
                        variants_map[main_word] = variants
        
        return variants_map
    
    @field_validator('available_llm_providers', mode='before')
    @classmethod
    def split_providers(cls, comma_separated_string: str) -> List[str]:
        if isinstance(comma_separated_string, str) and len(comma_separated_string) > 0:
            return parse_multi_columns(comma_separated_string)
        
        # No fallback - if no config provided, return empty list
        return []
    
    @model_validator(mode="after")
    def validate_llm_provider_in_available_list(self) -> Self:
        """Ensure the default LLM provider is in the available providers list."""
        if not self.available_llm_providers:
            # No providers configured - log error and keep default
            logging.error("AVAILABLE_LLM_PROVIDERS is empty or not configured. Please set this environment variable.")
            return self
            
        if self.llm_provider not in self.available_llm_providers:
            # Default provider not in available list, use the first available one
            old_provider = self.llm_provider
            self.llm_provider = self.available_llm_providers[0]
            logging.warning(f"Default LLM provider '{old_provider}' not in available list {self.available_llm_providers}. Using '{self.llm_provider}' instead.")
        return self


class _AppSettings(BaseModel):
    base_settings: _BaseSettings = _BaseSettings()
    azure_openai: _AzureOpenAISettings = _AzureOpenAISettings()
    claude: _ClaudeSettings = _ClaudeSettings()
    openai_direct: _OpenAIDirectSettings = _OpenAIDirectSettings()
    mistral: _MistralSettings = _MistralSettings()
    gemini: _GeminiSettings = _GeminiSettings()
    ovh: _OvhSettings = _OvhSettings()
    search: _SearchCommonSettings = _SearchCommonSettings()
    ui: Optional[_UiSettings] = _UiSettings()
    custom_avanteam_settings: _CustomAvanteamSettings = _CustomAvanteamSettings()
    usage_tracker: _UsageTrackerSettings = _UsageTrackerSettings()

    # Constructed properties
    chat_history: Optional[_ChatHistorySettings] = None
    mongo_history: Optional[_MongoHistorySettings] = None
    datasource: Optional[DatasourcePayloadConstructor] = None
    promptflow: Optional[_PromptflowSettings] = None

    @model_validator(mode="after")
    def set_promptflow_settings(self) -> Self:
        try:
            self.promptflow = _PromptflowSettings()
            
        except ValidationError:
            self.promptflow = None
            
        return self
    
    @model_validator(mode="after")
    def set_chat_history_settings(self) -> Self:
        try:
            self.chat_history = _ChatHistorySettings()

        except ValidationError:
            self.chat_history = None

        return self

    @model_validator(mode="after")
    def set_mongo_history_settings(self) -> Self:
        try:
            self.mongo_history = _MongoHistorySettings()

        except ValidationError:
            self.mongo_history = None

        return self
    
    @model_validator(mode="after")
    def set_datasource_settings(self) -> Self:
        try:
            if self.base_settings.datasource_type == "AzureCognitiveSearch":
                self.datasource = _AzureSearchSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Azure Cognitive Search")
            
            elif self.base_settings.datasource_type == "AzureCosmosDB":
                self.datasource = _AzureCosmosDbMongoVcoreSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Azure CosmosDB Mongo vcore")
            
            elif self.base_settings.datasource_type == "Elasticsearch":
                self.datasource = _ElasticsearchSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Elasticsearch")
            
            elif self.base_settings.datasource_type == "Pinecone":
                self.datasource = _PineconeSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Pinecone")
            
            elif self.base_settings.datasource_type == "AzureMLIndex":
                self.datasource = _AzureMLIndexSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Azure ML Index")
            
            elif self.base_settings.datasource_type == "AzureSqlServer":
                self.datasource = _AzureSqlServerSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using SQL Server")
            
            elif self.base_settings.datasource_type == "MongoDB":
                self.datasource = _MongoDbSettings(settings=self, _env_file=DOTENV_PATH)
                logging.debug("Using Mongo DB")
                
            else:
                self.datasource = None
                logging.warning("No datasource configuration found in the environment -- calls will be made to Azure OpenAI without grounding data.")
                
            return self

        except ValidationError as e:
            logging.warning("No datasource configuration found in the environment -- calls will be made to Azure OpenAI without grounding data.")
            logging.warning(e.errors())


app_settings = _AppSettings()
