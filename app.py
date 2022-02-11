import os
import asyncio
import json
from sqlite3 import paramstyle
from urllib import response
from json_database import JsonDatabase
from flask import Flask, render_template, jsonify, request, make_response

from weather import WeatherAPI, WeatherOWM
import datetime
import uuid as uuid_challenge
import threading

app = Flask(__name__)
device_registry = JsonDatabase('/tmp/ovos_api.json')
weather_app_owm = WeatherOWM()
weather_app_wapi = WeatherAPI()
weather_app_wapi_manger = weather_app_wapi.w_api
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

@app.route('/weather/generate_current_weather_report/<string:uuid>/<string:location>', methods=['GET'])
def generate_current_weather_report(uuid, location):
    try:
        # check request header for backend
        backend = request.headers.get('backend')
        selected_backend = None
        
        if backend:
            selected_backend = backend
        else:
            selected_backend = 'WAPI'
                        
        # check request header for session challenge
        if request.headers.get('session_challenge') == read_session_challenge(): 
            # search the list of dictionaries if the uuid key has the same value as the uuid parameter
            if check_if_device_is_registered(uuid):
                if selected_backend == "OWM":
                    current_report = loop.run_until_complete(weather_app_owm.manager.weather_at_place(location))
                else:  
                    current_report = loop.run_until_complete(weather_app_wapi_manger.current(location))
                    
                response = make_response(current_report.json(), 200)
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

@app.route('/weather/generate_forecast_weather_report/<string:uuid>/<string:location>', methods=['GET'])
def generate_forecast_weather_report(uuid, location):
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
                    forecast_report = loop.run_until_complete(weather_app_owm.manager.forecast_at_place(location))
                else:
                    forecast_report = loop.run_until_complete(weather_app_wapi_manger.forecast(location))
                return make_response(forecast_report.json(), 200)
            else:
                return make_response(jsonify({'status': 'error'}), 400)
        else:
            return make_response(jsonify({'status': 'error'}), 400)
    except Exception as e:
        print(e)
        return make_response(jsonify({'error': str(e)}), 500)
        
@app.route('/weather/generate_hourly_weather_report/<string:uuid>/<string:location>', methods=['GET'])
def generate_hourly_weather_report(uuid, location):
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
                    hourly_report = loop.run_until_complete(weather_app_owm.manager.hourly_forecast(location))
                else:
                    hourly_report = loop.run_until_complete(weather_app_wapi_manger.day(location, datetime.date.today()))
                return make_response(hourly_report.json(), 200) 
            else:
                return make_response(jsonify({'status': 'error'}), 400)
        else:
            return make_response(jsonify({'status': 'error'}), 400)

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
                    hourly_report = loop.run_until_complete(weather_app_wapi_manger.day(location, datetime.datetime.strptime(date, '%Y-%m-%d').date()))
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
            
        if request.headers.get('session_challenge') == read_session_challenge():
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

if __name__ == '__main__':
    app.run(host="0.0.0.0", debug=True)