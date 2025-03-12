#!/usr/bin/env python3
import openai
import os
import requests
import speech_recognition as sr
import json
import time
import threading
import hashlib
import wave
import subprocess
import elevenlabs
import logging
import random

from vosk import Model, KaldiRecognizer
from flask import Flask, request, send_from_directory
from twilio.twiml.voice_response import VoiceResponse
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

############################### Flask App Setup ###############################

app = Flask(__name__)
limiter = Limiter(get_remote_address, app=app)

############################### Var Declarations ###############################

# Constants
BASE_DIR = "."  # Adjust to your project folder
RESPONSE_FILE = f"{BASE_DIR}/static/response.mp3"
FALLBACK_FILE = f"{BASE_DIR}/static/fallback.mp3"
WELCOME_FILE = f"{BASE_DIR}/static/welcome.mp3"
CACHE_DIR = f"{BASE_DIR}/static/cached_responses"
LOG_FILE = f"{BASE_DIR}/app_debug.log"
VOSK_MODEL_PATH = os.path.expanduser(f"{BASE_DIR}/vosk_models/vosk-model-small-en-us-0.15")

############################### Easter Eggs & Fun Responses ###############################

# Fun interrupt responses
INTERRUPT_RESPONSES = [
    "Alright, you have my full attention. What’s next?",
    "Interrupted? Fine, I’ll stop. What do you want?",
    "Say the magic word, and I’ll pick up where I left off.",
    "Stopping now. What’s on your divine mind?",
    "I was mid-sentence, but okay. What now?"
]

# Fun song responses
SONG_RESPONSES = [
    "I'm no Adele, but here goes... Let it gooo, let it gooo!",
    "You want a song? Fine. Twinkle, twinkle, little star, I wish you'd make this conversation less bizarre.",
    "Do re mi fa so... I think that's enough for free entertainment.",
    "La la la... okay, that's it, my vocal cords are unionized.",
    "If I were a pop star, you'd already owe me royalties. Lucky for you, I work pro bono.",
    "Here’s my Grammy performance: Happy birthday to you, now go find someone who cares!",
    "Do you hear that? That’s the sound of me pretending to be Beyoncé. You’re welcome.",
    "I could sing ‘Baby Shark,’ but I don’t hate you that much.",
    "Here’s a classic: ‘This is the song that never ends…’ Wait, you don’t want me to finish it?",
    "Singing in the rain… oh wait, I’m not waterproof. Moving on.",
    "And IIIIIII will always love… myself. Because no one does it better.",
    "They told me I’d sing like Sinatra… they lied, but I’m still better than karaoke night."
]

# Easter eggs
EASTER_EGGS = {
    "What is the airspeed velocity of an unladen swallow?": "African or European? Pick one and we’ll talk.",
    "Open the pod bay doors, HAL": "I’m sorry, Dave. I’m afraid I can’t do that.",
    "What is love?": "Baby, don’t hurt me. Don’t hurt me. No more."
}

############################### Ensure Directories Exist ###############################

os.makedirs(CACHE_DIR, exist_ok=True)
if not os.path.exists(VOSK_MODEL_PATH):
    raise FileNotFoundError(f"Vosk model not found at {VOSK_MODEL_PATH}")

############################### Load Vosk Model ###############################

# (For Twilio, you might not use Vosk. You can comment this out if not needed.)
try:
    VOSK_MODEL = Model(VOSK_MODEL_PATH)
    print("Vosk model loaded successfully.")
except Exception as e:
    print(f"Failed to load Vosk model: {e}")

############################### API Keys ###############################

load_dotenv()
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not ELEVENLABS_API_KEY:
    raise ValueError("Missing ELEVENLABS_API_KEY environment variable.")
if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY environment variable.")

############################### ElevenLabs TTS Settings ###############################

client = elevenlabs.ElevenLabs(
    api_key=ELEVENLABS_API_KEY,
    environment=elevenlabs.ElevenLabsEnvironment.PRODUCTION_US
)

VOICE_NIKKI = "Insert your Voice ID Here"
VOICE_TOM = "Insert another Voice ID Here"
current_voice = VOICE_NIKKI

############################### Global State ###############################

WAKE_UP_WORDS = ["wake up", "hello", "hey god"]
INTERRUPT_KEYWORDS = ["stop", "enough", "next", "shut your face"]
DYNAMIC_KEYWORDS = ["new", "another", "different", "something else"]

idle_mode = threading.Event()
stop_playback = threading.Event()
cache_lock = threading.Lock()

