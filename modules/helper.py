import geocoder
from timezonefinder import TimezoneFinder

class Helper:
    def __init__(self):
        pass

    def geolocate(self, address):
        data = {}
        location_data = geocoder.osm(address)
        if location_data.ok:
            location_data = location_data.json
            data["raw"] = location_data
            data["country"] = location_data.get("country")
            data["country_code"] = location_data.get("country_code")
            data["region"] = location_data.get("region")
            data["address"] = location_data.get("address")
            data["state"] = location_data.get("state")
            data["confidence"] = location_data.get("confidence")
            data["lat"] = location_data.get("lat")
            data["lon"] = location_data.get("lng")
            data["city"] = location_data.get("city")

            data["postal"] = location_data.get("postal")
            data["timezone"] = location_data.get("timezone_short")
        return data
    
    def get_timezone(self, latitude, longitude):
        tf = TimezoneFinder()
        return tf.timezone_at(lng=longitude, lat=latitude)