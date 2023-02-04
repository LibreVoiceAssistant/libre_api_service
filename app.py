import asyncio
import base64
import datetime
import json
import os
import re
import threading
import openai as ai
import uuid as uuid_challenge
from sqlite3 import paramstyle
from urllib import response

import requests
from flask import (Flask, jsonify, make_response, redirect, render_template,
                   request)
from json_database import JsonDatabase

from modules.storage import Storage
from modules.helper import Helper
from ovos_utils.smtp_utils import send_smtp
from weather import WeatherAPI, WeatherOWM

app = Flask(__name__)
device_registry = JsonDatabase('/tmp/ovos_api.json')
weather_app_owm = WeatherOWM()
weather_app_wapi = WeatherAPI()
loop = asyncio.get_event_loop()

class Devices:
    def __init__(self, uuid):
        self.uuid = uuid

# Generate a session challenge which is only valid for one hour and store it in a file
@app.route('/get_session_challenge', methods=["GET"])
def create_session_challenge():
    try:
        if os.path.exists('/tmp/ovos_session_challenge.json'):
            current_challenge = read_session_challenge()
            return jsonify({'challenge': str(current_challenge)})
        else:
            challenge = str(uuid_challenge.uuid4().hex)
            with open('/tmp/ovos_session_challenge.json', 'w') as f:
                f.write(json.dumps({'session_challenge': challenge}))
            return jsonify({'challenge': str(challenge)})
    except Exception as e:
        print(e)
        return jsonify({'error': str(e)}, 500)

