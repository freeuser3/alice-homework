import asyncio

import pytest

from alice_skill.quiz_state import QuizSlot


async def _finish_now(slot, subject, question):
    slot.finish(subject, question)


@pytest.mark.asyncio
async def test_set_pending_and_finish():
    slot = QuizSlot()
    task = asyncio.create_task(_finish_now(slot, "География", "Какой газопровод важнее?"))
    slot.set_pending(subject="География", paragraph=6, task=task)
    assert slot.task is task
    assert slot.has_pending is True
    await task  # внутри task'а: slot.task is current_task → вопрос записывается
    assert slot.question == "Какой газопровод важнее?"
    assert slot.has_pending is True


@pytest.mark.asyncio
async def test_finish_ignores_stale_task():
    slot = QuizSlot()
    old_task = asyncio.create_task(_finish_now(slot, "География", "старый вопрос"))
    slot.set_pending(subject="География", paragraph=6, task=old_task)
    # «протухший» фоновый таск заканчивается, а слот уже переключён на новый — вызов из теста
    # не совпадает с slot.task (current_task — корутина теста), вопрос должен игнорироваться
    new_task = asyncio.create_task(asyncio.sleep(0))
    slot.set_pending(subject="Биология", paragraph=3, task=new_task)
    assert slot.paragraph == 3
    old_task.cancel()
    await asyncio.sleep(0)  # даём старому таску «упасть»
    slot.finish("География", "старый вопрос")
    assert slot.question is None
    assert slot.subject == "Биология"
    await new_task


def test_clear_resets_all():
    slot = QuizSlot()
    slot.subject = "География"
    slot.paragraph = 6
    slot.question = "Вопрос"
    slot.clear()
    assert slot.subject is None
    assert slot.paragraph is None
    assert slot.question is None
    assert slot.task is None
    assert slot.has_pending is False


def test_slot_paragraph_is_str():
    from unittest.mock import MagicMock
    slot = QuizSlot()
    slot.set_pending("ОБЗР", "6.1", MagicMock())
    assert slot.paragraph == "6.1"