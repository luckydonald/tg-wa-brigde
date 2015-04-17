import logging
import threading
from yowsup.layers.auth                        import YowCryptLayer, YowAuthenticationProtocolLayer
from yowsup.layers.coder                       import YowCoderLayer
from yowsup.layers.network                     import YowNetworkLayer
from yowsup.layers.protocol_messages           import YowMessagesProtocolLayer
from yowsup.layers.protocol_media              import YowMediaProtocolLayer
from yowsup.layers.stanzaregulator             import YowStanzaRegulator
from yowsup.layers.protocol_receipts           import YowReceiptProtocolLayer
from yowsup.layers.protocol_acks               import YowAckProtocolLayer
from yowsup.stacks import YowStack
from yowsup.common import YowConstants
from yowsup.layers import YowLayerEvent, YowParallelLayer
from yowsup import env
from pytg2 import Telegram

import config_reader  # force execution
from config_reader import config

CREDENTIALS = (config["wa-phone-number"], config["wa-phone-password"])  # replace with your phone and password in config
LOG_LEVEL = logging.getLevelName(config["log-level"])

if __name__==  "__main__":
	logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger("root")
logger.setLevel(LOG_LEVEL)


from layer import EchoLayer  # import after setting up logger and config_reader.

if __name__==  "__main__":
	layers = (
			EchoLayer,
			YowParallelLayer([YowAuthenticationProtocolLayer, YowMessagesProtocolLayer, YowMediaProtocolLayer, YowReceiptProtocolLayer, YowAckProtocolLayer]),
			YowCoderLayer,
			YowCryptLayer,
			YowStanzaRegulator,
			YowNetworkLayer
		)


	tg = Telegram(telegram=config["tg-cli-path"], pubkey_file=config["tg-cli-pubkey"])
	stack = YowStack(layers)
	stack.setProp(EchoLayer.PROP_TELEGRAM, tg)
	stack.getLayer(-1).start() #EchoLayer, the highest element.
	stack.setProp(YowAuthenticationProtocolLayer.PROP_CREDENTIALS, CREDENTIALS)         #setting credentials
	stack.setProp(YowNetworkLayer.PROP_ENDPOINT, YowConstants.ENDPOINTS[0])    #whatsapp server address
	stack.setProp(YowCoderLayer.PROP_DOMAIN, YowConstants.DOMAIN)
	stack.setProp(YowCoderLayer.PROP_RESOURCE, env.CURRENT_ENV.getResource())          #info about us as WhatsApp client

	#EchoLayer.set_tg(tg)
	#receiver_thread = threading.Thread(target=stack.loop, args=()) #this is the program mainloop
	#receiver_thread.daemon = True  # exit if script reaches end.
	#receiver_thread.start()
	tg.receiver.start()
	while 1:
		stack.broadcastEvent(YowLayerEvent(YowNetworkLayer.EVENT_STATE_CONNECT))   #sending the connect signal
		stack.loop() #this is the program mainloop
		logger.debug("exited loop, reconnecting.")
