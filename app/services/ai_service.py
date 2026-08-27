"""AI business assistant service for financial insights."""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.report import FinancialReport
from app.services.base import BaseService


class AIService(BaseService):
    """AI Assistant providing intelligent financial tips and natural language analysis."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def generate_financial_advice(
        self,
        report: FinancialReport,
        business_name: Optional[str] = None,
    ) -> str:
        """Generate structured AI recommendations based on financial performance."""
        biz = business_name or "Biznesingiz"
        advice = [
            f"📊 <b>{biz} uchun moliyaviy tahlil va tavsiyalar:</b>\n",
            f"• Jami daromad: <b>{report.total_income:,.2f} UZS</b>",
            f"• Jami xarajat: <b>{report.total_expense:,.2f} UZS</b>",
            f"• Sof foyda: <b>{report.net_profit:,.2f} UZS</b> (Rentabellik: {report.profit_margin_percent}%)\n",
        ]

        if report.profit_margin_percent < 15:
            advice.append("⚠️ <i>Rentabellik darajasi past. Xarajatlar strukturasini qayta ko'rib chiqish tavsiya etiladi.</i>")
        else:
            advice.append("✅ <i>Rentabellik me'yorda. Aylanma mablag'larni ko'paytirishga e'tibor qarating.</i>")

        return "\n".join(advice)
