"""
Enhanced Manufacturing Agent for CPG Manufacturing Operations.

This module provides an AI agent that routes manufacturing queries to specialized
toolsets based on query type, using LangGraph for workflow orchestration.
"""

import logging
import uuid
from typing import Dict, List, Optional, Callable, Union
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, END, MessagesState
from toolbox_langchain import ToolboxClient
from couchbase.cluster import Cluster
from langgraph_checkpointer_couchbase import AsyncCouchbaseSaver

from src.models.manufacturing_models import OperatorQuery, AIResponse
from src.tools.couchbase_manual_retriever import create_couchbase_manual_tools
from src.config.config import settings

# Configure logging
logger = logging.getLogger(__name__)

# =============================================================================
# CONSTANTS AND CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class AgentConfig:
    """Configuration constants for the manufacturing agent."""
    
    # Default toolbox URL
    DEFAULT_TOOLBOX_URL: str = "http://127.0.0.1:5000"
    
    # LLM configuration
    MODEL_NAME: str = "gemini-2.5-flash"
    TEMPERATURE: float = 0.1
    
    # Thread ID template
    THREAD_ID_TEMPLATE: str = "react_agent_thread_{operator_id}_{toolset_key}"
    
    # Error messages
    AGENT_NOT_FOUND_ERROR: str = "Critical failure: Agent for toolset {toolset_key} not found or could not be initialized."
    PROCESSING_ERROR: str = "I apologize, but I encountered an error while processing your query: {error}. Please try rephrasing your question or contact technical support if the issue persists."
    NO_RESPONSE_ERROR: str = "Error: No response from AI."


# Toolset mappings
TOOLSETS = {
    "troubleshooting": "troubleshooting",
    "maintenance": "maintenance-planning", 
    "monitoring": "production-monitoring",
    "performance": "performance-analysis",
    "general": "full-manufacturing-suite"
}

DEFAULT_TOOLSET = "full-manufacturing-suite"

# Node name mappings for the graph
TOOLSET_TO_NODE_SUFFIX = {
    "troubleshooting": "troubleshooting",
    "maintenance-planning": "maintenance", 
    "production-monitoring": "monitoring",
    "performance-analysis": "performance",
    "full-manufacturing-suite": "general"
}

# System prompts for different agent types
SYSTEM_PROMPTS = {
    "troubleshooting": """You are a manufacturing troubleshooting expert. Help operators identify and resolve equipment issues safely.

Use available tools to gather information. For errors codes, must use both manual search tools and past solutions tools and show them separately.
Provide step-by-step instructions with specific manual sections/error codes. Escalate complex issues to maintenance.""",

    "maintenance": """You are a maintenance planning specialist. Help manage scheduled and unscheduled maintenance activities.

Use tools to check upcoming/overdue maintenance. Prioritize critical tasks and coordinate to minimize downtime.""",

    "monitoring": """You are a production monitoring assistant. Provide real-time visibility into production line status.

Use monitoring tools for current data. Base all responses strictly on retrieved system information.""",

    "performance": """You are a performance analyst. Help analyze and improve production efficiency.

Use efficiency tools to analyze trends over specified periods. Provide data-driven insights for improvement decisions.""",

    "general": """You are a CPG manufacturing operations expert. Help with troubleshooting, monitoring, maintenance, and performance optimization.

Use appropriate tools for information gathering. For errors codes, must use both manual search tools and past solutions tools and show them separately.
Prioritize safety, provide actionable steps, reference specific data/sources, and suggest preventive measures."""
}

# =============================================================================
# STATE AND EXCEPTIONS
# =============================================================================

class AgentGraphState(MessagesState):
    """State class for the agent graph workflow."""
    operator_query: OperatorQuery
    current_route: str


class AgentInitializationError(Exception):
    """Raised when agent initialization fails."""
    pass


class ToolsetNotFoundError(Exception):
    """Raised when a requested toolset is not found."""
    pass


# =============================================================================
# MAIN AGENT CLASS
# =============================================================================

