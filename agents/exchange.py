
from agents.base import AgentBase, AgentContext, AgentOutput, Ask, Info
class ExchangeAgent(AgentBase):
    async def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ws = ctx.workstream
        order_id = ws.slots.get("order_id")
        if not order_id:
            return AgentOutput(action=Ask(question="What's the order ID you want to exchange?", slot="order_id"))
        try:
            resp = await self.tools.call("Exchanges.check_eligibility", {"order_id": order_id})
            if resp.get("eligible"):
                return AgentOutput(action=Info(message="Exchange eligible. I can proceed with the request."), mark_completed=True)
            return AgentOutput(action=Info(message=f"Exchange not eligible: {resp.get('reason','unknown')}"))
        except Exception as e:
            return AgentOutput(action=Info(message=f"Exchange check failed: {e}"))
