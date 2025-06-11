from pydantic import BaseModel


class QueryRequest(BaseModel):
    user_input: str
    chat_session_id: str
    selected_line: str
    machine_id: str
    query_type: str


class QueryResponse(BaseModel):
    response_text: str 