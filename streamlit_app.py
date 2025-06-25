import streamlit as st
import logging
import uuid
from datetime import datetime
import httpx

# Configuration
API_URL = "http://127.0.0.1:8000"
DEFAULT_TOOLBOX_URL = "http://127.0.0.1:5000"
REQUEST_TIMEOUT = 120.0

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="CPG Manufacturing AI Assistant",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


def load_custom_css():
    """Load custom CSS styles for the application."""
    st.markdown("""
    <style>
        .main-header {
            font-size: 2.5rem;
            color: #1f77b4;
            text-align: center;
            margin-bottom: 1rem;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
        }
        .system-status {
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 10px;
            border-radius: 8px;
            margin: 10px 0;
            font-weight: bold;
            font-size: 0.9em;
        }
        .system-online {
            background-color: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .system-offline {
            background-color: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .agent-info {
            background: linear-gradient(135deg, #f8f9fa, #e9ecef);
            padding: 1rem;
            border-radius: 10px;
            margin: 10px 0;
            border-left: 4px solid #6c757d;
            font-size: 0.9em;
        }
    </style>
    """, unsafe_allow_html=True)


@st.cache_data(ttl=60)
def get_system_status():
    """Check the backend API status with caching."""
    try:
        response = httpx.get(f"{API_URL}/status", timeout=10.0)
        response.raise_for_status()
        return response.json().get("system_online", False)
    except httpx.RequestError as e:
        logger.error(f"Failed to connect to backend API: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking system status: {e}")
        return False


def get_agent_descriptions():
    """Get descriptions for all agent types."""
    return {
        "general": "🤖 **General Agent** - Comprehensive manufacturing support",
        "troubleshooting": "🔧 **Troubleshooting Agent** - Error resolution specialist",
        "monitoring": "📊 **Monitoring Agent** - Production metrics expert",
        "maintenance": "🛠️ **Maintenance Agent** - Maintenance planning specialist"
    }


def get_agent_intro_messages():
    """Get intro messages for all agent types."""
    return {
        "general": "👋 Hello! I'm your CPG Manufacturing AI Assistant. I'm here to help with troubleshooting, maintenance, production monitoring, and general manufacturing questions. How can I assist you today?",
        "troubleshooting": "👋 Switched to **Troubleshooting Agent**. This chat is now focused on resolving issues. Please describe the problem.",
        "monitoring": "👋 Switched to **Monitoring Agent**. This chat is now focused on production metrics. What would you like to see?",
        "maintenance": "👋 Switched to **Maintenance Agent**. This chat is now focused on maintenance tasks. How can I assist?"
    }


def display_system_status(system_online):
    """Display system status with appropriate styling."""
    status_class = "system-online" if system_online else "system-offline"
    status_icon = "🟢" if system_online else "🔴"
    status_text = "AI Assistant Online & Ready" if system_online else "API Backend Offline - Limited Functionality"
    
    st.markdown(f"""
    <div class="system-status {status_class}">
        {status_icon} {status_text}
    </div>
    """, unsafe_allow_html=True)


def initialize_chat():
    """Initialize chat session with default values."""
    if "messages" not in st.session_state:
        intro_messages = get_agent_intro_messages()
        st.session_state.messages = [{
            "role": "assistant",
            "content": intro_messages["general"],
            "timestamp": datetime.now(),
            "agent_type": "general"
        }]

    if "chat_session_id" not in st.session_state:
        st.session_state.chat_session_id = str(uuid.uuid4())


def add_message(role: str, content: str, agent_type: str = "general"):
    """Add a message to the chat history."""
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "timestamp": datetime.now(),
        "agent_type": agent_type
    })


def clear_chat():
    """Clear chat history while retaining current agent context."""
    agent_type = st.session_state.get("agent_type_selector", "general")
    intro_messages = get_agent_intro_messages()
    
    clear_message = intro_messages.get(agent_type, intro_messages["general"]).replace(
        "Hello!", "Chat cleared!"
    ).replace("Switched to", "Chat cleared! Staying with")
    
    st.session_state.messages = [{
        "role": "assistant",
        "content": clear_message,
        "timestamp": datetime.now(),
        "agent_type": agent_type
    }]
    st.session_state.chat_session_id = str(uuid.uuid4())


def reset_chat_for_new_agent():
    """Reset chat when a new agent is selected."""
    agent_type = st.session_state.agent_type_selector
    intro_messages = get_agent_intro_messages()
    
    st.session_state.messages = [{
        "role": "assistant",
        "content": intro_messages.get(agent_type, intro_messages["general"]),
        "timestamp": datetime.now(),
        "agent_type": agent_type
    }]
    st.session_state.chat_session_id = str(uuid.uuid4())


def process_message_via_api(user_input: str, query_type: str):
    """Process user message by calling the backend API."""
    logger.info(f"chat_session_id: {st.session_state.chat_session_id}")
    payload = {
        "user_input": user_input,
        "chat_session_id": st.session_state.chat_session_id,
        "query_type": query_type
    }

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
            response = client.post(f"{API_URL}/process_query", json=payload)
            response.raise_for_status()
            return response.json()["response_text"]
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error occurred: {e.response.text}")
        return f"An error occurred communicating with the AI Agent: {e.response.text}"
    except httpx.RequestError as e:
        logger.error(f"Request error occurred: {e}")
        return "Could not connect to the AI Agent backend. Please ensure it's running."
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        return f"An unexpected error occurred: {str(e)}"