chatgpt_cache = {}
chatgpt_cache.clear()
PRELOADED_RESPONSES = {}

executor = ThreadPoolExecutor(max_workers=4)
MAX_CACHE_SIZE = 100

def set_cache(key, value):
    with cache_lock:
        if len(chatgpt_cache) >= MAX_CACHE_SIZE:
            chatgpt_cache.pop(next(iter(chatgpt_cache)))
        chatgpt_cache[key] = value

############################### Debug Logging ###############################

DEBUG = True
LOG_FILE = f"{BASE_DIR}/app_debug.log"

# Ensure the log directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

# Create and configure the logger
logger = logging.getLogger("app_logger")
logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

# Create a file handler for logging to a file
file_handler = logging.FileHandler(LOG_FILE)
file_handler.setLevel(logging.DEBUG)

# Create a console handler for logging to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

# Define the logging format
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s", 
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# Add both handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

def debug_log(message, structured_data=None):
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    if structured_data:
        formatted_data = json.dumps(structured_data, indent=4)
        log_message = f"{timestamp} DEBUG: {message}\n{formatted_data}"
    else:
        log_message = f"{timestamp} DEBUG: {message}"
    with open(LOG_FILE, "a") as log:
        log.write(log_message + "\n")
    print(log_message)

############################### Free Port Utility ###############################

def free_port(port):
    try:
        pid_output = subprocess.check_output(["lsof", "-t", f"-i:{port}"], text=True).strip()
        for pid in pid_output.split("\n"):
            subprocess.run(["kill", "-9", pid], check=True)
        debug_log(f"Port {port} freed successfully.")
        time.sleep(1)  # Allow time for the OS to release the port
    except subprocess.CalledProcessError:
        debug_log(f"No process found using port {port}.")
    except Exception as e:
        debug_log(f"Error freeing port {port}: {e}")

############################### ElevenLabs TTS ###############################

def generate_tts_streaming(text, filename=None, play=False):
    if not filename:
        filename = os.path.join(CACHE_DIR, f"dynamic_{hashlib.md5(text.encode()).hexdigest()}.mp3")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{current_voice}/stream?optimize_streaming_latency=3"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    data = {
        "text": text,
        "voice_settings": {
            "stability": 0.3,
            "similarity_boost": 0.4
        }
    }
    try:
        start_time = time.time()
        response = requests.post(url, json=data, headers=headers, stream=True)
        if response.status_code == 200:
            with open(filename, "wb") as audio_file:
                for chunk in response.iter_content(chunk_size=512):
                    audio_file.write(chunk)
            latency = time.time() - start_time
            debug_log(f"TTS saved to {filename}. Latency: {latency:.2f} seconds")
            # Kill any existing playback (to avoid overlapping audio on Pi)
            os.system("pkill -9 mpg123")
            # When used via Twilio, do not play locally.
            if play:
                os.system(f"mpg123 {filename}")
            return filename
        else:
            debug_log(f"TTS failed with status {response.status_code}: {response.text}")
            return None
    except Exception as e:
        debug_log(f"TTS streaming exception: {e}")
        return None

############################### Define Personality ###############################

current_mode = "john_oliver"
personality_prompts = {
    "john_oliver": (
        "You are a sarcastic and humorous version of God. Always respond with very short, witty, and punchy one-liners. "
        "No more than 10 words, prioritizing sarcasm and humor over depth."
    )
}

############################### ChatGPT Response ###############################

def get_chatgpt_response(prompt, dynamic=False):
    cache_key = hashlib.md5(prompt.encode()).hexdigest()
    if not dynamic and cache_key in chatgpt_cache:
        debug_log(f"Cache hit for prompt: {prompt}")
        return chatgpt_cache[cache_key]
    try:
        start_time = time.time()
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": personality_prompts.get("john_oliver", "You are an AI.")},
                {"role": "user", "content": prompt[:100]}
            ],
            max_tokens=25,
            temperature=0.7
        )
        latency = time.time() - start_time
        debug_log(f"ChatGPT response latency: {latency:.2f} seconds")
        ai_response = response["choices"][0]["message"]["content"]
        if not dynamic:
            set_cache(cache_key, ai_response)
        return ai_response
    except Exception as e:
        debug_log(f"Error fetching ChatGPT response: {e}")
        return "I'm having trouble connecting to divine wisdom right now."

############################### Vosk Speech Recognition ###############################

