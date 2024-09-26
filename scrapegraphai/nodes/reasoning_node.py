"""
PromptRefinerNode Module
"""
from typing import List, Optional
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel
from langchain_core.utils.pydantic import is_basemodel_subclass
from langchain_openai import ChatOpenAI, AzureChatOpenAI
from langchain_mistralai import ChatMistralAI
from langchain_community.chat_models import ChatOllama
from tqdm import tqdm
from .base_node import BaseNode
from ..utils import transform_schema

class ReasoningNode(BaseNode):
    """
    ...

    Attributes:
        llm_model: An instance of a language model client, configured for generating answers.
        verbose (bool): A flag indicating whether to show print statements during execution.

    Args:
        input (str): Boolean expression defining the input keys needed from the state.
        output (List[str]): List of output keys to be updated in the state.
        node_config (dict): Additional configuration for the node.
        node_name (str): The unique identifier name for the node, defaulting to "GenerateAnswer".
    """

    def __init__(
        self,
        input: str,
        output: List[str],
        node_config: Optional[dict] = None,
        node_name: str = "PromptRefiner",
    ):
        super().__init__(node_name, "node", input, output, 2, node_config)

        self.llm_model = node_config["llm_model"]

        if isinstance(node_config["llm_model"], ChatOllama):
            self.llm_model.format="json"

        self.verbose = (
            True if node_config is None else node_config.get("verbose", False)
        )
        self.force = (
            False if node_config is None else node_config.get("force", False)
        )

        self.additional_info = node_config.get("additional_info", None)
        
        self.output_schema = node_config.get("schema")

    def execute(self, state: dict) -> dict:
        """
        ...

        Args:
            state (dict): The current state of the graph. The input keys will be used
                            to fetch the correct data from the state.

        Returns:
            dict: The updated state with the output key containing the generated answer.

        Raises:
            KeyError: If the input keys are not found in the state, indicating
                      that the necessary information for generating an answer is missing.
        """

        self.logger.info(f"--- Executing {self.node_name} Node ---")

        TEMPLATE_REASONING = """
        **Task**: Analyze the user's request and the provided JSON schema to clearly map the desired data extraction.\n
        Break down the user's request into key components, and then explicitly connect these components to the 
        corresponding elements within the JSON schema.

        **User's Request**:
        {user_input}

        **Desired JSON Output Schema**:
        ```json
        {json_schema}
        ```

        **Analysis Instructions**:
        1. **Break Down User Request:** 
        * Clearly identify the core entities or data types the user is asking for.\n
        * Highlight any specific attributes or relationships mentioned in the request.\n

        2. **Map to JSON Schema**:
        * For each identified element in the user request, pinpoint its exact counterpart in the JSON schema.\n
        * Explain how the schema structure accommodates the user's needs.
        * If applicable, mention any schema elements that are not directly addressed in the user's request.\n

        This analysis will be used to guide the HTML structure examination and ultimately inform the code generation process.\n
        Please generate only the analysis and no other text.

        **Response**:
        """
                
        TEMPLATE_REASONING_WITH_CONTEXT = """
        **Task**: Analyze the user's request, the provided JSON schema, and the additional context the user provided to clearly map the desired data extraction.\n
        Break down the user's request into key components, and then explicitly connect these components to the corresponding elements within the JSON schema.\n

        **User's Request**:
        {user_input}

        **Desired JSON Output Schema**:
        ```json
        {json_schema}
        ```

        **Additional Context**:
        {additional_context}

        **Analysis Instructions**:
        1. **Break Down User Request:** 
        * Clearly identify the core entities or data types the user is asking for.\n
        * Highlight any specific attributes or relationships mentioned in the request.\n

        2. **Map to JSON Schema**:
        * For each identified element in the user request, pinpoint its exact counterpart in the JSON schema.\n
        * Explain how the schema structure accommodates the user's needs.\n
        * If applicable, mention any schema elements that are not directly addressed in the user's request.\n

        This analysis will be used to guide the HTML structure examination and ultimately inform the code generation process.\n
        Please generate only the analysis and no other text.

        **Response**:
        """
        
        user_prompt = state['user_prompt']

        self.simplefied_schema = transform_schema(self.output_schema.schema())
        
        if self.additional_info is not None:
            prompt = PromptTemplate(
                template=TEMPLATE_REASONING_WITH_CONTEXT,
                partial_variables={"user_input": user_prompt,
                                    "json_schema": str(self.simplefied_schema),
                                    "additional_context": self.additional_info})
        else:
            prompt = PromptTemplate(
                template=TEMPLATE_REASONING,
                partial_variables={"user_input": user_prompt,
                                    "json_schema": str(self.simplefied_schema)})

        output_parser = StrOutputParser()

        chain =  prompt | self.llm_model | output_parser
        refined_prompt = chain.invoke({})

        state.update({self.output[0]: refined_prompt})
        return state
