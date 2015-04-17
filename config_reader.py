import json as module_json # load settings file
from DictObject import DictObject  # load settings file

try:
	with open("config.json") as file:
		json_code = module_json.load(file)
		config = DictObject(json_code)
except:
	print("\nLoading Configuration from 'config.json' failed. Does this file exist? \nYou can use the 'config.json.sample' file as a guide.\n\n\n")
	raise