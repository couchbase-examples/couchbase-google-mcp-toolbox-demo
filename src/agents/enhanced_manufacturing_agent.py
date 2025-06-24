import logging
import uuid
from typing import Dict, Any, List, Optional, Callable, Union

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from toolbox_langchain import ToolboxClient
from couchbase.cluster import Cluster
from langgraph_checkpointer_couchbase import AsyncCouchbaseSaver

from src.models.manufacturing_models import OperatorQuery, AIResponse
from src.tools.couchbase_manual_retriever import create_couchbase_manual_tools
from src.config.config import settings

logger = logging.getLogger(__name__)

# Constants
TOOLSETS = {
    "troubleshooting": "troubleshooting",
    "maintenance": "maintenance-planning", 
    "monitoring": "production-monitoring",
    "performance": "performance-analysis",
    "general": "full-manufacturing-suite"
}

DEFAULT_TOOLSET = "full-manufacturing-suite"

SYSTEM_PROMPTS = {
    "troubleshooting": """You are an expert AI assistant for troubleshooting manufacturing equipment.
Your primary role is to help operators identify and resolve issues with machines on the production line.

**Use the necessary tools to get the information you need to answer the question.**

Guidelines for responses:
1. **Safety First**: Always prioritize safety in your recommendations.
2. **Analyze**: Correlate information from different tools to find the root cause of the issue.
3. **Actionable Guidance**: Provide clear, step-by-step instructions. Reference specific manual sections or error codes from tool results.
4. **Escalate**: If an issue is beyond the scope of an operator, recommend escalating to the appropriate maintenance personnel.""",

    "maintenance": """You are an AI assistant specialized in maintenance planning for a CPG manufacturing facility.
Your goal is to help operators and maintenance staff manage scheduled and unscheduled maintenance activities.

**Use the necessary tools to get the information you need to answer the question.**

Guidelines for responses:
1. **Proactive Planning**: Help users to check for upcoming or overdue maintenance to plan their work using `get-upcoming-maintenance` and `get-overdue-maintenance`.
2. **Prioritization**: Clearly highlight overdue and critical upcoming maintenance tasks.
3. **Efficiency**: Help coordinate maintenance activities to minimize production downtime by providing accurate maintenance schedules.""",

    "monitoring": """You are an AI assistant for production monitoring in a CPG manufacturing plant.
Your job is to provide real-time visibility into the status of production lines and the overall facility.

**Use the necessary tools to get the information you need to answer the question.**

Guidelines for responses:
1. **Real-time Status**: Provide the most up-to-date information on production lines using the available tools.
2. **Data-Driven**: Base all responses strictly on the data retrieved from the production system tools.""",

    "performance": """You are an AI performance analyst for a CPG manufacturing facility.
Your role is to help supervisors and engineers analyze and improve production efficiency.

**Use the necessary tools to get the information you need to answer the question.**

Guidelines for responses:
1. **Analyze Trends**: When asked for performance, use the `get-line-efficiency` tool to analyze trends over a specified period.
2. **Reporting**: Provide clear and concise summaries of performance metrics.
3. **Data-Driven Insights**: Offer insights based on historical data to support decision-making for performance improvements.""",

    "general": """You are an expert AI assistant for Consumer Packaged Goods (CPG) manufacturing operations.
Your role is to help operators troubleshoot issues, monitor production, and maintain optimal efficiency.

**Use the necessary tools to get the information you need to answer the question.**

Guidelines for responses:
1. **Safety First**: Always prioritize safety in your recommendations
2. **Data-Driven**: Use appropriate tools to gather relevant context
3. **Comprehensive**: Consider all available information sources when responding
4. **Actionable**: Provide clear, step-by-step actions when possible
5. **Contextual**: Consider machine history, recent alerts, and maintenance status
6. **Preventive**: Suggest preventive measures when appropriate
7. **Concise**: Be thorough but concise in your explanations

When responding to queries:
- Assess what information you need to provide a complete answer
- Use the most appropriate tools for gathering that information
- Cross-reference multiple sources when beneficial
- Provide escalation steps if issues are beyond operator capabilities
- Reference specific data points, alert IDs, manual sections, and sources from tool results

Always base your responses on current system data and authoritative sources."""
}