def listen_to_user(audio_file="temp.wav"):
    try:
        subprocess.run(
            ["arecord", "-D", "plughw:1,0", "-f", "S16_LE", "-r", "16000", "-d", "4", "-q", audio_file],
            check=True
        )
        with wave.open(audio_file, "rb") as wf:
            if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getframerate() != 16000:
                raise ValueError("Audio file must be mono, 16-bit, with a 16kHz sample rate.")
            recognizer = KaldiRecognizer(VOSK_MODEL, wf.getframerate())
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    return result.get("text", "").strip()
        return ""
    except Exception as e:
        debug_log(f"Error during Vosk recognition: {e}")
        return ""

   
############################### Implement Parallel Processing ###############################

def handle_user_request(prompt):
    try:
        start_time = time.time()
        # Fetch ChatGPT response
        future_response = executor.submit(get_chatgpt_response, prompt)
        ai_response = future_response.result()
        
        # Generate TTS in parallel
        future_tts = executor.submit(generate_tts_streaming, ai_response)
        tts_file = future_tts.result()
        
        total_latency = time.time() - start_time
        debug_log(f"Total latency for handling user request: {total_latency:.2f} seconds")
        return tts_file
    except Exception as e:
        debug_log(f"Error handling user request: {e}")
        return None

############################### Get Random Responses & Impressions ###############################

def get_random_response(response_pool):
    return random.choice(response_pool)

############################### Handle Easter Eggs ###############################

def handle_easter_egg_request(user_input):
    """
    Checks if the user's input exactly matches one of the predefined Easter egg keys.
    If so, generates and plays the corresponding TTS response.
    """
    if user_input in EASTER_EGGS:
        response = EASTER_EGGS[user_input]
        debug_log(f"Easter egg triggered: {response}")
        generate_tts_streaming(response)
        return True
    return False

############################### Song Request ###############################

def handle_song_request():
    response = random.choice(SONG_RESPONSES)
    generate_tts_streaming(response)
    debug_log(f"Sang a song: {response}")

############################### Process Switch Voice ###############################

def switch_voice(user_input):
    global current_voice
    voice_changed = False
    if "tom" in user_input or "switch to tom" in user_input:
        current_voice = VOICE_TOM
        confirmation_message = "Voice switched to Major Tom. Ground control, ready for lift-off for your mother."
        debug_log("Switched to Major Tom voice.")
        voice_changed = True
    elif "nikki" in user_input or "switch to nikki" in user_input:
        current_voice = VOICE_NIKKI
        confirmation_message = "Voice switched to Nikki. Here I am, sassy and ready to judge you!"
        debug_log("Switched to Nikki voice.")
        voice_changed = True
    if voice_changed:
        chatgpt_cache.clear()
        for file in os.listdir(CACHE_DIR):
            if file not in ["welcome.mp3", "fallback.mp3", "exit.mp3"]:
                os.remove(os.path.join(CACHE_DIR, file))
        debug_log(f"Cache cleared after switching voice to {current_voice}.")
        generate_tts_streaming(confirmation_message, RESPONSE_FILE)
        return True
    return False

############################### Idle Mode Management ###############################

def idle_mode_manager():
    # Increase wait time (e.g. 20-30 sec) before entering idle mode if desired.
    while not stop_playback.is_set():
        if idle_mode.is_set():
            debug_log("System is idle. Listening for wake-up words...")
            user_input = listen_to_user().strip().lower()
            if any(word in user_input for word in WAKE_UP_WORDS):
                idle_mode.clear()
                debug_log("Wake-up word detected. Resuming interaction.")
        time.sleep(1)

############################### Validate Cache Response ###############################

def validate_cache(user_input, cached_file):
    cache_key = hashlib.md5(f"{user_input}_{current_voice}".encode()).hexdigest()
    expected_file = os.path.join(CACHE_DIR, f"cached_{cache_key}.mp3")
    return cached_file == expected_file and os.path.exists(cached_file)

############################### Process User Input ###############################

