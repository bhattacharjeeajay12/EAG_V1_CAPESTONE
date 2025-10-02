
from agents.base import AgentBase, AgentContext, AgentOutput, Ask, Info
class PaymentAgent(AgentBase):
    async def decide_next(self, ctx: AgentContext) -> AgentOutput:
        ws = ctx.workstream
        amount = ws.slots.get("amount")
        method = ws.slots.get("payment_method")
        if not method:
            return AgentOutput(action=Ask(question="Which payment method would you like to use?", slot="payment_method"))
        try:
            resp = await self.tools.call("Payments.charge", {"method": method, "amount": amount})
            ok = bool(resp.get("success", False))
            return AgentOutput(action=Info(message="Payment successful." if ok else "Payment failed."), mark_completed=ok)
        except Exception as e:
            return AgentOutput(action=Info(message=f"Payment error: {e}"))