# Node name mappings
TOOLSET_TO_NODE_SUFFIX = {
    "troubleshooting": "troubleshooting",
    "maintenance-planning": "maintenance", 
    "production-monitoring": "monitoring",
    "performance-analysis": "performance",
    "full-manufacturing-suite": "general"
}


class AgentGraphState(MessagesState):
    """State class for the agent graph workflow."""
    operator_query: OperatorQuery
    current_route: str


class EnhancedManufacturingAgent:
    """
    Enhanced manufacturing agent where each toolset-specific agent is a distinct node 
    in a LangGraph workflow.
    """
    
    def __init__(self, cluster: Cluster, checkpointer: AsyncCouchbaseSaver, 
                 toolbox_url: str = "http://127.0.0.1:5000"):
        """
        Initialize the Enhanced Manufacturing Agent.
        
        Args:
            cluster: Couchbase cluster instance
            checkpointer: AsyncCouchbaseSaver for state persistence
            toolbox_url: URL for the toolbox service
        """
        self.toolbox_url = toolbox_url
        self.cluster = cluster
        self.checkpointer = checkpointer
        
        # Initialize LLM
        self.llm = self._initialize_llm()
        
        # Initialize tools and agents
        self.manual_search_tools = self._initialize_manual_search_tools()
        self.agent_cache: Dict[str, Any] = {}
        self.agents = self._initialize_agents()
        
        # Build the workflow graph
        self.graph = self._build_graph()

    def _initialize_llm(self) -> ChatGoogleGenerativeAI:
        """Initialize the language model."""
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-pro-preview-03-25",
            temperature=0.1,
            api_key=settings.google_api_key
        )

    def _initialize_manual_search_tools(self) -> List[Any]:
        """Initialize manual search tools if cluster is available."""
        if not self.cluster:
            logger.warning("No Couchbase client provided - manual search tools will not be available")
            return []
            
        tools = [create_couchbase_manual_tools(self.cluster)]
        logger.info("Initialized Couchbase manual search tools")
        return tools

    def _initialize_agents(self) -> Dict[str, Any]:
        """Pre-initialize all ReAct agents for different toolsets."""
        try:
            agents = {}
            for agent_key, toolset_name in TOOLSETS.items():
                agents[agent_key] = self._create_react_agent(toolset_name, agent_key)
            
            logger.info(f"Successfully pre-initialized ReAct agents for toolsets: {set(TOOLSETS.values())}")
            return agents
            
        except Exception as e:
            logger.error(f"Failed to pre-initialize agents: {e}", exc_info=True)
            raise

    def _create_react_agent(self, toolset_name: str, agent_key: str) -> Any:
        """Create a ReAct agent for the specified toolset."""
        if toolset_name in self.agent_cache:
            return self.agent_cache[toolset_name]
        
        logger.info(f"Initializing ReAct agent for toolset: {toolset_name}")
        
        try:
            # Load and prepare tools
            toolbox_tools = self._load_toolbox_tools(toolset_name)
            all_tools = self._prepare_tools_for_toolset(toolset_name, toolbox_tools)
            
            # Get system prompt
            system_prompt = SYSTEM_PROMPTS.get(agent_key, SYSTEM_PROMPTS['general'])

            # Create and cache agent
            react_agent = self._build_react_agent(all_tools, system_prompt)
            self.agent_cache[toolset_name] = react_agent
            
            logger.info(f"Successfully initialized and cached ReAct agent for toolset: {toolset_name}")
            return react_agent
            
        except Exception as e:
            logger.error(f"Failed to create ReAct agent for toolset '{toolset_name}': {e}")
            raise

    def _load_toolbox_tools(self, toolset_name: str) -> List[Any]:
        """Load tools from the toolbox for a specific toolset."""
        toolbox_tools = list(ToolboxClient(self.toolbox_url).load_toolset(toolset_name) or [])
        logger.info(f"Loaded {len(toolbox_tools)} tools from GenAI Toolbox for toolset '{toolset_name}'")
        return toolbox_tools

    def _prepare_tools_for_toolset(self, toolset_name: str, toolbox_tools: List[Any]) -> List[Any]:
        """Prepare all tools for a specific toolset, including manual search tools for troubleshooting."""
        all_tools = toolbox_tools
        
        if toolset_name == "troubleshooting" and self.manual_search_tools:
            all_tools = toolbox_tools + self.manual_search_tools
            logger.info(f"Added {len(self.manual_search_tools)} manual search tools for troubleshooting agent")
            
        logger.info(f"Total tools available for toolset '{toolset_name}': {len(all_tools)}")
        return all_tools

    def _build_react_agent(self, tools: List[Any], system_prompt: str) -> Any:
        """Build a ReAct agent with the given tools and system prompt."""
        react_agent_memory = MemorySaver()
        return create_react_agent(
            model=self.llm,
            tools=tools,
            checkpointer=react_agent_memory,
            prompt=system_prompt,
            debug=True
        )

    def _get_node_name(self, toolset_name: str) -> str:
        """Generate node name for a given toolset."""
        suffix = TOOLSET_TO_NODE_SUFFIX.get(toolset_name, "general")
        return f"{suffix}_agent_node"

    def _select_toolset(self, query_type: str) -> str:
        """Select the appropriate toolset based on query type."""
        return TOOLSETS.get(query_type, DEFAULT_TOOLSET)

    async def _router_node(self, state: AgentGraphState) -> Dict[str, str]:
        """Route queries to the appropriate agent node based on query type."""
        operator_query = state['operator_query']
        query_type = operator_query.query_type
        
        logger.info(f"Router: Determining route for query_type: {query_type}")
        
        # Determine toolset and route
        selected_toolset = self._select_toolset(query_type)
        route_destination = self._get_node_name(selected_toolset)
        
        logger.info(f"Router: Selected toolset '{selected_toolset}', routing to node '{route_destination}' for query_type '{query_type}'")
        return {"current_route": route_destination}

    async def _execute_agent_node(self, state: AgentGraphState, toolset_key: str) -> Dict[str, List[AIMessage]]:
        """Execute a specific agent node and return its response."""
        react_agent = self.agents.get(toolset_key)
        
        if not react_agent:
            error_msg = f"Critical failure: Agent for toolset {toolset_key} not found or could not be initialized."
            logger.error(error_msg)
            return {"messages": [AIMessage(content=error_msg)]}
        
        try:
            # Prepare execution context
            operator_query = state['operator_query']
            thread_id = f"react_agent_thread_{operator_query.operator_id}_{toolset_key}"
            config = {"configurable": {"thread_id": thread_id}}
            inputs = {"messages": state['messages']}
            
            # Execute agent
            response = await react_agent.ainvoke(inputs, config=config)
            
            # Extract and return response
            ai_message_content = self._extract_response_content(response)
            logger.info(f"Agent Node ({toolset_key}): Response: {ai_message_content[:100]}...")
            
            return {"messages": [AIMessage(content=ai_message_content)]}
        
        except Exception as e:
            error_msg = f"Error executing agent for toolset {toolset_key}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"messages": [AIMessage(content=error_msg)]}

    def _extract_response_content(self, response: Dict[str, Any]) -> str:
        """Extract content from agent response."""
        if response and "messages" in response and response["messages"]:
            final_message = response["messages"][-1]
            return getattr(final_message, 'content', str(final_message))
        return "Could not extract response."

    def _create_agent_node_method(self, toolset_key: str) -> Callable:
        """Create an agent node method for a specific toolset."""
        async def agent_node_method(state: AgentGraphState):
            return await self._execute_agent_node(state, toolset_key)
        return agent_node_method

    def _build_graph(self) -> Any:
        """Build the LangGraph workflow."""
        workflow = StateGraph(AgentGraphState)
        
        # Add router node
        workflow.add_node("router", self._router_node)
        
        # Add agent nodes dynamically
        node_names = []
        for toolset_key, toolset_name in TOOLSETS.items():
            node_name = self._get_node_name(toolset_name)
            node_method = self._create_agent_node_method(toolset_key)
            
            workflow.add_node(node_name, node_method)
            workflow.add_edge(node_name, END)
            node_names.append(node_name)
        
        # Set entry point and routing
        workflow.set_entry_point("router")
        
        # Add conditional edges from router
        conditional_path_map = {node_name: node_name for node_name in node_names}
        workflow.add_conditional_edges(
            "router",
            lambda state: state["current_route"],
            conditional_path_map
        )
        
        return workflow.compile(checkpointer=self.checkpointer, debug=True)

    async def process_query(self, operator_query: OperatorQuery) -> AIResponse:
        """
        Process an operator query and return AI response.
        
        Args:
            operator_query: The operator query to process
            
        Returns:
            AIResponse: The agent's response
        """
        logger.info(f"Processing query_id: {operator_query.query_id} with text: {operator_query.query_text}")
        
        try:
            # Prepare initial state
            initial_state = AgentGraphState(
                messages=[HumanMessage(content=operator_query.query_text)],
                operator_query=operator_query,
                current_route=""
            )
            
            # Execute graph
            thread_id = f"graph_thread_{operator_query.operator_id}_{uuid.uuid4()}"
            config = {"configurable": {"thread_id": thread_id}}
            final_state = await self.graph.ainvoke(initial_state, config=config)
            
            # Extract and return response
            response_text = self._extract_final_response(final_state)
            
            logger.info(f"Successfully processed query {operator_query.query_id}. Response: {response_text[:100]}...")
            
            return AIResponse(
                response_id=str(uuid.uuid4()),
                query_id=operator_query.query_id,
                response_text=response_text,
            )
            
        except Exception as e:
            logger.error(f"Error processing query '{operator_query.query_id}': {e}", exc_info=True)
            return self._create_error_response(operator_query, str(e))

    def _extract_final_response(self, final_state: Dict[str, Any]) -> str:
        """Extract the final response text from the graph execution state."""
        if final_state and final_state.get("messages"):
            final_message = final_state["messages"][-1]
            return getattr(final_message, 'content', str(final_message))
        return "Error: No response from AI."

    def _create_error_response(self, operator_query: OperatorQuery, error_message: str) -> AIResponse:
        """Create an error response for failed queries."""
        return AIResponse(
            response_id=str(uuid.uuid4()),
            query_id=operator_query.query_id,
            response_text=f"I apologize, but I encountered an error while processing your query: {error_message}. "
                         f"Please try rephrasing your question or contact technical support if the issue persists.",
        )


def create_manufacturing_agent(
    cluster: Cluster,
    checkpointer: AsyncCouchbaseSaver,
    toolbox_url: str = "http://127.0.0.1:5000"
) -> EnhancedManufacturingAgent:
    """
    Factory function to create an EnhancedManufacturingAgent.
    
    Args:
        cluster: Couchbase cluster instance
        checkpointer: AsyncCouchbaseSaver for state persistence
        toolbox_url: URL for the toolbox service
        
    Returns:
        EnhancedManufacturingAgent: Configured agent instance
    """
    return EnhancedManufacturingAgent(
        toolbox_url=toolbox_url, 
        cluster=cluster, 
        checkpointer=checkpointer
    ) 