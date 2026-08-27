"""Financial reports & analytics service."""
from datetime import datetime
from decimal import Decimal
from typing import List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.transaction import TransactionType
from app.database.repositories.category_repo import CategoryRepository
from app.database.repositories.transaction_repo import TransactionRepository
from app.schemas.report import CategorySummary, FinancialReport
from app.services.base import BaseService


class ReportService(BaseService):
    """Business service for generating financial summaries and reports."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.tx_repo = TransactionRepository(session)
        self.cat_repo = CategoryRepository(session)

    async def get_period_report(
        self,
        user_id: int,
        start_date: datetime,
        end_date: datetime,
    ) -> FinancialReport:
        """Generate financial statement for a custom date period."""
        summary = await self.tx_repo.get_summary(user_id, start_date, end_date)
        income = summary.get("income", Decimal("0"))
        expense = summary.get("expense", Decimal("0"))
        net_profit = summary.get("profit", Decimal("0"))
        margin = float(summary.get("margin", Decimal("0")))

        income_cats_raw = await self.tx_repo.get_by_category(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            transaction_type=TransactionType.INCOME,
        )
        expense_cats_raw = await self.tx_repo.get_by_category(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            transaction_type=TransactionType.EXPENSE,
        )

        def map_breakdown(raw_rows: List[Tuple], total: Decimal) -> List[CategorySummary]:
            result = []
            for row in raw_rows:
                # row is (name, icon, total, count)
                cat_name = row[0] or "Boshqa"
                cat_icon = row[1] or "📁"
                amt = row[2] or Decimal("0")
                cnt = row[3] or 0
                pct = float((amt / total) * 100) if total > Decimal("0") else 0.0
                result.append(
                    CategorySummary(
                        category_name=cat_name,
                        category_icon=cat_icon,
                        total_amount=amt,
                        percentage=round(pct, 1),
                        transaction_count=cnt,
                    )
                )
            return result

        return FinancialReport(
            total_income=income,
            total_expense=expense,
            net_profit=net_profit,
            profit_margin_percent=round(margin, 2),
            top_income_categories=map_breakdown(income_cats_raw, income),
            top_expense_categories=map_breakdown(expense_cats_raw, expense),
            start_date=start_date,
            end_date=end_date,
        )
