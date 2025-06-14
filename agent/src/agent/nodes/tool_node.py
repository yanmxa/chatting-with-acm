"""
A LangGraph implementation of the human-in-the-loop agent.
"""

import json
from typing import Dict, List, Any

# LangGraph imports
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END, START
from langgraph.types import Command, interrupt
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

# CopilotKit imports
from copilotkit import CopilotKitState
from copilotkit.langgraph import copilotkit_customize_config, copilotkit_emit_state, copilotkit_interrupt,copilotkit_exit

# LLM imports
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from .agent_state import AgentState, ActionState
from .agent_state import tool_data  # shared globals

from dotenv import load_dotenv
load_dotenv()

async def ToolNode(state: AgentState, config: RunnableConfig):
    print(f"========================== tool node start: {config["metadata"]["thread_id"]}===================== \n")
    print(state)
        
    state["progress"]["label"] = "Tool Node is tarting."    
    state["progress"]["value"] = 10
    await copilotkit_emit_state(config, state)
    
    messages = state.get("messages", [])

    response = messages[-1]
    if state.get("actions") is None:
        state["actions"] = []
    action: ActionState = {}
    # Handle tool calls
    if hasattr(response, "tool_calls") and response.tool_calls and len(response.tool_calls) > 0:
        tool_call = response.tool_calls[0]
        # Extract tool call information
        if hasattr(tool_call, "id"):
            tool_call_id = tool_call.id
            tool_call_name = tool_call.name
            tool_call_args = tool_call.args if not isinstance(tool_call.args, str) else json.loads(tool_call.args)
        else:
            tool_call_id = tool_call.get("id", "")
            tool_call_name = tool_call.get("name", "")
            args = tool_call.get("args", {})
            tool_call_args = args if not isinstance(args, str) else json.loads(args)
        # action
        action["name"] = tool_call_name
        action["args"] = tool_call_args
        action["status"] = "pending"
        action["approval"] = "y"
        state["actions"].append(action)
        # progress
        state["progress"]["label"] = f"Tool Node '{tool_call_name}' is invoking..."
        state["progress"]["value"] = 40
        await copilotkit_emit_state(config, state)
        
        # print("------------")
        # print()
        # print(state)
        # print()
        # print("-------------")
        
        # update action
        tool_call_message = ToolMessage(tool_call_id=tool_call_id, name=tool_call_name, content=f"{tool_call_name}: {tool_call_args} is not allowed to perform into the current system")
        if action["approval"] == "y":
            print(tool_data)
            selected_tool = tool_data.tool_map[tool_call_name]
            tool_output = await selected_tool.ainvoke(tool_call_args)
            action["status"] = "completed"
            action["output"] = tool_output
            tool_call_message = ToolMessage(tool_call_id=tool_call_id, name=tool_call_name, content=f"{tool_output}")
       
        # update message
        messages = state["messages"] + [tool_call_message]
   
        # update progress
        state["progress"]["label"] = f"Tool Node '{tool_call_name}' has returned a result."
        state["progress"]["value"] = 100
        await copilotkit_emit_state(config, state)
        
        print(f"agent action state: {state['actions']} \n")
        print(f"tool call end: {state['messages']} \n")
        
        print(f"--- tool node end ----")

        return {
            **state,
            "messages": messages,
        }
    # await copilotkit_exit(config)
    # return Command(
    #     goto=END,
    #     update={
    #         "messages": messages,
    #         "update": state["update"],
    #     }
    # )