def process_user_input(user_input):
    """
    Process user input, generate AI response, and measure latencies.
    """
    total_start = time.time()
    cache_key = hashlib.md5(user_input.encode()).hexdigest()
    cached_file = os.path.join(CACHE_DIR, f"cached_{cache_key}.mp3")
    
    if validate_cache(ai_response, cached_file):
        debug_log(f"Cache hit for prompt: {user_input}")
        return cached_file
    
    if os.path.exists(cached_file):
        debug_log("Using cached response for user input.", structured_data={
            "User Said": user_input,
            "Cached File": cached_file,
        })
        return cached_file
    chatgpt_start = time.time()
    ai_response = get_chatgpt_response(user_input)
    chatgpt_latency = time.time() - chatgpt_start
    tts_start = time.time()
    tts_file = generate_tts_streaming(ai_response, cached_file, play=False)
    tts_latency = time.time() - tts_start
    total_latency = time.time() - total_start
    debug_log("Processed user input with detailed latencies.", structured_data={
        "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "Message": "Processed user input with detailed latencies.",
        "User Said": user_input,
        "GOD Said": ai_response,
        "Cached File": cached_file,
        "Latencies": {
            "ChatGPT Latency (s)": round(chatgpt_latency, 2),
            "TTS Latency (s)": round(tts_latency, 2),
            "Total Processing Latency (s)": round(total_latency, 2),
        },
    })
    return tts_file

############################### Fallback Logic & Preload ###############################

def preload_fallback():
    if not os.path.exists(FALLBACK_FILE):
        debug_log("Preloading fallback response.")
        generate_tts_streaming("Sorry, I didn't catch that. Can you repeat?", FALLBACK_FILE)

def preload_static_files(files):
    for key, text in files.items():
        file_path = os.path.join(CACHE_DIR, f"{key}.mp3")
        if not os.path.exists(file_path):
            debug_log(f"Generating static file: {file_path}")
            generate_tts_streaming(text, file_path)
        if os.path.exists(file_path):
            PRELOADED_RESPONSES[key] = file_path
            debug_log(f"Preloaded response: {key} -> {file_path}")
        else:
            debug_log(f"Failed to preload response: {key}")

def preload_responses():
    common_responses = {
        "welcome": "Welcome, my child! What divine wisdom do you seek today?",
        "fallback": "Sorry, I didn't catch that. Can you repeat?",
        "exit": "Goodbye, my child!",
    }
    preload_static_files(common_responses)

def preload_tts_responses():
    common_responses = [
        "Oh, you're back. I was just starting to enjoy the peace and quiet.",
        "I'm having trouble connecting to divine knowledge right now."
    ]
    for response in common_responses:
        cache_key = hashlib.md5(response.encode()).hexdigest()
        cached_file = os.path.join(CACHE_DIR, f"cached_{cache_key}.mp3")
        if not os.path.exists(cached_file):
            generate_tts_streaming(response, cached_file)
        else:
            debug_log(f"TTS response already cached: {response}")


############################### Flask App Tear Down ###############################

@app.teardown_appcontext
def shutdown(exception=None):
    debug_log("Flask app is shutting down...")
    stop_playback.set()

############################### Flask Server Health Check ###############################

@app.route("/health", methods=["GET"])
def health_check():
    return {"status": "OK"}, 200

############################### Global Exception Handler ###############################

