import os
from urllib.error import HTTPError
from tempfile import gettempdir
import hashlib
from urllib.request import urlopen


def download_file(url, used_cached=True, temp_dir=None):
	if not temp_dir:
		temp_dir = gettempdir()
	file_name = url.split("/")[-1]
	suffix = file_name.split(".")[-1] # TODO suffix: if no ending? what if .htaccess?
	file_name = str(hashlib.md5(url.encode()).hexdigest()) + "." + suffix
	file_name = os.path.join(temp_dir, file_name)

	if os.path.isfile(file_name):
		if used_cached:
			print("DL: File exists, using cached: %s" % file_name)
			return file_name
		print("DL: File exists, redownloading: %s" % file_name)
	else:
		print("DL: File does not exist, downloading: %s" % file_name)
		if not os.path.exists(os.path.dirname(file_name)):
			print("DL: Download Folder does not exists. Creating.")
			os.makedirs(os.path.dirname(file_name))

	try:
		print("DL: Downloading from %s to %s" % (url, file_name))
		with open(file_name, 'wb') as f:
			f.write(urlopen(url).read())

	except HTTPError as e:
		print("DL: Error in URL '" + url + "'.\n" + str(e))
		file_name = None
	except Exception as e:
		print("DL: Error in Download '" + url + "' to '" + file_name + "'.\n" + str(e))
		file_name = None
	return file_name
