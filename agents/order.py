from .base import AgentBase, AgentContext, AgentOutput, Ask, Commit
from core.states import OrderState

class OrderAgent(AgentBase):
    def __init__(self, tools, llm, cfg):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    async def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ws = ctx.workstream
        entities = ctx.nlu_result["current_turn"].get("entities", {})
        ws.update_slots(entities)

        # Step 1: Need a product_id
        if "product_id" not in ws.slots:
            ws.status = OrderState.COLLECTING
            return AgentOutput(action=Ask("Which product would you like to order?"))

        # Step 2: Place order (simulate tool call)
        ws.status = OrderState.CONFIRMING
        result = await self.tools.call("place_order", {"product_id": ws.slots["product_id"]})

        ws.status = OrderState.COMPLETED
        return AgentOutput(action=Commit(result), mark_completed=True)
