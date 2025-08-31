from .base import AgentBase, AgentContext, AgentOutput, Ask, Commit

class OrderAgent(AgentBase):
    def __init__(self, tools, llm, cfg):
        self.tools = tools
        self.llm = llm
        self.cfg = cfg

    async def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ws = ctx.workstream
        entities = ctx.nlu_result["current_turn"].get("entities", {})
        ws.slots.update(entities)

        if "product_id" not in ws.slots:
            return AgentOutput(action=Ask("Which product would you like to order?"))

        ws.status = "completed"
        return AgentOutput(action=Commit({"order_id": "ord_456"}), mark_completed=True)
