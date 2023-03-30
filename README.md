# ChatGPT Telegram Bot in AWS Lambda

This a Telegram bot that lets you chat with [ChatGPT](https://openai.com/blog/chatgpt/). This bot is created using the [__brand new ChatGPT API__](https://openai.com/blog/introducing-chatgpt-and-whisper-apis). The Telegram bot is deployed in completely serverless in AWS Lambda. No need to setup a local server or do login in the browser.

# Features

- [X] __New ChatGPT API support.__ :brain:
- [X] __Voice messages support!__ :fire:
- [X] __Markdown rendering support.__

<p align="center">
    <img src="./img/chatgpt_animation_fast.gif" width="500"/>
</p>

# Initial Setup

1. Create an [OpenAI account](https://openai.com/api/) and [get an API Key](https://platform.openai.com/account/api-keys).
2. Create an [AWS account](https://aws.amazon.com/es/).
3. Setup your Telegram bot. You can follow [this instructions](https://core.telegram.org/bots/tutorial#obtain-your-bot-token) to get your token.
4. Get your internal session token for ChatGPT:
- For this go to [ChatGPT](https://chat.openai.com/chat)
- Press F12, click on `session` and copy the contents of `__Secure-next-auth.session-token`.

<details>
[<img src="./img/session_token.png" width="500"/>](/img/session_token.png)
</details>

5. To enable support for voice messages you need to create a S3 bucket in your AWS account.
- Go to the top search bar and write `S3`.

<details>
[<img src="./img/s3_browser.png" width="500"/>](/img/s3_browser.png)
</details>

- Click the Create Bucket button.

<details>
[<img src="./img/create_bucket_button.png" width="500"/>](/img/create_bucket_button.png)
</details>

- Configure the creation of your bucket. The name must be unique worldwide. Scroll to bottom and click Create Bucket and don't change any other configuration.

<details>
[<img src="./img/create_bucket_config.png" width="500"/>](/img/create_bucket_config.png)
</details>

6. Go to `.chalice/config.json` and stablish the configurations:
- `TELEGRAM_TOKEN` with your Telegram token. 
- `OPENAI_API_KEY` with the value of your Open AI API Token.
- `VOICE_MESSAGES_BUCKET` with the bucket name you created previously.

# Installation

1. Install Python using [pyenv](https://github.com/pyenv/pyenv-installer) or your prefered Python installation.
2. Create a virtual environment: `python3 -m venv .venv`.
3. Activate you virtual environment: `source .venv/bin/activate`.
3. Install dependencies: `pip install -r requirements.txt`.
4. [Install the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) and [configure your credentials](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-quickstart.html).

# Deployment

1. Run `chalice deploy`.
2. Go to the AWS Console -> Lambda -> chatgpt-telegram-bot-dev-message-handler-lambda -> Configuration -> Function URL.
3. Click Create Function URL and set Auth type to NONE.
4. Copy the created function URL.
5. Stablish your Telegram webhook to point to you AWS Lambda running `curl --request POST --url https://api.telegram.org/bot<YOUR_TELEGRAM_TOKEN>/setWebhook --header 'content-type: application/json' --data '{"url": "YOUR_FUNCTION_URL"}'`

Great! Everything is setup :) Now go to Telegram and find your bot name and use ChatGPT from there!

# Coming soon!

- [X] Decoupled Token refresh in conversation.
- [X] Increase response performance.
- [X] Error handling from ChatGPT services.
- [ ] Deploy solution with one-click using CloudFormation.

# Credits

-  [ChatGPT Telegram Bot - @altryne
](https://github.com/altryne/chatGPT-telegram-bot)
- [whatsapp-gpt](https://github.com/danielgross/whatsapp-gpt)
- [ChatGPT Reverse Engineered API](https://github.com/acheong08/ChatGPT)
