from ConversationSummaryMemory import build_summarymemory
from ConversationBufferMemory import build_buffermemory

memory_map = {
    "conversation_summary_memory": build_summarymemory,
    "conversation_buffer_memory": build_buffermemory,
}