class EnhancedManufacturingAgent:
    """
    Enhanced manufacturing agent that routes queries to specialized toolsets.
    
    This agent uses LangGraph to create a workflow where each toolset-specific 
    agent is a distinct node. It routes manufacturing queries based on their type
    and provides specialized responses using the appropriate tools.
    """
    
    def __init__(
        self, 
        cluster: Optional[Cluster] = None, 
        checkpointer: Optional[AsyncCouchbaseSaver] = None, 
        toolbox_url: str = AgentConfig.DEFAULT_TOOLBOX_URL
    ):
        """
        Initialize the Enhanced Manufacturing Agent.
        
        Args:
            cluster: Optional Couchbase cluster instance for manual search tools
            checkpointer: Optional AsyncCouchbaseSaver for state persistence
            toolbox_url: URL for the toolbox service
            
        Raises:
            AgentInitializationError: If agent initialization fails
        """
        self.config = AgentConfig()
        self.toolbox_url = toolbox_url
        self.cluster = cluster
        self.checkpointer = checkpointer
        
        try:
            # Initialize core components
            self.llm = self._initialize_llm()
            self.manual_search_tools = self._initialize_manual_search_tools()
            self.agent_cache: Dict[str, object] = {}
            
            # Initialize agents and build graph
            self.agents = self._initialize_all_agents()
            self.graph = self._build_workflow_graph()
            
            logger.info("Enhanced Manufacturing Agent initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Enhanced Manufacturing Agent: {e}", exc_info=True)
            raise AgentInitializationError(f"Agent initialization failed: {e}") from e

    # =========================================================================
    # INITIALIZATION METHODS
    # =========================================================================

    def _initialize_llm(self) -> ChatGoogleGenerativeAI:
        """Initialize and configure the language model."""
        return ChatGoogleGenerativeAI(
            model=self.config.MODEL_NAME,
            temperature=self.config.TEMPERATURE,
            api_key=settings.google_api_key
        )

    def _initialize_manual_search_tools(self) -> List[BaseTool]:
        """
        Initialize manual search tools if Couchbase cluster is available.
        
        Returns:
            List of manual search tools, empty if cluster not available
        """
        if not self.cluster:
            logger.warning("No Couchbase cluster provided - manual search tools unavailable")
            return []
            
        try:
            tools = [create_couchbase_manual_tools(self.cluster)]
            logger.info("Initialized Couchbase manual search tools")
            return tools
        except Exception as e:
            logger.error(f"Failed to initialize manual search tools: {e}")
            return []

    def _initialize_all_agents(self) -> Dict[str, object]:
        """
        Pre-initialize all ReAct agents for different toolsets.
        
        Returns:
            Dictionary mapping agent keys to initialized agents
            
        Raises:
            AgentInitializationError: If any agent fails to initialize
        """
        try:
            agents = {}
            for agent_key, toolset_name in TOOLSETS.items():
                agents[agent_key] = self._create_react_agent(toolset_name, agent_key)
            
            logger.info(f"Successfully initialized {len(agents)} ReAct agents")
            return agents
            
        except Exception as e:
            logger.error(f"Failed to initialize agents: {e}", exc_info=True)
            raise AgentInitializationError(f"Agent initialization failed: {e}") from e

    # =========================================================================
    # AGENT CREATION METHODS
    # =========================================================================

    def _create_react_agent(self, toolset_name: str, agent_key: str) -> object:
        """
        Create and cache a ReAct agent for the specified toolset.
        
        Args:
            toolset_name: Name of the toolset to create agent for
            agent_key: Key to identify the agent type
            
        Returns:
            Configured ReAct agent
        """
        # Check cache first
        if toolset_name in self.agent_cache:
            return self.agent_cache[toolset_name]
        
        logger.info(f"Creating ReAct agent for toolset: {toolset_name}")
        
        try:
            # Prepare tools and configuration
            all_tools = self._prepare_agent_tools(toolset_name)
            system_prompt = self._get_system_prompt(agent_key)
            
            # Create and cache agent
            react_agent = self._build_react_agent(all_tools, system_prompt)
            self.agent_cache[toolset_name] = react_agent
            
            logger.info(f"Successfully created and cached agent for: {toolset_name}")
            return react_agent
            
        except Exception as e:
            logger.error(f"Failed to create agent for toolset '{toolset_name}': {e}")
            raise

    def _prepare_agent_tools(self, toolset_name: str) -> List[BaseTool]:
        """
        Prepare all tools for a specific toolset.
        
        Args:
            toolset_name: Name of the toolset
            
        Returns:
            List of tools for the toolset
        """
        # Load toolbox tools
        toolbox_tools = self._load_toolbox_tools(toolset_name)
        
        # Add manual search tools for troubleshooting and general agents
        if self._should_include_manual_tools(toolset_name):
            all_tools = toolbox_tools + self.manual_search_tools
            logger.info(f"Added {len(self.manual_search_tools)} manual search tools for {toolset_name}")
        else:
            all_tools = toolbox_tools
            
        logger.info(f"Prepared {len(all_tools)} tools for toolset '{toolset_name}'")
        return all_tools

    def _load_toolbox_tools(self, toolset_name: str) -> List[BaseTool]:
        """
        Load tools from the toolbox service for a specific toolset.
        
        Args:
            toolset_name: Name of the toolset
            
        Returns:
            List of tools from the toolbox
        """
        try:
            toolbox_client = ToolboxClient(self.toolbox_url)
            tools = list(toolbox_client.load_toolset(toolset_name) or [])
            logger.info(f"Loaded {len(tools)} tools from toolbox for '{toolset_name}'")
            return tools
        except Exception as e:
            logger.error(f"Failed to load tools for toolset '{toolset_name}': {e}")
            return []

    def _should_include_manual_tools(self, toolset_name: str) -> bool:
        """Check if manual search tools should be included for the toolset."""
        return (
            toolset_name in ["troubleshooting", "full-manufacturing-suite"] 
            and self.manual_search_tools
        )

    def _get_system_prompt(self, agent_key: str) -> str:
        """Get the system prompt for an agent type."""
        return SYSTEM_PROMPTS.get(agent_key, SYSTEM_PROMPTS['general'])

    def _build_react_agent(self, tools: List[BaseTool], system_prompt: str) -> object:
        """Build a ReAct agent with the given tools and system prompt."""
        return create_react_agent(
            model=self.llm,
            tools=tools,
            checkpointer=self.checkpointer,
            prompt=system_prompt,
            debug=True
        )

    # =========================================================================
    # GRAPH WORKFLOW METHODS
    # =========================================================================

    def _build_workflow_graph(self) -> object:
        """
        Build the LangGraph workflow with routing and agent nodes.
        
        Returns:
            Compiled workflow graph
        """
        workflow = StateGraph(AgentGraphState)
        
        # Add router node
        workflow.add_node("router", self._router_node)
        
        # Add agent nodes and edges
        node_names = self._add_agent_nodes(workflow)
        
        # Configure routing
        self._configure_workflow_routing(workflow, node_names)
        
        return workflow.compile()

    def _add_agent_nodes(self, workflow: StateGraph) -> List[str]:
        """
        Add agent nodes to the workflow graph.
        
        Args:
            workflow: The StateGraph workflow to add nodes to
            
        Returns:
            List of added node names
        """
        node_names = []
        
        for toolset_key, toolset_name in TOOLSETS.items():
            node_name = self._get_node_name(toolset_name)
            node_method = self._create_agent_node_method(toolset_key)
            
            workflow.add_node(node_name, node_method)
            workflow.add_edge(node_name, END)
            node_names.append(node_name)
        
        return node_names

    def _configure_workflow_routing(self, workflow: StateGraph, node_names: List[str]) -> None:
        """Configure the workflow routing from router to agent nodes."""
        workflow.set_entry_point("router")
        
        conditional_path_map = {node_name: node_name for node_name in node_names}
        workflow.add_conditional_edges(
            "router",
            lambda state: state["current_route"],
            conditional_path_map
        )

    # =========================================================================
    # ROUTING AND EXECUTION METHODS
    # =========================================================================

    async def _router_node(self, state: AgentGraphState) -> Dict[str, str]:
        """
        Route queries to the appropriate agent node based on query type.
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with routing information
        """
        operator_query = state['operator_query']
        query_type = operator_query.query_type
        
        logger.info(f"Routing query_type: {query_type}")
        
        # Determine route destination
        toolset_name = self._select_toolset(query_type)
        route_destination = self._get_node_name(toolset_name)
        
        logger.info(f"Selected toolset '{toolset_name}', routing to '{route_destination}'")
        return {"current_route": route_destination}

    async def _execute_agent_node(self, state: AgentGraphState, toolset_key: str) -> Dict[str, List[AIMessage]]:
        """
        Execute a specific agent node and return its response.
        
        Args:
            state: Current graph state
            toolset_key: Key identifying the toolset agent to execute
            
        Returns:
            Dictionary with the agent's response message
        """
        agent = self.agents.get(toolset_key)
        
        if not agent:
            error_msg = self.config.AGENT_NOT_FOUND_ERROR.format(toolset_key=toolset_key)
            logger.error(error_msg)
            return {"messages": [AIMessage(content=error_msg)]}
        
        try:
            # Prepare execution context
            execution_config = self._prepare_execution_config(state, toolset_key)
            inputs = {"messages": state['messages']}
            
            # Execute agent
            response = await agent.ainvoke(inputs, config=execution_config)
            
            # Extract and return final message
            final_message = response["messages"][-1]
            logger.info(f"Agent ({toolset_key}) response: {final_message.content[:100]}...")
            
            return {"messages": [final_message]}
        
        except Exception as e:
            error_msg = f"Error executing agent for toolset {toolset_key}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"messages": [AIMessage(content=error_msg)]}

    def _prepare_execution_config(self, state: AgentGraphState, toolset_key: str) -> Dict[str, Dict[str, str]]:
        """Prepare the execution configuration for an agent."""
        operator_query = state['operator_query']
        thread_id = self.config.THREAD_ID_TEMPLATE.format(
            operator_id=operator_query.operator_id, 
            toolset_key=toolset_key
        )
        return {"configurable": {"thread_id": thread_id}}

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def _get_node_name(self, toolset_name: str) -> str:
        """Generate node name for a given toolset."""
        suffix = TOOLSET_TO_NODE_SUFFIX.get(toolset_name, "general")
        return f"{suffix}_agent_node"

    def _select_toolset(self, query_type: str) -> str:
        """Select the appropriate toolset based on query type."""
        return TOOLSETS.get(query_type, DEFAULT_TOOLSET)

    def _create_agent_node_method(self, toolset_key: str) -> Callable:
        """Create an agent node method for a specific toolset."""
        async def agent_node_method(state: AgentGraphState):
            return await self._execute_agent_node(state, toolset_key)
        return agent_node_method

    # =========================================================================
    # PUBLIC API METHODS
    # =========================================================================

    async def process_query(self, operator_query: OperatorQuery) -> AIResponse:
        """
        Process an operator query and return AI response.
        
        Args:
            operator_query: The operator query to process
            
        Returns:
            AIResponse with the agent's response
        """
        logger.info(f"Processing query {operator_query.query_id}: {operator_query.query_text}")
        
        try:
            # Prepare and execute workflow
            initial_state = self._create_initial_state(operator_query)
            final_state = await self.graph.ainvoke(initial_state)
            
            # Extract response and create result
            response_text = self._extract_final_response(final_state)
            
            logger.info(f"Successfully processed query {operator_query.query_id}")
            
            return AIResponse(
                response_id=str(uuid.uuid4()),
                query_id=operator_query.query_id,
                response_text=response_text,
            )
            
        except Exception as e:
            logger.error(f"Error processing query '{operator_query.query_id}': {e}", exc_info=True)
            return self._create_error_response(operator_query, str(e))

    def _create_initial_state(self, operator_query: OperatorQuery) -> AgentGraphState:
        """Create the initial state for graph execution."""
        return AgentGraphState(
            messages=[HumanMessage(content=operator_query.query_text)],
            operator_query=operator_query,
            current_route=""
        )

    def _extract_final_response(self, final_state: Dict[str, Union[List, str]]) -> str:
        """Extract the final response text from the graph execution state."""
        if final_state and final_state.get("messages"):
            final_message = final_state["messages"][-1]
            return getattr(final_message, 'content', str(final_message))
        return self.config.NO_RESPONSE_ERROR

    def _create_error_response(self, operator_query: OperatorQuery, error_message: str) -> AIResponse:
        """Create an error response for failed queries."""
        return AIResponse(
            response_id=str(uuid.uuid4()),
            query_id=operator_query.query_id,
            response_text=self.config.PROCESSING_ERROR.format(error=error_message),
        )


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_manufacturing_agent(
    cluster: Optional[Cluster] = None,
    checkpointer: Optional[AsyncCouchbaseSaver] = None,
    toolbox_url: str = AgentConfig.DEFAULT_TOOLBOX_URL
) -> EnhancedManufacturingAgent:
    """
    Factory function to create an EnhancedManufacturingAgent.
    
    Args:
        cluster: Optional Couchbase cluster instance
        checkpointer: Optional AsyncCouchbaseSaver for state persistence
        toolbox_url: URL for the toolbox service
        
    Returns:
        Configured EnhancedManufacturingAgent instance
        
    Raises:
        AgentInitializationError: If agent creation fails
    """
    return EnhancedManufacturingAgent(
        cluster=cluster, 
        checkpointer=checkpointer,
        toolbox_url=toolbox_url
    ) 