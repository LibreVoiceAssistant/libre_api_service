
class Storage:
    def __init__(self):
        pass
        
    def set_api_connection_config(self):
        # read entry from file
        try:
            with open("/etc/wapi/wapi.conf", "r") as conf_file:
                return conf_file.read()
        except Exception as e:
            print(e)
            return " "
        
    def set_owm_api_config(self):
        # read entry from file
        try:
            with open("/etc/wapi/owm.conf", "r") as conf_file:
                return conf_file.read()
        except Exception as e:
            print(e)
            return " "