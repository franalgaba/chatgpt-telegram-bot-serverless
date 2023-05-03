from unittest.mock import MagicMock, patch

import pytest

from app import process_message


def mock_update(chat_id, chat_text):
    update = MagicMock()
    update.message.chat_id = chat_id
    update.message.text = chat_text
    return update


def mock_context():
    context = MagicMock()
    return context


@pytest.mark.parametrize("chat_id, chat_text", [(1234, "/clear"), (5678, "Hello")])
def test_process_message_normal(chat_id, chat_text):
    update = mock_update(chat_id, chat_text)
    context = mock_context()

    with patch(
        "app.AIService.orchestrate_message", return_value="Mocked response"
    ) as orchestratemock, patch(
        "app.MessageService.clear_chat_history", return_value=None
    ) as clearmock:
        process_message(update, context)

    if chat_text == "/clear":
        clearmock.assert_called_once_with(chat_id)
        context.bot.send_message.assert_called_once_with(
            chat_id=chat_id,
            text="Chat cleared",
            parse_mode="Markdown",
        )
    else:
        orchestratemock.assert_called_once_with(chat_id, chat_text)
        context.bot.send_message.assert_called_once_with(
            chat_id=chat_id,
            text="Mocked response",
            parse_mode="Markdown",
        )


def test_process_message_exception():
    chat_id = 1234
    chat_text = "Hello"
    update = mock_update(chat_id, chat_text)
    context = mock_context()

    with patch(
        "app.AIService.orchestrate_message", side_effect=Exception("Test exception")
    ), patch("app.TelegramService.send_chat_message") as send_err_mock:
        process_message(update, context)

    send_err_mock.assert_called_once_with(
        chat_id,
        "There was an error handling your message :( Test exception",
    )
