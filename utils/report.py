from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from users.models import get_engine, get_session, Draw, Feedback, Pair


async def generate_report_file() -> BytesIO:
    engine = get_engine()
    async with get_session(engine) as session:
        stmt = (
            select(Draw)
            .options(
                selectinload(Draw.pairs).selectinload(Pair.participant1),
                selectinload(Draw.pairs).selectinload(Pair.participant2),
                selectinload(Draw.pairs).selectinload(Pair.participant3),
                selectinload(Draw.feedbacks).selectinload(Feedback.participant),
            )
            .order_by(Draw.draw_date)
        )
        result = await session.execute(stmt)
        draws = result.scalars().all()

        wb = Workbook()
        ws = wb.active
        ws.title = "Отчет по встречам"

        headers = [
            "Дата жеребьевки", "Участник 1", "Участник 2", "Участник 3",
            "Встреча состоялась (1)", "Комментарий (1)", "Позитив (1)", "Отзыв (1)",
            "Встреча состоялась (2)", "Комментарий (2)", "Позитив (2)", "Отзыв (2)",
            "Встреча состоялась (3)", "Комментарий (3)", "Позитив (3)", "Отзыв (3)",
        ]
        ws.append(headers)

        for draw in draws:
            for pair in draw.pairs:
                participants = [pair.participant1, pair.participant2]
                participants.append(pair.participant3 if pair.participant3 else None)

                feedback_map = {fb.participant_id: fb for fb in draw.feedbacks}

                row = [
                    draw.draw_date.strftime("%Y-%m-%d"),
                    *(p.name if p else "" for p in participants),
                ]

                for p in participants:
                    if p:
                        fb = feedback_map.get(p.id)
                        if fb:
                            row.append("Да" if fb.success else "Нет" if fb.success is False else "")
                            row.append(fb.skip_reason or "")
                            row.append("Да" if fb.rating else "Нет" if fb.rating is False else "")
                            row.append(fb.comment or "")
                        else:
                            row.extend(["", "", "", ""])
                    else:
                        row.extend(["", "", "", ""])

                ws.append(row)

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer
