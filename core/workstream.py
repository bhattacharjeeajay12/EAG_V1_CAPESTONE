# core/workstream.py
from dataclasses import dataclass, field
from typing import Dict, Any, Union, List
from config.enums import WorkstreamState
from core.fsm_engine import FSMEngine
from core.fsm_rules import PHASE_TRANSITIONS, WS_TRANSITIONS
from config.enums import Agents, ChatInfo
from core.PlanGenerator import PlanGenerator
from agents.DiscoveryAgent import DiscoveryAgent
import uuid
from nlu.discovery_nlu import DiscoveryNLU
from agents.QueryAgent import QueryAgent # QueryBuilder
from agents.SummarizerAgent import SummarizerAgent
from core.QueryExecutor import QueryExecutorSimple
from config.utils import get_specification_list
from pathlib import Path

class Workstream:
    def __init__(self, phase, target: Dict[str, Any], id: str):
        self.id: str = id
        self.current_state: Union[WorkstreamState, str] = WorkstreamState.NEW
        self.current_phase: str = phase
        self.first_phase: Union[Agents, str] = phase
        self.target: Dict[str, Any] = target

        self.chats: List[Dict[str, Any]] = []
        self.processing: Dict[str, Any] = {}
        self.all_phases: Dict[str, Any] = {}
        self.consolidated_entities: List[Dict[str, Any]] = []

        # Correct instance initialization
        self.fsm: FSMEngine = FSMEngine(WS_TRANSITIONS)
        self.discoveryPlanGenerator: PlanGenerator = PlanGenerator(type=phase)
        self.discoveryNer: DiscoveryAgent = DiscoveryAgent(
            subcategory=target.get("subcategory") if target else None
        )

        self.specification_list: List[Dict[str, Any]] = get_specification_list(
            subcategory=target.get("subcategory")
        )
        self.specification_Ask: bool = True
        self.last_query_result: Dict[str, Any] | None = None


    def get_workstream_id(self):
        return self.id

    def get_state(self):
        return self.current_state

    def get_phase(self):
        return self.current_phase

    def get_target_entity(self):
        return self.target
    def get_chats(self):
        return self.chats

    def add_chat_in_ws(self, msg_type: str, message: Any) -> bool:
        """
        A sample chats looks like this:
        chats = [
                    {chat_id, user_message, ai_message, processed = [{}, {}, {}]},
                    {chat_id, user_message, ai_message, processed = [{}, {}, {}]},
                    ...
        ]
        """
        if msg_type == ChatInfo.user_message.value:
            # chats = self.workstreams[ws_id].chats
            chat_obj = {
                            ChatInfo.chat_id.value: uuid.uuid4(),
                            ChatInfo.user_message.value: message,
                            ChatInfo.ai_message.value: None,
                            ChatInfo.processed.value: []}
            self.chats.append(chat_obj)
            return True

        elif msg_type == ChatInfo.ai_message.value:
            # chats = self.workstreams[ws_id].chats
            if not self.chats:
                raise Exception("Cannot add AI message before a user message")
            if ChatInfo.user_message.value not in self.chats[-1].keys():
                raise Exception("Cannot add AI message before a user message")
            if ChatInfo.ai_message.value in self.chats[-1].keys():
                if self.chats[-1][ChatInfo.ai_message.value] is None:
                    self.chats[-1][ChatInfo.ai_message.value] = message
                return True
        elif msg_type == ChatInfo.processed.value:
            if not self.chats:
                raise Exception("Cannot add processed information before a user message")
            if ChatInfo.processed.value in self.chats[-1].keys():
                self.chats[-1][ChatInfo.processed.value].append(message)
                return True
        return False
    def update_status(self, target_state: Union[WorkstreamState, str]) -> bool:
        """
        Attempt to transition state using the FSM.
        Returns True on success, raises ValueError on invalid transition.
        """

        if self.fsm.can_transition(self.current_state, target_state):
            # preserve original type if it's an Enum, else keep string
            self.current_state = target_state
            return True
        else:
            raise ValueError(f"Invalid transition: {self.current_state} → {target_state}")

    async def get_preplan(self, user_query: str) -> str|None:
        d_output = await self.discoveryNer.run(user_query, self.specification_list, self.specification_Ask)
        self.specification_Ask = False  # Only it will ask for specs once.
        if type(d_output) == str:  # AI response
            self.add_chat_in_ws(ChatInfo.ai_message.value, d_output)
            return d_output
        return None

    async def run(self, user_query: str) -> str|None:

        if self.first_phase == Agents.DISCOVERY:
            self.add_chat_in_ws(ChatInfo.user_message.value, user_query)

            #pre plan stuff
            if self.specification_Ask:
                d_output = await self.get_preplan(user_query)
                if d_output is not None:
                    return d_output
                else:
                    raise Exception("While generating exception error occurred in preplan")

            # generate the plan
            plan = await self.discoveryPlanGenerator.run(user_query, self.chats)
            steps = plan.get("plan", [])
            print(f"steps: {steps}")
            # execute the plan
            for step in steps:
                if step["name"] == "ENTITY_EXTRACTION":
                    spec_nlu = DiscoveryNLU(self.target.get("subcategory"), self.specification_list)
                    spec_nlu_response = await spec_nlu.run(user_query)
                    processed_data = {"process_name": "ENTITY_EXTRACTION",
                                      "output_type": List[Dict[str, Any]],
                                      "output": spec_nlu_response}
                    self.add_chat_in_ws(ChatInfo.processed.value, processed_data)
                if step["name"] == "QUERY_BUILDER_EXECUTOR":
                    # Query Builder
                    query_agent = QueryAgent()
                    query_llm_output = await query_agent.run(current_query=user_query,
                                                       consolidated_entities=self.consolidated_entities,
                                                       specification_list=self.specification_list,
                                                       chats=self.chats,
                                                       subcategory=self.target.get("subcategory"))
                    pandas_query = query_llm_output.get("pandas_query")

                    # Query Executor
                    # TODO: Below should be from env
                    from pathlib import Path
                    DB_DIR = Path(__file__).resolve().parent.parent / "db"
                    REQUIRED_FILES = ["product.json", "specification.json"]
                    for filename in REQUIRED_FILES:
                        path = DB_DIR / filename
                        if not path.exists():
                            raise FileNotFoundError(f"Required data file missing: {path}")
                    
                    executor = QueryExecutorSimple(pandas_query, data_dir=str(DB_DIR))
                    df_result = await executor.execute()

                    if df_result is not None:
                        print("Result shape:", df_result.shape)
                        print(df_result)
                        result_payload = {
                            "process_name": "QUERY_RESULT",
                            "output_type": "DataFrame",
                            "row_count": len(df_result),
                            "columns": list(df_result.columns),
                            "preview": df_result.to_string(index=False),
                        }
                        self.last_query_result = result_payload
                        self.add_chat_in_ws(ChatInfo.processed.value, result_payload)

                if step["name"] == "SUMMARIZER":
                    # Summarization and follow up
                    summarizer = SummarizerAgent()
                    summary_response = await summarizer.run(
                        current_query=user_query,
                        chats=self.chats,
                        query_result=self.last_query_result,
                    )
                    if summary_response:
                        self.add_chat_in_ws(ChatInfo.ai_message.value, summary_response)
                        return summary_response

        # if self.current_phase == Agents.DISCOVERY:
        #     self.add_chat_in_ws(ChatInfo.user_message.value, user_query)
        #     subcategory = self.target.get("subcategory")
        #     if self.current_phase not in self.all_phases:
        #         discovery_phase = DiscoveryAgent(subcategory=subcategory)
        #         self.all_phases[self.current_phase] = discovery_phase
        #     discovery_phase = self.all_phases.get(self.current_phase)
        #
        #     # Step 1. Gather specification using Discovery NLU
        #     d_output = await discovery_phase.run(user_query, self.specification_list, self.specification_Ask)
        #     self.specification_Ask = False  # Only it will ask for specs once.
        #     if type(d_output) == str: # AI response
        #         self.add_chat_in_ws(ChatInfo.ai_message.value, d_output)
        #         return d_output
        #     else:
        #         # Step 1. Gather specification using Discovery NLU
        #         pass
        return None
        