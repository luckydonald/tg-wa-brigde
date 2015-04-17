import os
import tempfile
import threading
import utils #own file
import logging
from pytg2 import Telegram, NoResponse
from pytg2.utils import coroutine
from yowsup.layers.protocol_media.mediauploader import MediaUploader
from yowsup.layers.protocol_messages.protocolentities import TextMessageProtocolEntity
from yowsup.layers.protocol_media.protocolentities import MediaMessageProtocolEntity, RequestUploadIqProtocolEntity, \
	ImageDownloadableMediaMessageProtocolEntity
from yowsup.layers.protocol_receipts.protocolentities import OutgoingReceiptProtocolEntity
from yowsup.layers.protocol_acks.protocolentities import OutgoingAckProtocolEntity
from yowsup.layers.interface import YowInterfaceLayer, ProtocolEntityCallback

from config_reader import config

tg_wa = config["wa-to-tg-relation"]
wa_tg = {v: k for k, v in tg_wa.items()}

tempdir = tempfile.mkdtemp(prefix="de.luckydonald.whatsapp-telegram-bridge.temp.")
logger = logging.getLogger("luckydonald.whatsapp-telegram-bridge.layer")

def tg_to_wa(tg_peer):
	if tg_peer in tg_wa:
		return tg_wa[tg_peer]
	else:
		return config["wa-default-receiver"]


def wa_to_tg(wa_peer):
	if wa_peer in wa_tg:
		return wa_tg[wa_peer]
	else:
		return config["tg-default-receiver"]


