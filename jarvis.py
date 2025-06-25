from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from timezonefinder import TimezoneFinder
from datetime import datetime
from geopy.geocoders import Nominatim
import requests
import os
import subprocess
import webbrowser
import speech_recognition as sr
import psutil
import pytz
from dotenv import load_dotenv
load_dotenv()


# === SET YOUR API KEYS ===
google_key = os.getenv("GOOGLE_API_KEY")
tavily_key = os.getenv("TAVILY_API_KEY")
weather_key = os.getenv("WEATHER_API_KEY")


# === Load Gemini LLM ===
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash")

# === Weather Tool ===
def get_weather(city):
    url = f"http://api.weatherapi.com/v1/current.json?key={weather_key}&q={city}&aqi=no"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return f"Sorry, couldn't fetch weather for {city} (status code {response.status_code})."
        data = response.json()
        condition = data['current']['condition']['text']
        temp_c = data['current']['temp_c']
        feels_like = data['current']['feelslike_c']
        return f"The weather in {city} is {condition} with {temp_c}°C (feels like {feels_like}°C)."
    except Exception as e:
        return f"Error: {str(e)}"


# === World Time Tool ===

def get_time_in_city(city_name):
    try:
        geolocator = Nominatim(user_agent="jarvis-time-bot")
        location = geolocator.geocode(city_name)
        if not location:
            return f"Couldn't find the city '{city_name}', sir."

        tf = TimezoneFinder()
        timezone_str = tf.timezone_at(lat=location.latitude, lng=location.longitude)
        if not timezone_str:
            return f"Couldn't determine the timezone for '{city_name}'."

        tz = pytz.timezone(timezone_str)
        local_time = datetime.now(tz).strftime("%I:%M %p")
        return f"The local time in {city_name.title()} is {local_time}, sir."
    except Exception as e:
        return f"Error getting time for {city_name}: {str(e)}"

# === Smart Open ===
def smart_open(query):
    from tavily import TavilyClient

    search_query = query.lower().replace("open", "").strip()
    try:
        print(f"🔎 Searching for: {search_query}")
        client = TavilyClient()
        results = client.search(query=search_query, max_results=1)
        if results and "results" in results and len(results["results"]) > 0:
            top_link = results["results"][0]["url"]
            webbrowser.open(top_link)
            return f"Opening {search_query}..."
        else:
            return f"Couldn't find a link for '{search_query}'."
    except Exception as e:
        return f"Error searching: {str(e)}"

# === System Commands ===
def handle_system_commands(query):
    query = query.lower()

    if "open youtube" in query:
        webbrowser.open("https://www.youtube.com")
        return "Opening YouTube..."

    elif "launch firefox" in query or "open firefox" in query:
        subprocess.Popen(["firefox"])
        return "Launching Firefox..."

    elif "open google" in query:
        webbrowser.open("https://www.google.com")
        return "Opening Google..."

    elif query.startswith("open "):
        return smart_open(query)

    elif "rickroll" in query:
        webbrowser.open("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        return "Never gonna give you up, sir."

    elif any(word in query for word in ["what time", "current time", "time is it", "tell me the time"]):
        from datetime import datetime
        now = datetime.now().strftime("%I:%M %p")
        return f"The current time is {now}, sir."

    elif "time in" in query:
        city = query.split("time in")[-1].strip()
        return get_time_in_city(city)


    return None

# === Voice Input ===
def listen_to_voice():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 Listening for 5 seconds...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        audio = recognizer.listen(source, phrase_time_limit=5)
    try:
        query = recognizer.recognize_google(audio)
        print(f"You (voice): {query}")
        return query
    except sr.UnknownValueError:
        print("❌ Couldn't understand, try again.")
        return ""
    except sr.RequestError as e:
        print(f"🔌 Could not request results: {e}")
        return ""
#=== Battery Status ===
def get_battery_status():
    battery = psutil.sensors_battery()
    if battery is None:
        return "I'm unable to access battery information on this device, sir."

    percent = battery.percent
    plugged = battery.power_plugged

    if plugged:
        return f"Power level at {percent}%. Currently charging, sir."
    elif percent < 20:
        return f"Warning: power at {percent}%. Recommend immediate recharge, sir."
    else:
        return f"Battery is at {percent}%. Not charging."


# === Main Loop ===
print("🧠 Jarvis Ready. Ask me anything! (Type 'exit' to quit)\n")

while True:
    user_input = input("You (type or press Enter for voice): ").strip()

    if user_input == "":
        query = listen_to_voice()
        if not query:
            continue  # skip if voice input failed
    else:
        query = user_input

        query_lower = query.lower()

    if query_lower in ("exit", "quit"):
        print("Jarvis: Shutting down. Stay smart 😎")
        break

    # Check for system commands
    sys_response = handle_system_commands(query_lower)
    if sys_response:
        response = sys_response

    # Weather check
    elif "weather in" in query_lower:
        city = query.split("weather in")[-1].strip()
        response = get_weather(city)

    # Battery Check
    elif any(word in query_lower for word in ["battery", "power level", "charge", "power status", "energy level"]):
        response = get_battery_status()

    # Time Check
    elif "time in" in query_lower:
        city = query_lower.split("time in")[-1].strip()
        response = get_time_in_city(city)



    # Fallback to Gemini (Falls back to gemini to give output)
    else:
        response = llm.invoke([HumanMessage(content=query)]).content

    print("Jarvis:", response)

