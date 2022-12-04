# ChatGPT Telegram Bot in AWS Lambda

This a Telegram bot that lets you chat with [ChatGPT](https://openai.com/blog/chatgpt/). This bot is created using reverse engineering from the ChatGPT internal backend request to use the internal API endpoint. The Telegram bot is deployed in completely serverless in AWS Lambda. No need to setup a local server or do login in the browser.

# Initial Setup

1. Create an [OpenAI account](https://openai.com/api/).
2. Create an [AWS account](https://aws.amazon.com/es/).
3. Setup your Telegram bot. You can follow [this instructions](https://core.telegram.org/bots/tutorial#obtain-your-bot-token) to get your token.
4. Get your internal session token for ChatGPT:
- For this go to [ChatGPT](https://chat.openai.com/chat)
- Press F12, click on `session` and copy the contents of `accessToken`.
5. Go to `.chalice/config.json` and stablish the value of `TELEGRAM_TOKEN` with your Telegram token. Also stablish `CHATGPT_TOKEN` with the value of your ChatGPT Token.

# Installation

1. Install Python using [pyenv](https://github.com/pyenv/pyenv-installer) or your prefered Python installation.
2. Create a virtual environment: `python3 -m venv .venv`.
3. Activate you virtual environment: `source .venv/bin/activate`.
3. Install dependencies: `pip install -r requirements.txt`.
4. [Install the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) and [configure your credentials](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html).

# Deployment

1. Run `chalice deploy`.
2. Go to the AWS Console -> Lambda -> <your_function_name> -> Configuration -> Function URL.
3. Click Create Function URL and set Auth type to NONE.
4. Copy the created function URL.
5. Stablish your Telegram webhook to point to you AWS Lambda running `curl --request POST --url https://api.telegram.org/<YOUR_TELEGRAM_TOKEN>/setWebhook --header 'content-type: application/json' --data '{"url": "<YOUR_FUNCTION_URL"}'`

Great! Everything is setup :) Now go to Telegram and find your bot name and use ChatGPT from there!

# Cooming Features
- [ ] Markdown rendering in Telegram.
- [ ] Automatic ChatGPT token rotation.
- [ ] Much more!

# Credits

-  [ChatGPT Telegram Bot - @altryne
](https://github.com/altryne/chatGPT-telegram-bot)
- [whatsapp-gpt](https://github.com/danielgross/whatsapp-gpt)
- [ChatGPT Reverse Engineered API](https://github.com/acheong08/ChatGPT)