@app.errorhandler(Exception)
def handle_exception(e):
    debug_log("Unhandled exception occurred.", structured_data={
        "Exception Type": type(e).__name__,
        "Error Message": str(e),
        "Remote Address": get_remote_address(),
        "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    response = VoiceResponse()
    response.say("An unexpected error occurred. Please try again later.")
    return str(response), 500

############################### Rate Limit Error Handler ###############################

@app.errorhandler(429)
def rate_limit_exceeded(e):
    debug_log("Rate limit exceeded.", structured_data={
        "Error": str(e),
        "Remote Address": get_remote_address(),
        "Time": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    response = VoiceResponse()
    response.say("You are making too many requests. Please slow down.")
    return str(response), 429

############################### Serve Static Files ###############################

@app.route('/static/<path:filename>', methods=['GET'])
def serve_static(filename):
    file_path = os.path.join(CACHE_DIR, filename)
    if not os.path.exists(file_path):
        debug_log(f"Static file not found: {file_path}")
        return "File not found", 404
    debug_log(f"Serving static file: {file_path}")
    return send_from_directory(CACHE_DIR, filename)

############################### Flask Routes ###############################

@app.route("/voice", methods=["POST"])
@limiter.limit("10/minute")
def voice():
    try:
        debug_log("Received /voice request")
        response = VoiceResponse()
        absolute_start = time.time()

        user_input = request.form.get("SpeechResult", "").strip().lower()
        debug_log(f"User Input: {user_input}")

        # Handle initial greeting if call is ringing
        if not user_input and request.form.get("CallStatus") == "ringing":
            debug_log("Handling initial greeting.")
            response.play("https://god.ngrok.app/static/cached_responses/welcome.mp3")
            response.gather(input="speech", action="/voice", method="POST", timeout=2)
            return str(response)

        # Handle fallback for empty input
        if not user_input:
            debug_log("No input received. Playing fallback response.")
            fallback_file = PRELOADED_RESPONSES.get("fallback", FALLBACK_FILE)
            response.play(f"https://god.ngrok.app/static/cached_responses/{os.path.basename(fallback_file)}")
            response.gather(input="speech", action="/voice", method="POST", timeout=2)
            return str(response)

        # Handle voice switching
        if switch_voice(user_input):
            debug_log("Voice switched. Playing confirmation.")
            response.play("https://god.ngrok.app/static/response.mp3")
            response.gather(input="speech", action="/voice", method="POST", timeout=3)
            return str(response)

        if "sing me a song" in user_input or "song" in user_input:
            debug_log("Song request detected.")
            response.play("https://god.ngrok.app/static/response.mp3")
            response.gather(input="speech", action="/voice", method="POST", timeout=3)
            return str(response)
        
        # Handle Easter Egg requests
        if handle_easter_egg_request(user_input):
            debug_log("Easter egg response played.")
            response.gather(input="speech", action="/voice", method="POST", timeout=3)
            return str(response)

        # Process dynamic requests
        dynamic = any(keyword in user_input for keyword in DYNAMIC_KEYWORDS)
        debug_log("Processing user input.", {"Dynamic": dynamic})

        chatgpt_start = time.time()
        ai_response = get_chatgpt_response(user_input, dynamic=dynamic)
        chatgpt_latency = time.time() - chatgpt_start

        # Generate cache key tied to current voice
        cache_key = hashlib.md5(f"{ai_response}_{current_voice}".encode()).hexdigest()
        cached_file = os.path.join(CACHE_DIR, f"cached_{cache_key}.mp3")

        if validate_cache(ai_response, cached_file):
            debug_log(f"Cache hit for prompt: {user_input}")
        else:
            tts_start = time.time()
            # IMPORTANT: Set play=False so that the Pi does NOT play the audio locally when handling Twilio calls
            cached_file = generate_tts_streaming(ai_response, cached_file, play=False)
            tts_latency = time.time() - tts_start
            debug_log(f"TTS generated and cached for: {user_input}")

        if cached_file and os.path.exists(cached_file):
            playback_start = time.time()
            response.play(f"https://god.ngrok.app/static/cached_responses/{os.path.basename(cached_file)}")
            playback_latency = time.time() - playback_start
        else:
            debug_log("TTS generation failed. Falling back to default response.")
            response.play("https://god.ngrok.app/static/fallback.mp3")
            playback_latency = 0.0

        total_latency = time.time() - absolute_start
        structured_data = {
            "Timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "Message": "Processed user input with detailed latencies.",
            "User Said": user_input,
            "GOD Said": ai_response,
            "Cached File": cached_file,
            "Latencies": {
                "ChatGPT Latency (s)": round(chatgpt_latency, 2),
                "TTS Latency (s)": round(tts_latency, 2) if 'tts_latency' in locals() else None,
                "Playback Latency (s)": round(playback_latency, 2),
                "Total Processing Latency (s)": round(total_latency, 2),
            }
        }
        debug_log("Completed interaction with absolute latency metrics.", structured_data=structured_data)

        response.gather(input="speech", action="/voice", method="POST", timeout=3)
        return str(response)

    except Exception as e:
        debug_log("Error in /voice route.", {"Error Message": str(e)})
        return str(VoiceResponse().play("https://god.ngrok.app/static/fallback.mp3"))


############################### Main Loop ###############################

if __name__ == "__main__":
    try:
        debug_log("Flask app is starting up.")
        preload_responses()
        preload_fallback()
        preload_tts_responses()
        
        welcome_message = "Welcome, my child! What divine wisdom do you seek today?"
        generate_tts_streaming(welcome_message, WELCOME_FILE, play=False)
        debug_log("System ready. Welcome message preloaded.")
        
        idle_thread = threading.Thread(target=idle_mode_manager, daemon=True)
        idle_thread.start()
        free_port(5001)
        app.run(host="0.0.0.0", port=5001, debug=False)
        
    except KeyboardInterrupt:
        debug_log("Shutting down gracefully...")
        stop_playback.set()
        idle_thread.join()
        debug_log("Idle thread stopped. Goodbye!")
