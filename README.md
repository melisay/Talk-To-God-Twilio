# TalkToGod-local

A Raspberry Pi-based conversational AI that uses OpenAI's ChatGPT and ElevenLabs TTS to simulate a witty, sarcastic version of God. This project listens for your speech, processes your requests, and responds with humorous audio.

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Exposing Your Server with Ngrok](#Ngrok)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

## Features

- Voice call integration using Twilio's Voice API.
- Speech recognition for capturing user input.
- Text-to-speech conversion using the ElevenLabs API.
- ChatGPT integration for dynamic, conversational responses.
- Caching of responses to reduce latency and API calls.
- Support for various modes such as impressions, compliments, motivational quotes, voice switching, and more.

## Requirements

- **Hardware:**
  - A device capable of running a Python web server (e.g., a cloud VM, Raspberry Pi, etc.)
  - A telephone (for making calls via Twilio)

- **Software:**
  - Python 3.x
  - Git
  - `mpg123` for audio playback (if local playback is needed)
  - A web server (Flask is used in this project)

- **Python Libraries:**
  - `openai`
  - `requests`
  - `speech_recognition`
  - `pyaudio`
  - `elevenlabs`
  - `python-dotenv`
  - `flask`
  - `flask_limiter`

- **Or install the libraries manually:**
   ```bash
   pip3 install openai requests speechrecognition pyaudio elevenlabs python-dotenv flask flask-limiter twilio ngrok vosk

- **Install mpg123 (if required for local audio playback):**
   ```bash
   sudo apt-get update
   sudo apt-get install mpg123


## Installation

1. **Clone the Repository:**
   ```bash
   git clone https://github.com/melisay/TalkToGod-local.git
   cd TalkToGod-local

## Configuration

1. **Environment Variables::**
   ```bash
   ELEVENLABS_API_KEY=your_elevenlabs_api_key
   OPENAI_API_KEY=your_openai_api_key
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   TWILIO_PHONE_NUMBER=your_twilio_phone_number

2. **Voice Settings:**
- The project uses preset voices (VOICE_NIKKI) and (VOICE_TOM). 
- You can change these in the source code if needed.

3. **Paths:**
- Adjust paths such as BASE_DIR, CACHE_DIR and LOG_FILE in the source code if required

## Usage

1. **Running the Application::**
   ```bash
   python3 callgod.py

2. **Interacting::**
- Call the Twilio phone number you have configured.
- Speak your request (e.g., "compliment me", "do an impression", "sing me a song").
- The AI will process your request and respond with humorous audio.

3. **Updating the Code::**
   ```bash
   git pull

## Ngrok 

1. **Exposing Your Server with Ngrok::**
When running your Flask server locally (for example, on a Raspberry Pi), it listens on a local address (such as http://127.0.0.1:5001), which isn’t directly accessible from the public internet. This is where ngrok comes into play. Ngrok creates a secure tunnel from a public URL (for example, https://abc123.ngrok.io) to your local server, enabling external services like Twilio to reach your application.

2. **Why Use Ngrok?::**
- Public Accessibility: Exposes your local server to the internet, allowing external webhooks (e.g., from Twilio) to connect.
- Ease of Setup: Quickly test and develop without deploying to a cloud server.
- Secure Tunneling: Protects your local machine behind a firewall while still allowing external access.

3. **How It Works in This Project::**
- Run Your Flask App Locally:
- Your Flask server starts on a specified local port (e.g., 5001).

4. **Start Ngrok::**
- Run ngrok with the following command to create a tunnel to your local server:
   ```bash
   ngrok http 5001

- Ngrok will provide a public URL, for example, https://abc123.ngrok.io.

5. **Configure Twilio::**
- In your Twilio account, set the webhook URL for voice requests to your ngrok URL (e.g., https://abc123.ngrok.io/voice).

6. **Handle Incoming Requests::**
- When a call is made to your Twilio number, Twilio sends a request to the ngrok URL, which is forwarded to your local Flask server for processing.


## Troubleshooting

No Valid Input Devices:
- Ensure your Twilio phone number is properly configured and your API keys in the .env file are correct.

API Errors:
- Verify that your .env file has the correct API keys and that your network connection is active.

Audio Playback Issues:
- Confirm that mpg123 is installed and functioning correctly.
- Check that your Flask app is reachable via the public URL configured in your Twilio account

## Contributing

If you'd like to contribute, please fork the repository and create a pull request with your changes. Follow the coding standards and guidelines outlined in the repository.

## Licence
MIT License