# display_chat_messages function removed - now integrated directly into render_chat_interface


def render_sidebar():
    """Render the sidebar with all controls and settings."""
    with st.sidebar:
        st.header("🔧 Chat Settings")

        # Agent selection
        agent_type_selection = st.selectbox(
            "🤖 AI Agent",
            ["general", "troubleshooting", "monitoring", "maintenance"],
            help="Choose your specialist",
            key="agent_type_selector",
            on_change=reset_chat_for_new_agent
        )

        # Display agent description
        agent_descriptions = get_agent_descriptions()
        st.markdown(f"""
        <div class="agent-info">
            {agent_descriptions.get(agent_type_selection, agent_descriptions["general"])}
        </div>
        """, unsafe_allow_html=True)

        # Advanced settings
        with st.expander("⚙️ Advanced Settings"):
            toolbox_url_selection = st.text_input(
                "GenAI Toolbox URL",
                value=DEFAULT_TOOLBOX_URL,
                key="toolbox_url_input"
            )

        st.divider()

        # Chat controls
        st.subheader("💬 Chat Controls")
        if st.button("🗑️ Clear Chat", use_container_width=True):
            clear_chat()
            st.rerun()

        # Export chat functionality
        if st.button("📄 Export Chat", use_container_width=True):
            chat_export = "\n".join([
                f"[{msg['timestamp'].strftime('%H:%M:%S')}] {msg['role'].title()}: {msg['content']}"
                for msg in st.session_state.messages
            ])
            st.download_button(
                "💾 Download Chat History",
                chat_export,
                file_name=f"chat_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain"
            )

        # Setup information
        with st.expander("📋 Setup Info"):
            st.write("""
            **First Time Setup:**
            1. Run backend: `uvicorn api:app --reload`
            2. Run frontend: `streamlit run streamlit_app.py`
            """)

        # Chat statistics
        st.metric("💬 Messages", len(st.session_state.messages))
        st.metric("🤖 Agent", agent_type_selection.title())

    return agent_type_selection


def render_chat_interface(system_online, agent_type):
    """Render the main chat interface."""
    col1, col2 = st.columns([4, 1])
    
    with col1:
        # Chat section
        st.subheader("💬 Continuous Manufacturing Support Chat")
        
        # Create a container for messages only
        messages_container = st.container()
        with messages_container:
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])

    # Move Quick Questions and input OUTSIDE the columns to prevent duplication
    st.write("💡 **Quick Questions:**")
    cols = st.columns(5)
    suggestions = [
        "What's the status of all machines?",
        "Help with temperature alert",
        "Show maintenance schedule",
        "Troubleshoot conveyor issue",
        "Production efficiency report"
    ]

    user_clicked_suggestion = None
    for i, suggestion in enumerate(suggestions):
        if cols[i].button(suggestion, key=f"suggest_{i}", use_container_width=True):
            user_clicked_suggestion = suggestion
            break

    # Chat input
    if user_input := st.chat_input("Ask about machines, troubleshooting, maintenance, or production..."):
        handle_user_input(user_input, system_online, agent_type)
    elif user_clicked_suggestion:
        handle_user_input(user_clicked_suggestion, system_online, agent_type)

    # System status in sidebar
    with col2:
        render_system_status_panel(system_online)


def handle_user_input(user_input, system_online, agent_type):
    """Handle user input and generate AI response."""
    add_message("user", user_input, agent_type)

    with st.spinner("🤖 AI is thinking..."):
        if system_online:
            ai_response = process_message_via_api(
                user_input,
                query_type=agent_type
            )
        else:
            ai_response = "The backend API is offline. Please start the API server to enable the AI assistant."
    
    add_message("assistant", ai_response, agent_type)
    st.rerun()  # Need this to immediately display the new messages


def render_system_status_panel(system_online):
    """Render the system status panel."""
    st.subheader("📊 System Status")
    status_indicator = "✅ Online" if system_online else "❌ Offline"
    ready_indicator = "✅ Ready" if system_online else "⚠️ Offline"
    
    st.write(f"🌐 API Backend: {status_indicator}")
    st.write(f"🤖 AI Agent: {ready_indicator}")
    st.write(f"🛠️ Toolbox: {ready_indicator}")


def main():
    """Main application entry point."""
    # Load custom CSS
    load_custom_css()
    
    # Header
    st.markdown('<h1 class="main-header">🤖 Manufacturing AI Chat Assistant</h1>', unsafe_allow_html=True)

    # Initialize application state
    system_online = get_system_status()
    initialize_chat()

    # Display system status
    display_system_status(system_online)

    # Render sidebar and get selected agent
    agent_type = render_sidebar()

    # Render main chat interface
    render_chat_interface(system_online, agent_type)


if __name__ == "__main__":
    main()
   