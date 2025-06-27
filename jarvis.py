import os
import json
import requests
import webbrowser
import re
import psutil
import pytz
import speech_recognition as sr
from datetime import datetime
from timezonefinder import TimezoneFinder
from geopy.geocoders import Nominatim
from dotenv import load_dotenv
from tavily import TavilyClient
from groq import Groq

# === Load API Keys ===
load_dotenv()
weather_key = os.getenv("WEATHER_API_KEY")
tavily_key = os.getenv("TAVILY_API_KEY")
groq_key = os.getenv("GROQ_API_KEY")

# === Memory and History Files ===
MEMORY_FILE = "jarvis_memory.json"
HISTORY_FILE = "chat_history.txt"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {"natural": [], "structured": {}}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

def append_history(role, content):
    with open(HISTORY_FILE, "a") as f:
        f.write(f"{role}: {content.strip()}\n")

def get_history_context(limit=10):
    if not os.path.exists(HISTORY_FILE):
        return ""
    with open(HISTORY_FILE, "r") as f:
        lines = f.readlines()
    return "".join(lines[-limit*2:])  # last N user+jarvis turns

memory = load_memory()
client = Groq(api_key=groq_key)

def ask_llm(query):
    history = get_history_context()
    context = "\n".join([f"{k}: {v}" for k, v in memory["structured"].items()])
    prompt = f"""You are Jarvis, a helpful assistant.

Here is what you know about the user:
{context}

Here is the recent conversation:
{history}

User just asked: {query}
Respond helpfully, naturally, and consistently."""
    
    chat_completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[{"role": "user", "content": prompt}],
    )
    return chat_completion.choices[0].message.content.strip()

# === Intent Detection for Structured Memory ===
def extract_structured_facts(text):
    structured = {}
    patterns = {
        "name": [r"my name is (\w+)", r"i am (\w+)", r"this is (\w+)"],
        "favorite_color": [r"my favourite color is (\w+)", r"i like the color (\w+)"],
        "title": [r"call me (\w+)", r"from now on call me (\w+)"],
        "hobby": [r"my hobby is (.+)", r"i enjoy (.+)", r"i love (.+)"],
    }

    text = text.lower()
    for key, regex_list in patterns.items():
        for pattern in regex_list:
            match = re.search(pattern, text)
            if match:
                structured[key] = match.group(1).strip()
                break
    return structured

def answer_from_structured(query):
    patterns = {
        "favorite_color": [r"(?i)what(?:'s| is)? my favorite color"],
        "name": [r"(?i)what(?:'s| is)? my name", r"(?i)who am i"],
        "title": [r"(?i)what(?:'s| is)? my title", r"(?i)what should i call you"],
        "hobby": [r"(?i)what(?:'s| is)? my hobby"],
    }

    for key, regex_list in patterns.items():
        for pattern in regex_list:
            if re.search(pattern, query, re.IGNORECASE):
                if key in memory["structured"]:
                    return f"Your {key.replace('_', ' ')} is {memory['structured'][key]}."
    return None

# === Utilities ===
def get_weather(city):
    url = f"http://api.weatherapi.com/v1/current.json?key={weather_key}&q={city}&aqi=no"
    try:
        r = requests.get(url)
        data = r.json()["current"]
        return f"{city.title()}: {data['condition']['text']}, {data['temp_c']}°C (Feels like {data['feelslike_c']}°C)"
    except:
        return "Sorry, I couldn't fetch the weather."

def get_battery():
    battery = psutil.sensors_battery()
    if not battery:
        return "Battery info unavailable."
    status = "charging" if battery.power_plugged else "not charging"
    return f"Battery is at {battery.percent}%, {status}."

def get_time_in(city):
    try:
        geo = Nominatim(user_agent="jarvis")
        loc = geo.geocode(city)
        tz = TimezoneFinder().timezone_at(lat=loc.latitude, lng=loc.longitude)
        now = datetime.now(pytz.timezone(tz)).strftime("%I:%M %p")
        return f"Local time in {city.title()} is {now}"
    except:
        return "Couldn't get the time."

def smart_open(query):
    client = TavilyClient(api_key=tavily_key)
    results = client.search(query=query, max_results=1)
    if results["results"]:
        url = results["results"][0]["url"]
        webbrowser.open(url)
        return f"Opening: {url}"
    return "No results found."

def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Listening...")
        r.adjust_for_ambient_noise(source)
        audio = r.listen(source, phrase_time_limit=5)
        try:
            return r.recognize_google(audio)
        except:
            return ""

# === Main Loop ===
print("🧠 Jarvis is online. Say or type something ('exit' to quit)\n")

while True:
    query = input("You (or press Enter for voice): ").strip()
    if not query:
        query = listen()
    if not query:
        continue

    append_history("User", query)

    query_lower = query.lower()
    if query_lower in ["exit", "quit"]:
        print("Jarvis: Goodbye!")
        append_history("Jarvis", "Goodbye!")
        break

    if "weather in" in query_lower:
        city = query.split("weather in")[-1].strip()
        response = get_weather(city)

    elif "battery" in query_lower or "charge" in query_lower:
        response = get_battery()

    elif "time in" in query_lower:
        city = query.split("time in")[-1].strip()
        response = get_time_in(city)

    elif query_lower.startswith("open "):
        response = smart_open(query)

    elif "what do you remember" in query_lower:
        structured = "\n".join([f"{k.replace('_',' ')}: {v}" for k, v in memory["structured"].items()])
        natural = "\n".join(["- " + f for f in memory["natural"]])
        response = f"Here's what I remember:\n\n🔹 Facts:\n{structured or 'None'}\n\n📝 Notes:\n{natural or 'None'}"

    else:
        structured_response = answer_from_structured(query)
        if structured_response:
            response = structured_response
        else:
            facts = extract_structured_facts(query)
            if facts:
                memory["structured"].update(facts)
                save_memory(memory)
                response = "Got it. I'll remember that."
            else:
                memory["natural"].append(query)
                save_memory(memory)
                response = ask_llm(query)

    print("Jarvis:", response)
    append_history("Jarvis", response)
