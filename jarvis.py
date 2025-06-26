import os
import json
import requests
import webbrowser
import subprocess
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

# === Memory ===
MEMORY_FILE = "jarvis_memory.json"

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            return json.load(f)
    return {"natural": [], "structured": {}}

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

memory = load_memory()

# === Groq LLM ===
client = Groq(api_key=groq_key)

def ask_llm(prompt):
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

# === Answer from Structured Memory ===
def answer_from_structured(query):
    patterns = {
        "favorite_color": [r"(?i)what(?:'s| is)? my favorite color", r"(?i)do you know.*color.*like"],
        "name": [r"(?i)what(?:'s| is)? my name", r"(?i)who am i", r"(?i)do you know my name"],
        "hobby": [r"(?i)what(?:'s| is)? my hobby", r"(?i)what do i enjoy"],
    }

    for key, regex_list in patterns.items():
        for pattern in regex_list:
            if re.search(pattern, query, re.IGNORECASE):
                if key in memory["structured"]:
                    return f"Your {key.replace('_', ' ')} is {memory['structured'][key]}."
    return None

# === Weather ===
def get_weather(city):
    url = f"http://api.weatherapi.com/v1/current.json?key={weather_key}&q={city}&aqi=no"
    try:
        r = requests.get(url)
        data = r.json()["current"]
        return f"{city.title()}: {data['condition']['text']}, {data['temp_c']}°C (Feels like {data['feelslike_c']}°C)"
    except:
        return "Sorry, I couldn't fetch the weather."

# === Battery ===
def get_battery():
    battery = psutil.sensors_battery()
    if not battery:
        return "Battery info unavailable."
    status = "charging" if battery.power_plugged else "not charging"
    return f"Battery is at {battery.percent}%, {status}."

# === World Time ===
def get_time_in(city):
    try:
        geo = Nominatim(user_agent="jarvis")
        loc = geo.geocode(city)
        tz = TimezoneFinder().timezone_at(lat=loc.latitude, lng=loc.longitude)
        now = datetime.now(pytz.timezone(tz)).strftime("%I:%M %p")
        return f"Local time in {city.title()} is {now}"
    except:
        return "Couldn't get the time."

# === Tavily Smart Search ===
def smart_open(query):
    client = TavilyClient(api_key=tavily_key)
    results = client.search(query=query, max_results=1)
    if results["results"]:
        url = results["results"][0]["url"]
        webbrowser.open(url)
        return f"Opening: {url}"
    return "No results found."

# === Voice Input ===
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
print(extract_structured_facts("my name is sankar"))

while True:
    query = input("You (or press Enter for voice): ").strip()
    if not query:
        query = listen()
    if not query:
        continue

    query_lower = query.lower()
    if query_lower in ["exit", "quit"]:
        print("Jarvis: Goodbye!")
        break

    # === Commands ===
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
        structured = "\n".join([f"{k.replace('_',' ')}: {v}" for k,v in memory["structured"].items()])
        natural = "\n".join(["- " + f for f in memory["natural"]])
        response = f"Here's what I remember:\n\n🔹 Facts:\n{structured or 'None'}\n\n📝 Notes:\n{natural or 'None'}"

    else:
        # Step 1: Try to respond from structured memory
        structured_response = answer_from_structured(query)
        if structured_response:
            response = structured_response
        else:
            # Step 2: Try to extract and store structured info
            facts = extract_structured_facts(query)
            if facts:
                memory["structured"].update(facts)
                save_memory(memory)
                response = "Got it. I'll remember that."
            else:
                # Step 3: Fallback to natural memory + LLM
                memory["natural"].append(query)
                save_memory(memory)
                context = "\n".join([f"{k}: {v}" for k,v in memory["structured"].items()])
                prompt = f"""You are Jarvis. The user said: {query}

Here is what you know about them:
{context}

Respond helpfully and naturally."""
                response = ask_llm(prompt)

    print("Jarvis:", response)