@app.route('/create_challenge', methods=['GET'])
def create_challenge():
    try:
        challenge = str(uuid_challenge.uuid4().hex)
        challenge_secret = str(uuid_challenge.uuid4().hex)

        # store challenge in a temporary file
        challenge_data = {'challenge': challenge, 'secret': challenge_secret}
        with open('/tmp/ovos_api_challenge.json', 'w') as f:
            f.write(json.dumps(challenge_data))

        response = make_response(jsonify({'challenge': challenge, 'secret': challenge_secret}), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    except Exception as e:
        print(e)
        response = make_response(jsonify({'error': str(e)}), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

@app.route('/register_device/<string:uuid>/<string:key>', methods=['GET'])
def register_device(uuid, key):
    try:
        deviceID = uuid
        deviceKey = key
        challenge = read_challenge()

        if deviceKey == challenge['secret']:
            device = Devices(deviceID)
            # first check if device is already registered
            if deviceID in device_registry.search_by_value('uuid', deviceID):
                response = make_response(jsonify({'error': 'Device Already Registered'}), 500)
                response.headers['Content-Type'] = 'application/json'
                return response
            else:
                if device_registry.add_item(device):
                    device_registry.commit()
                    response = make_response(jsonify({'status': 'success'}), 200)
                    response.headers['Content-Type'] = 'application/json'
                    return response
                else:
                    response = make_response(jsonify({'status': 'error'}), 400)
                    response.headers['Content-Type'] = 'application/json'
                    return response
        else:
            response = make_response(jsonify({'status': 'error'}), 400)
            response.headers['Content-Type'] = 'application/json'
            return response

    except Exception as e:
        print(e)
        response = make_response(jsonify({'error': str(e)}), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

@app.route('/weather/generate_current_weather_report/<string:uuid>', methods=['GET', 'POST'])
def generate_current_weather_report(uuid):
    _storage = Storage()
    _app_id = base64.b64decode(_storage.set_owm_api_config()).decode("utf-8")

    try:
        # check request header for backend
        backend = request.headers.get('backend')
        selected_backend = None

        if request.method == 'GET':
            lat = request.args.get('lat', "")
            lon = request.args.get('lon', "")
            lang = request.args.get('lang', "")
            units = request.args.get('units', "")
            location = request.args.get('location', "")

        if request.method == 'POST':
            request_params = request.form
            if request_params:
                lat = request_params.get('lat', "")
                lon = request_params.get('lon', "")
                lang = request_params.get('lang', "")
                units = request_params.get('units', "")
                location = request_params.get('location', "")

        if backend:
            selected_backend = backend
        else:
            selected_backend = 'WAPI'

        # check request header for session challenge
        if request.headers.get('session_challenge') == read_session_challenge():
            # search the list of dictionaries if the uuid key has the same value as the uuid parameter
            if check_if_device_is_registered(uuid):
                if selected_backend == "OWM":
                    params = {
                        "lat": lat,
                        "lon": lon,
                        "lang": lang,
                        "units": units,
                        "appid": _app_id
                    }
                    url = "https://api.openweathermap.org/data/2.5/weather"
                    current_report = requests.get(url, params=params)
                else:
                    current_report = loop.run_until_complete(weather_app_wapi.current(location))

                response = make_response(current_report.json(), 200)
                response.headers['Content-Type'] = 'application/json'
                return response
            else:
                response = make_response(jsonify({'status': 'not authorized'}), 401)
                response.headers['Content-Type'] = 'application/json'
                return response
        else:
            response = make_response(jsonify({'status': 'invalid session'}), 401)
            response.headers['Content-Type'] = 'application/json'
            return response

    except Exception as e:
        print(e)
        response = make_response(jsonify({'error': str(e)}), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

@app.route('/weather/generate_forecast_weather_report/<string:uuid>', methods=['GET', 'POST'])
def generate_forecast_weather_report(uuid):
    _storage = Storage()
    _app_id = base64.b64decode(_storage.set_owm_api_config()).decode("utf-8")
    # Requires a paid subscription to OpenWeatherMap

    try:
        # check request header for backend
        backend = request.headers.get('backend')
        selected_backend = None

        if request.method == 'GET':
            lat = request.args.get('lat', "")
            lon = request.args.get('lon', "")
            lang = request.args.get('lang', "")
            units = request.args.get('units', "")
            location = request.args.get('location', "")

        if request.method == 'POST':
            request_params = request.form
            if request_params:
                lat = request_params.get('lat', "")
                lon = request_params.get('lon', "")
                lang = request_params.get('lang', "")
                units = request_params.get('units', "")
                location = request_params.get('location', "")

        if backend:
            selected_backend = backend
        else:
            selected_backend = 'WAPI'

        if request.headers.get('session_challenge') == read_session_challenge():
            # search the list of dictionaries if the uuid key has the same value as the uuid parameter
            if check_if_device_is_registered(uuid):
                if selected_backend == "OWM":
                    params = {
                        "lat": lat,
                        "lon": lon,
                        "lang": lang,
                        "units": units,
                        "appid": _app_id
                    }

                    url = "https://api.openweathermap.org/data/2.5/forecast/daily"
                    forecast_report = requests.get(url, params=params)
                else:
                    forecast_report = loop.run_until_complete(weather_app_wapi.forecast(location))
                return make_response(forecast_report.json(), 200)
            else:
                return make_response(jsonify({'status': 'not authorized'}), 401)
        else:
            return make_response(jsonify({'status': 'invalid session'}), 401)
    except Exception as e:
        print(e)
        return make_response(jsonify({'error': str(e)}), 500)

@app.route('/weather/generate_hourly_weather_report/<string:uuid>', methods=['GET', 'POST'])
def generate_hourly_weather_report(uuid):
    _storage = Storage()
    _app_id = base64.b64decode(_storage.set_owm_api_config()).decode("utf-8")

    try:
        # check request header for backend
        backend = request.headers.get('backend')
        selected_backend = None

        if request.method == 'GET':
            lat = request.args.get('lat', "")
            lon = request.args.get('lon', "")
            lang = request.args.get('lang', "")
            units = request.args.get('units', "")
            location = request.args.get('location', "")

        if request.method == 'POST':
            request_params = request.form
            if request_params:
                lat = request_params.get('lat', "")
                lon = request_params.get('lon', "")
                lang = request_params.get('lang', "")
                units = request_params.get('units', "")
                location = request_params.get('location', "")

        if backend:
            selected_backend = backend
        else:
            selected_backend = 'WAPI'

        if request.headers.get('session_challenge') == read_session_challenge():
            # search the list of dictionaries if the uuid key has the same value as the uuid parameter
            if check_if_device_is_registered(uuid):
                if selected_backend == "OWM":
                    params = {
                        "lat": lat,
                        "lon": lon,
                        "lang": lang,
                        "units": units,
                        "appid": _app_id
                    }
                    url = "https://api.openweathermap.org/data/2.5/forecast"
                    hourly_report = requests.get(url, params=params)
                else:
                    hourly_report = loop.run_until_complete(weather_app_wapi.day(location, datetime.date.today()))
                return make_response(hourly_report.json(), 200)
            else:
                return make_response(jsonify({'status': 'not authorized'}), 401)
        else:
            return make_response(jsonify({'status': 'invalid session'}), 401)

    except Exception as e:
        print(e)
        return make_response(jsonify({'error': str(e)}), 500)

@app.route('/weather/generate_hourly_weather_report_for_date/<string:uuid>/<string:location>/<string:date>', methods=['GET'])
def generate_hourly_weather_report_for_date(uuid, location, date):
    try:
        # check request header for backend
        backend = request.headers.get('backend')
        selected_backend = None

        if backend:
            selected_backend = backend
        else:
            selected_backend = 'WAPI'

        if request.headers.get('session_challenge') == read_session_challenge():
            # search the list of dictionaries if the uuid key has the same value as the uuid parameter
            if check_if_device_is_registered(uuid):
                if selected_backend == "OWM":
                    return make_response(jsonify({'status': 'error'}), 400)
                else:
                    hourly_report = loop.run_until_complete(weather_app_wapi.day(location, datetime.datetime.strptime(date, '%Y-%m-%d').date()))
                    return make_response(hourly_report.json(), 200)
            else:
                return make_response(jsonify({'status': 'error'}), 400)

    except Exception as e:
        print(e)
        return make_response(jsonify({'error': str(e)}), 500)

@app.route('/weather/onecall_weather_report/<string:uuid>', methods=['POST'])
def generate_onecall_weather_report(uuid):
    try:
        # check request header for backend
        params = request.form
        if params:
            lat = float(params.get('lat'))
            lon = float(params.get('lon'))
            units = params.get('units')
            lang = params.get('lang')
            print(lat, lon, units, lang)
        else:
            print("No params")
            lat = None
            lon = None
            units = None
            lang = None

        backend = request.headers.get('backend')
        selected_backend = None

        if backend:
            selected_backend = backend
        else:
            selected_backend = 'WAPI'

        print(request.headers.get('session_challenge'))
        if request.headers.get('session_challenge') == read_session_challenge():
            print("session challenge met")
            if check_if_device_is_registered(uuid):
                if selected_backend == "OWM":
                    print("Generating onecall report for OWM")
                    onecall_report = weather_app_owm.manager.one_call(lat=lat, lon=lon, units=units, lang=lang)

                    current_forecast_result = onecall_report.current.to_dict()
                    currentresult = weather_app_owm.map_to_owm_report_current(current_forecast_result)

                    daily_forecast_result_list = []
                    for dailyforecast in range(len(onecall_report.forecast_daily)):
                        daily_forecast_result_list.append(onecall_report.forecast_daily[dailyforecast].to_dict())
                    dailyforecastresult = weather_app_owm.map_to_owm_daily(daily_forecast_result_list)

                    hour_forecast_result_list = []
                    for hourforecast in range(len(onecall_report.forecast_hourly)):
                        hour_forecast_result_list.append(onecall_report.forecast_hourly[hourforecast].to_dict())
                    hourforecastresult = weather_app_owm.map_to_owm_hourly(hour_forecast_result_list)

                    get_timezone_obj = weather_app_owm.get_timezone_details(lat, lon)

                    forecast_result = weather_app_owm.generate_one_report(currentresult, dailyforecastresult, hourforecastresult, get_timezone_obj)
                    return make_response(jsonify(forecast_result), 200)
                else:
                    return make_response(jsonify({'status': 'error'}), 400)
            else:
                return make_response(jsonify({'status': 'error'}), 400)
        else:
            return make_response(jsonify({'status': 'error'}), 400)
    except Exception as e:
        print(e)
        return make_response(jsonify({'error': str(e)}), 500)

def read_challenge():
    with open('/tmp/ovos_api_challenge.json', 'r') as f:
        challenge = json.loads(f.read())
        return challenge

def read_session_challenge():
    with open('/tmp/ovos_session_challenge.json', 'r') as f:
        challenge = json.loads(f.read())
        return challenge['session_challenge']

def timer_for_session_challenge():
    # wait for one hour and then delete the session challenge file
    # use a thread to run this function
    threading.Timer(3600, delete_session_challenge).start()

def delete_session_challenge():
    os.remove('/tmp/ovos_session_challenge.json')

def check_if_device_is_registered(uuid):
    for device in device_registry:
        if device['uuid'] == uuid:
            return True
    return False

# Create a post api endpoint for omdb api call and return the response in json format
@app.route('/omdb/search_movie/', methods=['GET', 'POST'])
def search_movie():
    _storage = Storage()
    _key = base64.b64decode(_storage.set_omdb_api_config()).decode("utf-8")

    # check if movie_name, movie_year and movie_id are provided in the get request
    if request.method == 'GET':
        movie_name = request.args.get('movie_name', "")
        movie_year = request.args.get('movie_year', "")
        movie_id = request.args.get('movie_id', "")

    if request.method == 'POST':
        request_params = request.form
        if request_params:
            movie_name = request_params.get('movie_name', "")
            movie_id = request_params.get('movie_id', "")
            movie_year = request_params.get('movie_year', "")

    if movie_name and movie_year:
        movie_name = re.sub(r'[^\w\s]', '+', movie_name)

    if movie_name:
        extracted_name = re.search(r'(.*)\s\((\d{4})\)', movie_name)
        if extracted_name:
            extracted_name = extracted_name.group(1)
        else:
            extracted_name = re.search(r'(.*)\.(\d{4})\.', movie_name)
            if extracted_name:
                extracted_name = extracted_name.group(1)
            else:
                extracted_name = re.search(r'(.*)-(\d{4})-', movie_name)
                if extracted_name:
                    extracted_name = extracted_name.group(1)
                else:
                    extracted_name = re.search(r'(.*)-(\d{4})', movie_name)
                    if extracted_name and extracted_name.group(2):
                        extracted_name = extracted_name.group(1)
                    else:
                        extracted_name = re.search(r'(.*)\.(\d{4})', movie_name)
                        if extracted_name:
                            extracted_name = extracted_name.group(1)
                        else:
                            extracted_name = movie_name

        movie_year = re.search(r'\d{4}', movie_name)
        if movie_year:
            movie_year = movie_year.group(0)
        else:
            movie_year = ""

        movie_name = re.sub(r'[^\w\s]', '+', extracted_name)

    response_url = "http://www.omdbapi.com/"
    response_params = { "t": movie_name, "i": movie_id, "y": movie_year, "apikey": _key }
    response = requests.get(response_url, params=response_params)

    if response.status_code == 200:
        if response.json()['Response'] == 'False':
            response = search_omdb_movie(movie_name, _key)
            return make_response(jsonify(response), 200)
        else:
            response_dict = response.json()
            return make_response(jsonify(response_dict), 200)

    else:
        return make_response(jsonify({'status': 'error'}), 400)

def search_omdb_movie(movie_name, key):
    response = requests.get("http://www.omdbapi.com/?s=" + movie_name + "&apikey=" + key)
    if response.status_code == 200:
        return response.json()
    else:
        return None

@app.route('/invidious/', methods=['GET'])
def redirect_invidious_request():
    return redirect("https://invidious.jarbasai.online/", code=302)

@app.route('/recipes/search_recipe/', methods=['GET', 'POST'])
def search_recipe():
    _storage = Storage()
    _app_id = base64.b64decode(_storage.set_edamam_recipes_appid_config()).decode("utf-8")
    _app_key = base64.b64decode(_storage.set_edamam_recipes_appkey_config()).decode("utf-8")

    if request.method == 'GET':
        query = request.args.get('query', "")
        count = request.args.get('count', 5)

    if request.method == 'POST':
        request_params = request.form
        query = request_params.get('query', "")
        count = request_params.get('count', 5)

    data = "?q={0}&app_id={1}&app_key={2}&count={3}".format(query, _app_id, _app_key, count)
    method = "GET"
    url = "https://api.edamam.com/search"
    response = requests.request(method,url+data)

    if response:
        return response.json()
    else:
        return make_response(jsonify({'status': 'error'}), 400)
    
@app.route('/wolframalpha/spoken/<string:uuid>', methods=['GET', 'POST'])
def wolfie_spoken(uuid):
    _storage = Storage()
    _app_id = base64.b64decode(_storage.set_wolfram_appid_config()).decode("utf-8")

    query = request.args.get("input") or request.args.get("i")
    units = request.args.get("units") or request.args.get("u")

    if request.method == 'POST':
        request_params = request.form
        if request_params:
            query = request_params.get('input', "") or request_params.get('i', "")
            units = request_params.get('units', "") or request_params.get('u', "")

    if units != "metric":
        units = "imperial"
        
    if request.headers.get('session_challenge') == read_session_challenge():
        if check_if_device_is_registered(uuid):
            url = 'http://api.wolframalpha.com/v1/spoken'
            params = {"appid": _app_id,
                        "i": query,
                        "units": units}
            answer = requests.get(url, params=params).text
            if answer:
                return answer
            else:
                return make_response(jsonify({'status': 'error'}), 400)
        else:
            return make_response(jsonify({'status': 'not authorized'}), 401)
    else:
        return make_response(jsonify({'status': 'invalid session'}), 401)

@app.route('/wolframalpha/simple/<string:uuid>', methods=['GET', 'POST'])
def wolfie_simple(uuid):
    _storage = Storage()
    _app_id = base64.b64decode(_storage.set_wolfram_appid_config()).decode("utf-8")
    query = request.args.get("input") or request.args.get("i")
    units = request.args.get("units") or request.args.get("u")

    if request.method == 'POST':
        request_params = request.form
        if request_params:
            query = request_params.get('input', "") or request_params.get('i', "")
            units = request_params.get('units', "") or request_params.get('u', "")

    if units != "metric":
        units = "imperial"
        
    if request.headers.get('session_challenge') == read_session_challenge():
        if check_if_device_is_registered(uuid):
            url = 'http://api.wolframalpha.com/v1/simple'
            params = {"appid": _app_id,
                        "i": query,
                        "units": units}
            answer = requests.get(url, params=params).text
            
            if answer:
                return answer
            else:
                return make_response(jsonify({'status': 'error'}), 400)
        else:
            return make_response(jsonify({'status': 'not authorized'}), 401)
    else:
        return make_response(jsonify({'status': 'invalid session'}), 401)

@app.route('/wolframalpha/full/<string:uuid>', methods=['GET', 'POST'])
def wolfie_full(uuid):
    _storage = Storage()
    _app_id = base64.b64decode(_storage.set_wolfram_appid_config()).decode("utf-8")
    query = request.args.get("input") or request.args.get("i")
    units = request.args.get("units") or request.args.get("u")
    output = request.args.get("output", "json") or request.args.get("o", "json")

    if request.method == 'POST':
        request_params = request.form
        if request_params:
            query = request_params.get('input', "") or request_params.get('i', "")
            units = request_params.get('units', "") or request_params.get('u', "")
            output = request_params.get('output', "json") or request_params.get('o', "json")

    if request.headers.get('session_challenge') == read_session_challenge():
        if check_if_device_is_registered(uuid):
            url = 'http://api.wolframalpha.com/v2/query'
            params = {"appid": _app_id,
                        "input": query,
                        "output": output,
                        "units": units}

            if output == "json":
                answer = requests.get(url, params=params).json()
            else:
                answer = requests.get(url, params=params)
            
            if answer:
                return answer
            else:
                return make_response(jsonify({'status': 'error'}), 400)
        else:
            return make_response(jsonify({'status': 'not authorized'}), 401)
    else:
        return make_response(jsonify({'status': 'invalid session'}), 401)

@app.route('/geolocate/ip/', methods=['GET', 'POST'])
def geolocate_using_ip_address():
    ip = request.args.get("address", "") or request.args.get("a", "")
    
    if request.method == 'POST':
        request_params = request.form
        if request_params:
            ip = request_params.get('address', "") or request_params.get('a', "")
    
    if not ip or ip in ["0.0.0.0", "127.0.0.1"]:
        ip = requests.get('https://api.ipify.org').text
    
    fields = "status,country,countryCode,region,regionName,city,lat,lon,timezone,query"
    data = requests.get("http://ip-api.com/json/" + ip,
                        params={"fields": fields}).json()
    region_data = {"code": data["region"], "name": data["regionName"],
                   "country": {
                       "code": data["countryCode"],
                       "name": data["country"]}}
    city_data = {"code": data["city"], "name": data["city"],
                 "state": region_data,
                 "region": region_data}
    timezone_data = {"code": data["timezone"],
                     "name": data["timezone"],
                     "dstOffset": 3600000,
                     "offset": -21600000}
    coordinate_data = {"latitude": float(data["lat"]),
                       "longitude": float(data["lon"])}
    
    if city_data and timezone_data and coordinate_data:
        response = make_response(jsonify({'city': city_data,
                                          'timezone': timezone_data,
                                          'coordinates': coordinate_data}), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        return make_response(jsonify({'status': 'error'}), 400)

@app.route('/geolocate/address/', methods=['GET', 'POST'])
def geolocate_using_address():
    _helper = Helper()
    location_query = request.args.get("address", "") or request.args.get("a", "")
    
    if request.method == 'POST':
        request_params = request.form
        if request_params:
            location_query = request_params.get('address', "") or request_params.get('a', "")
            
    if location_query:
        location_data = _helper.geolocate(location_query)
        if location_data:
            response = make_response(jsonify(location_data), 200)
            response.headers['Content-Type'] = 'application/json'
            return response

@app.route('/geolocate/location/config/', methods=['GET', 'POST'])
def gelocate_location_config():
    _helper = Helper()
    location_query = request.args.get("address", "") or request.args.get("a", "")
    
    if request.method == 'POST':
        request_params = request.form
        if request_params:
            location_query = request_params.get('address', "") or request_params.get('a', "")
    
    location = {
        "city": {
            "code": "",
            "name": "",
            "state": {
                "code": "",
                "name": "",
                "country": {
                    "code": "US",
                    "name": "United States"
                }
            }
        },
        "coordinate": {
            "latitude": 37.2,
            "longitude": 121.53
        },
        "timezone": {
            "dstOffset": 3600000,
            "offset": -21600000
        }
    }
        
    if location_query:
        data = _helper.geolocate(location_query)
        location["city"]["code"] = data["city"]
        location["city"]["name"] = data["city"]
        location["city"]["state"]["name"] = data["state"]
        # TODO state code
        location["city"]["state"]["code"] = data["state"]
        location["city"]["state"]["country"]["name"] = data["country"]
        # TODO country code
        location["city"]["state"]["country"]["code"] = data["country"]
        location["coordinate"]["latitude"] = data["lat"]
        location["coordinate"]["longitude"] = data["lon"]

        timezone = _helper.get_timezone(data["lat"], data["lon"])
        location["timezone"]["name"] = data["timezone"]
        location["timezone"]["code"] = timezone
    
        response = make_response(jsonify(location), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        return make_response(jsonify({'status': 'error'}), 400)

@app.route('/geolocate/reverse/', methods=['GET', 'POST'])
def reverse_geolocate():
    _helper = Helper()
    _lat = request.args.get("lat", "") or request.args.get("latitude", "")
    _lon = request.args.get("lon", "") or request.args.get("longitude", "")
    
    if request.method == 'POST':
        _lat = request.form.get("lat", "") or request.form.get("latitude", "")
        _lon = request.form.get("lon", "") or request.form.get("longitude", "")
    
    url = "https://nominatim.openstreetmap.org/reverse"
    details = requests.get(url, params={"lat": _lat, "lon": _lon, "format": "json"}).json()
    address = details.get("address")
    location = {
        "address": details["display_name"],
        "city": {
            "code": address.get("postcode") or "",
            "name": address.get("city") or
                    address.get("village") or
                    address.get("county") or "",
            "state": {
                "code": address.get("state_code") or
                        address.get("ISO3166-2-lvl4") or "",
                "name": address.get("state") or "",
                "country": {
                    "code": address.get("country_code") or "",
                    "name": address.get("country") or "",
                }
            }
        },
        "coordinate": {
            "latitude": details.get("lat") or _lat,
            "longitude": details.get("lon") or _lon
        }
    }
    if "timezone" not in location:
        location["timezone"] = _helper.get_timezone(
            lon=location["coordinate"]["longitude"],
            lat=location["coordinate"]["latitude"])

    if location:
        response = make_response(jsonify(location), 200)
        response.headers['Content-Type'] = 'application/json'
        return response
    else:
        return make_response(jsonify({'status': 'error'}), 400)
    
@app.route('/cgpt/call_request/<string:uuid>', methods=['GET', 'POST'])
def make_cgpt_request(uuid):
    _storage = Storage()
    _api_key = base64.b64decode(_storage.set_cgpt_api_config()).decode("utf-8")
    _def_engine = _storage.set_cgpt_engine_config()
    _prompt = request.args.get("prompt", "") or request.args.get("p", "")
    _stop = request.args.get("stop", "\nHuman: ") or request.args.get("s", "\nHuman: ")
    _engine = request.args.get("engine", _def_engine) or request.args.get("e", _def_engine)
    
    if request.method == 'POST':
        _prompt = request.form.get('prompt', "") or request.form.get('p', "")
        _stop = request.form.get('stop', "\nHuman: ") or request.form.get('s', "\nHuman: ")
        _engine = request.form.get('engine', _def_engine) or request.form.get('e', _def_engine)
        
    if _prompt and _stop and _engine:
        if request.headers.get('session_challenge') == read_session_challenge():
            if check_if_device_is_registered(uuid):
                ai.api_key = _api_key
                response =  ai.Completion().create(prompt=_prompt, engine=_engine, temperature=0.85, 
                                                   top_p=1, frequency_penalty=0,
                                                   presence_penalty=0.7, best_of=2, max_tokens=100, stop=_stop)
                if response:
                    return response.choices[0].text
                else:
                    return make_response(jsonify({'status': 'error'}), 400)
            else:
                return make_response(jsonify({'status': 'not authorized'}), 401)
        else:
            return make_response(jsonify({'status': 'invalid session'}), 401)

@app.route('/send/mail/<string:uuid>', methods=['POST'])
def send_email(uuid):
    _storage = Storage()
    _mail_config = _storage.mail_config()
    _user = base64.b64decode(_mail_config["user"]).decode("utf-8")
    _key = base64.b64decode(_mail_config["key"]).decode("utf-8")
    _host = base64.b64decode(_mail_config["host"]).decode("utf-8")
    _port = base64.b64decode(_mail_config["port"]).decode("utf-8")
    _sender = base64.b64decode(_mail_config["sender"]).decode("utf-8")

    try:
        # check request header for backend
        params = request.form
        if params:
            recipient = float(params.get('recipient', ""))
            subject = float(params.get('subject', ""))
            body = float(params.get('body', ""))

            if request.headers.get('session_challenge') == read_session_challenge():
                if check_if_device_is_registered(uuid):
                    send_smtp(_user, _key, _sender, recipient, subject, body, _host, _port)
                    return make_response(jsonify({'status': 'success'}), 200)
                else:
                    return make_response(jsonify({'status': 'not authorized'}), 401)
            else:
                return make_response(jsonify({'status': 'invalid session'}), 401)
        else:
            return make_response(jsonify({'status': 'invalid data'}), 401)

    except Exception as e:
        print(e)
        return make_response(jsonify({'error': str(e)}), 500)


if __name__ == '__main__':
    app.run(host="127.0.0.2", debug=False)
