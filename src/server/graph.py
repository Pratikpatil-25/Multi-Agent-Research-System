from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from state import State
from components.nodes import (
    tool_node,
    search_node,
    route_scraping,
    single_scraper,
    writer_node,
    critic_node,
    extract_draft_node,
    human_review_node,        
    should_use_tool,
    should_stop_looping,
)


# create graph
graph = StateGraph(State)
graph.add_node("searcher", search_node)
graph.add_node("single_scraper", single_scraper)
graph.add_node("writer", writer_node)
graph.add_node("tools", tool_node)
graph.add_node("extract_draft", extract_draft_node)
graph.add_node("critic", critic_node)
graph.add_node("human_review", human_review_node)   # NEW

graph.add_edge(START, "searcher")
graph.add_conditional_edges("searcher", route_scraping, ["single_scraper"])
graph.add_edge("single_scraper", "writer")
graph.add_conditional_edges("writer", should_use_tool)

graph.add_edge("tools", "writer")
graph.add_edge("extract_draft", "critic")


graph.add_edge("critic", "human_review")


graph.add_conditional_edges("human_review", should_stop_looping)

checkpointer = MemorySaver()

app = graph.compile(checkpointer=checkpointer)