class EchoLayer(YowInterfaceLayer):


	###################
	#				  #
	#  WHATSAPP PART  #
	#				  #
	###################

	PROP_TELEGRAM = "de.luckydonald.whatsapp-telegram-bridge.prop.layer.telegram"  # storage key for the tg instance

	instance = None
	tg = None

	def __init__(self):
		super().__init__()
		EchoLayer.instance = self
		#print("All Loggers: %s" % str())


	@ProtocolEntityCallback("message")
	def onMessage(self, incoming):
		if incoming.isGroupMessage():
			# wa_peer = "1111111111111-%s" % incoming.getFrom().split("-")[-1]
			wa_peer = incoming.getFrom()
		else:
			wa_peer = incoming.getFrom()
		user_str = self.text_wa_to_str(incoming.getNotify())
		tg_peer = wa_to_tg(wa_peer)

		s = self.tg.sender
		receipt = OutgoingReceiptProtocolEntity(incoming.getId(), incoming.getFrom())
		logger.debug(">>%s<<" % str(incoming))

		msg = "<lol>"


		# MEDIA
		if incoming.getType() == "media":
			# MEDIA IMAGE
			if incoming.getMediaType() == "image":  # ('audio', 'image', 'video', 'vcard', 'location')
				url = incoming.getMediaUrl()  #todo DL
				file = utils.download_file(url=url,temp_dir=tempdir)
				try:
					s.send_msg(tg_peer, "{user}: [photo]{caption}:".format(user=user_str, caption=(
						" \"%s\"" % self.text_wa_to_str(incoming.getCaption()).strip()) if incoming.getCaption() else ""))
				except NoResponse:
					pass
				try:
					s.send_photo(tg_peer, file)
				except NoResponse:
					pass
			# MEDIA LOCATION
			elif incoming.getMediaType() == "location":
				msg = "{name}\n" \
					  "Latitude: {lat}\n" \
					  "Longitude: {long}\n".format(lat=incoming.getLatitude(), long=incoming.getLongitude(), name=(
					"\"%s\"" % self.text_wa_to_str(incoming.getLocationName()).strip() if incoming.getLocationName() else ""))
				try:
					s.send_msg(tg_peer, "{user}:".format(user=user_str))
				except NoResponse:
					pass
				try:
					s.send_location(tg_peer, float(incoming.getLatitude()), float(incoming.getLongitude()))
				except NoResponse:
					pass
				try:
					s.send_msg(tg_peer, msg)
				except NoResponse:
					pass

			else:
				msg = "{user}: [Unknown file '{type}']\n{dump}".format(user=user_str, type=incoming.getMediaType(),
																	   dump=self.text_wa_to_str(str(incoming)))
				try:
					s.send_msg(tg_peer, msg)
				except NoResponse:
					pass
		# TEXT
		elif incoming.getType() == "text":
			txt = self.text_wa_to_str(incoming.getBody())
			msg = "{user}: {msg}".format(user=user_str, msg=txt)
			try:
				s.send_msg(tg_peer, msg)
			except NoResponse:
				pass
		# UNKNOWN
		else:
			msg = "{user}: [Unknown '{type}']\n{dump}".format(user=user_str, type=incoming.getType(),
															  dump=str(incoming))
			try:
				s.send_msg(tg_peer, msg)
			except NoResponse:
				pass
		logger.debug("=>%s<=" % str(msg))

		self.toLower(receipt)

	@ProtocolEntityCallback("receipt")
	def onReceipt(self, entity):
		ack = OutgoingAckProtocolEntity(entity.getId(), "receipt", "delivery", entity.getFrom())
		self.toLower(ack)

	@ProtocolEntityCallback("chatstate")
	def onChatstate(self, entity):
		logger.info("chatstate: %s" % str(entity))


	# image upload stuff.
	def sendImage(self, imagePath, receiver_jid):
		logger.debug("Sending image to {jid} ({path})".format(jid=receiver_jid, path=imagePath))
		requestUploadEntity = RequestUploadIqProtocolEntity("image", filePath = imagePath)
		self._image_upload_receiver_jid = receiver_jid

		# lambda to add jid and path parameters to the function.
		onRequestUploadResultFunction = lambda successEntity, originalEntity: self.onRequestUploadResult(receiver_jid, imagePath, successEntity, originalEntity)
		onRequestUploadErrorFunction = lambda errorEntity, originalEntity: self.onRequestUploadError(receiver_jid, imagePath, errorEntity, originalEntity)
		self._sendIq(requestUploadEntity, onRequestUploadResultFunction, onRequestUploadErrorFunction)

	def onRequestUploadResult(self, receiver_jid, imagePath, resultRequestUploadIqProtocolEntity, requestUploadIqProtocolEntity):
		mediaUploader = MediaUploader(self._image_upload_receiver_jid, self.getOwnJid(), imagePath,
									  resultRequestUploadIqProtocolEntity.getUrl(),
									  resultRequestUploadIqProtocolEntity.getResumeOffset(),
									  self.onUploadSuccess, self.onUploadError, self.onUploadProgress)
		mediaUploader.start()

	def onRequestUploadError(self,receiver_jid, imagePath, errorRequestUploadIqProtocolEntity, requestUploadIqProtocolEntity):
		logger.error("Error requesting upload url for %s" % imagePath)

	def onUploadSuccess(self, filePath, receiver_jid, url):
		#convenience method to detect file/image attributes for sending, requires existence of 'pillow' library
		entity = ImageDownloadableMediaMessageProtocolEntity.fromFilePath(filePath, url, None, receiver_jid)
		self.toLower(entity)

	def onUploadError(self, filePath, jid, url):
		logger.error("Upload file failed!")

	def onUploadProgress(self, filePath, jid, url, progress):
		logger.debug("%s => %s, %d%% \r" % (os.path.basename(filePath), jid, progress))

	###################
	#				  #
	#  TELEGRAM PART  #
	#				  #
	###################

	def start_tg_routine(self):
		self.tg.receiver.message(self.tg_messages())

	download_list = {}
	@coroutine
	def tg_messages(self):
		try:
			while 1:
				message = (yield)
				logger.debug(str(message))
				if message.event == "message":
					# MESSAGE
					if message.own:
						continue
					user_str, wa_peer = self.get_tg_meta_from_message(message)
					# logger.debug("{user} ({tg_peer} > {wa_peer}): {msg}".format(user=user_str, tg_peer=tg_peer, wa_peer=wa_peer, msg=message))
					if "freshness" in message:
						if not message.freshness in ['startup','new']: # 'startup' or 'new', not 'old'
							continue
					if message.event == "message":
						# TEXT #
						if "text" in message and message.text and message.text is not None:
							txt = "{user}: {msg}".format(user=user_str, msg=message.text)
							reply = TextMessageProtocolEntity(txt.encode("utf-8"), to=wa_peer)
							self.toLower(reply)
						# IMAGE #
						elif "media" in message and message.media and message.media is not None:
							self.download_list[message.id] = message
				elif message.event == "download":
					if not message.id in self.download_list:
						logger.warning("Something downloaded: {msg}".format(msg=str(message)))
						continue
					message += self.download_list[message.id]  # add stored meta information.
					if message.own:
						continue
					user_str, wa_peer = self.get_tg_meta_from_message(message)
					if not "type" in message.media:
						raise False
					txt = "<placeholder>"
					if message.media.type=="photo":
						txt = "{user}: [image]".format(user=user_str)
						self.sendImage(message.file, wa_peer)
					elif message.media.type == "document":
						if message.media.document == "image":
							self.sendImage(message.file, wa_peer)
							txt = "{user}: [image]{file_name}".format(user=user_str, file_name=(" %s" % message.media.caption if "caption" in message.media else ""))
						else:
							txt = "{user}: [{doc} document]{file_name}\n(Not supported by Whatsapp.)".format(user=user_str, doc=(message.media.mime if "mime" in message.media else message.media.document), file_name=(" %s" % message.media.caption if "caption" in message.media else ""))
					else:
						# unhandled type, or unsupported by WA
						txt = "{user}: [{type}]".format(user=user_str, type=message.media.type)
					reply = TextMessageProtocolEntity(self.text_str_to_wa(txt), to=wa_peer)
					self.toLower(reply)
					#self.toLower(reply2)
		except GeneratorExit:
			logger.warn("GeneratorExit!")

	def get_tg_meta_from_message(self, message):
		if "peer" in message and message.peer:
			tg_peer = message.peer.cmd
		else:
			tg_peer = message.sender.cmd
		user_str = "{user}{forward_user}".format(user=message.sender.print_name, forward_user= (" [forwarded from {user}]".format(user=message.sender.print_name) if message.forward else ""))  # group=message.sender.print_name
		wa_peer = tg_to_wa(tg_peer)
		return (user_str, wa_peer)

	def text_wa_to_str(self, text):
		return text.encode("ISO 8859-1").decode("utf-8")

	def text_str_to_wa(self, text):
		return text.encode("utf-8").decode("ISO 8859-1")

	def start(self):
		if not self.tg:
			self.tg = self.getProp(self.__class__.PROP_TELEGRAM)
			receiver_thread = threading.Thread(target=self.start_tg_routine, args=())
			receiver_thread.daemon = True  # exit if script reaches end.
			receiver_thread.start()
