import datetime
import pyowm

import base64
from modules.storage import Storage

import pytz
from tzwhere import tzwhere

from weather_api import WeatherAPI as PyWeatherAPI 

class WeatherAPI:
    def __init__(self) -> None:
        self._storage = Storage()
        _key = base64.b64decode(self._storage.set_api_connection_config()).decode("utf-8")
        self.w_api = PyWeatherAPI(_key)
            
class WeatherOWM:
    
    def __init__(self) -> None:
        self._storage = Storage()
        self._owm = pyowm.OWM(base64.b64decode(self._storage.set_owm_api_config()).decode("utf-8"))
        self.manager = self._owm.weather_manager()
    
    def map_to_owm_report_current(self, current):
        return {
           "clouds":  current["clouds"],
           "dewPoint": current["dewpoint"],
           "dt": current["reference_time"],
           "feelsLike": current["temperature"]["feels_like"],
           "humidity": current["humidity"],
           "pressure": current["pressure"]["press"],
           "sunrise": current["sunrise_time"],
           "sunset": current["sunset_time"],
           "temp": current["temperature"]["temp"],
           "uvi": current["uvi"],
           "visibility": current["visibility_distance"],
           "weather": [
            {
                "description": current["detailed_status"],
                "icon": current["weather_icon_name"],
                "id": current["weather_code"],
                "main": current["status"],
            }
            ],
           "windSpeed": current["wind"]["speed"],
           "windDeg": current["wind"]["deg"]           
        }
        
    def map_to_owm_daily(self, forecast_daily):
        daily_new = []
        for forecast_type in forecast_daily:      
        # map keys from forecast_type to formated_type
            daily = {
                "clouds": forecast_type["clouds"],
                "dewPoint": forecast_type["dewpoint"],
                "dt": forecast_type["reference_time"],
                "feelsLike": {
                    "day": forecast_type["temperature"]["day"],
                    "eve": forecast_type["temperature"]["eve"],
                    "morn": forecast_type["temperature"]["morn"],
                    "night": forecast_type["temperature"]["night"]
                },
                "humidity": forecast_type["humidity"],
                "pressure": forecast_type["pressure"]["press"],
                "moonphase": "",
                "moonrise": "",
                "moonset": "",
                "pop": forecast_type["precipitation_probability"],
                "sunrise": forecast_type["sunrise_time"],
                "sunset": forecast_type["sunset_time"],
                "temp": {
                    "day": forecast_type["temperature"]["day"],
                    "eve": forecast_type["temperature"]["eve"],
                    "max": forecast_type["temperature"]["max"],
                    "min": forecast_type["temperature"]["min"],
                    "morn": forecast_type["temperature"]["morn"],
                    "night": forecast_type["temperature"]["night"]
                },
                "uvi": forecast_type["uvi"],
                "weather": [{
                "description": forecast_type["detailed_status"],
                "icon": forecast_type["weather_icon_name"],
                "id": forecast_type["weather_code"],
                "main": forecast_type["status"]
                }],
                "windDeg": forecast_type["wind"]["deg"],
                "windGust": forecast_type["wind"]["gust"],
                "windSpeed": forecast_type["wind"]["speed"]
            }
            daily_new.append(daily)
            
        return daily_new

    def map_to_owm_hourly(self, forecast_hourly):
        hourly_new = []
        for forecast_type in forecast_hourly:
            hourly = {
                "clouds": forecast_type["clouds"],
                "dewPoint": forecast_type["dewpoint"],
                "dt": forecast_type["reference_time"],
                "feelsLike": forecast_type["temperature"]["feels_like"],
                "humidity": forecast_type["humidity"],
                "pop": forecast_type["precipitation_probability"],
                "pressure": forecast_type["pressure"]["press"],
                "temp": forecast_type["temperature"]["temp"],
                "uvi": forecast_type["uvi"],
                "visibility": forecast_type["visibility_distance"],
                "weather": [{
                    "description": forecast_type["detailed_status"],
                    "icon": forecast_type["weather_icon_name"],
                    "id": forecast_type["weather_code"],
                    "main": forecast_type["status"]
                    }],
                "windDeg": forecast_type["wind"]["deg"],
                "windGust": forecast_type["wind"]["gust"],
                "windSpeed": forecast_type["wind"]["speed"]            
            }
            hourly_new.append(hourly)
            
        return hourly_new
    
    def get_timezone_details(self, lat, lon):
        tz = tzwhere.tzwhere()
        timezone_str = tz.tzNameAt(lat, lon)
        timezone = pytz.timezone(timezone_str)
        dt = datetime.datetime.now()
        timezone_offset = timezone.utcoffset(dt)
        # convert timezone offset to seconds
        timezone_offset_seconds = timezone_offset.total_seconds()
        return {"timezone": timezone_str, "offset": timezone_offset_seconds, "lat": lat, "lon": lon}
        
    def generate_one_report(self, current_obj, daily_obj, hourly_obj, timezone_obj):
        return {
            "current": current_obj,
            "daily": daily_obj,
            "hourly": hourly_obj,
            "timezone": timezone_obj["timezone"],
            "timezoneOffset": timezone_obj["offset"],
            "lat": timezone_obj["lat"],
            "lon": timezone_obj["lon"]           
        }