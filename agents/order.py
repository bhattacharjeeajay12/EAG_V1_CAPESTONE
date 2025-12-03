from typing import Dict, Any
from agents.base import AgentBase, AgentContext, AgentOutput, Ask, Info, Confirm
from tools.registry_old import ToolRegistry
from typing import Dict, Optional, Any
from core.llm_client import LLMClient
from config.planner_config import PlannerConfig

class OrderAgent(AgentBase):
    def __init__(self,
        tools: Optional[ToolRegistry] = None,
        llm: Optional[LLMClient] = None,
        cfg: PlannerConfig = PlannerConfig()):

        super().__init__()
        self.tools = tools   # <-- inject ToolRegistry
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    async def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ws = ctx.workstream
        product_id = ws.slots.get("product_id")
        if not product_id:
            return AgentOutput(
                action=Ask(question="Which product would you like to buy? Provide a product id.", slot="product_id")
            )

        try:
            resp = await self.tools.call("place_order", {"product_id": product_id})
            msg = f"Order confirmed (ID: {resp.get('order_id')})."
            return AgentOutput(
                action=Confirm(text=msg),
                updated_slots={"order_id": resp.get("order_id")},
                mark_completed=True,
            )
        except Exception as e:
            return AgentOutput(action=Info(message=f"Failed to place order: {e}"))
