import traceback
import slackclient
import json
import requests
import time

slack_token = "INSERT YOUR TOKEN HERE"

def get_card(name):
	query_url = "http://api.deckbrew.com/mtg/cards?name=%s" % name
	print query_url
	r = requests.get(query_url)
	cards = r.json()

	card = cards[0]
	best_match = None
	for card_iter in cards:
		pos = card_iter["name"].lower().find(name)
		if best_match is None or (pos != -1 and pos < best_match):
			best_match = pos
			card = card_iter

	most_recent = card["editions"][0]
	try:
		card["value"] = get_card_value(card["name"], most_recent["set"].replace(" ", "+"))
	except:
		print "Price fetch threw up"
		traceback.print_exc()
		card["value"] = {"onlineValue": 0, "paperValue": 0}

	return card

def get_card_value(card_name, set):
	url = "http://www.mtggoldfish.com/price/%s/%s" % (set, card_name.replace(" ", "%20"))
	print url
	data = requests.get(url).content

	def findValue(data, realm):
		pos = data.find("price-box %s" % realm)
		marker = "price-box-price"
		pos = data.find(marker, pos)
		pos += len(marker) + 2
		endPos = data.find("<", pos)
		return float(data[pos:endPos])

	onlineValue = -1
	paperValue = -1
	try:
		onlineValue = findValue(data, "online")
	except:
		pass
	try:
		paperValue = findValue(data, "paper")
	except:
		pass

	return {"onlineValue": onlineValue, "paperValue": paperValue}

def emoji_filter(input):
	ret = input.replace("{", ":_")
	ret = ret.replace("}", "_:")
	lastpos = None
	while ret.rfind(":_", 0, lastpos) != -1:
		lastpos = ret.rfind(":_", 0, lastpos)
		start = lastpos + 2
		end = ret.rfind("_:")
		content = ret[start:end]
		content = content.lower()
		content = content.replace("/", "")
		ret = ret[:start] + content + ret[end:]

	return ret

sc = slackclient.SlackClient(slack_token)
if sc.rtm_connect():

	def handle_input(input):
		try:
			if input.has_key("text"):
				userinput = input["text"].lower()

				card_trigger = "!card "
				if userinput.find(card_trigger) > -1:
					search_term = userinput[userinput.find(card_trigger) + len(card_trigger):]
					card = get_card(search_term)
					most_recent_printing = card["editions"][0]
					valueinfo = ""
					if card["value"]["paperValue"] > 0:
						valueinfo = "\n\nCurrent market price for most recent printing (%s) $%.1f" % (most_recent_printing["set"], card["value"]["paperValue"])

					sc.api_call(
						"chat.postMessage",
						channel=input["channel"],
						attachments='[{"image_url":"%s","title":"%s"}]' % (most_recent_printing["image_url"], card["name"]),
						text=valueinfo,
						as_user=True)

				oracle_trigger = "!oracle "
				if userinput.find(oracle_trigger) > -1:
					search_term = userinput[userinput.find(oracle_trigger) + len(oracle_trigger):]
					card = get_card(search_term)
					most_recent_printing = card["editions"][0]
					typeline = ""
					if card.has_key("supertypes"):
						for supertype in card["supertypes"]:
							typeline += supertype.capitalize() + " "
					if card.has_key("types"):
						for cardtype in card["types"]:
							typeline += cardtype.capitalize() + " "
						if card.has_key("subtypes"):
							typeline += "- "
					if card.has_key("subtypes"):
						for subtype in card["subtypes"]:
							typeline += subtype.capitalize() + " "
					answer = "%s\t\t%s\n%s\n%s" % (card["name"], emoji_filter(card["cost"]), typeline, emoji_filter(card["text"]))
					valueinfo = ""
					if card.has_key("power") and card.has_key("toughness"):
						answer += "\n*`%s/%s`*" % (card["power"], card["toughness"])
					if card["value"]["paperValue"] > 0:
						valueinfo = "\n\nCurrent market price for most recent printing (%s) - $%.1f (online) $%.1f (paper)" % (most_recent_printing["set"], card["value"]["onlineValue"], card["value"]["paperValue"])

					answer += valueinfo
					sc.api_call(
						"chat.postMessage",
						channel=input["channel"],
						text=answer,
						as_user=True)

				price_trigger = "!price "
				if userinput.find(price_trigger) > -1:
					search_term = userinput[userinput.find(price_trigger) + len(price_trigger):]
					card = get_card(search_term)
					most_recent_printing = card["editions"][0]
					answer = "Unable to find price information for %s" % card["name"]
					if card["value"]["paperValue"] > 0:
						answer = "Current market price for most recent printing of %s (%s) - $%.1f (online) $%.1f (paper)" % (card["name"], most_recent_printing["set"], card["value"]["onlineValue"], card["value"]["paperValue"])

					sc.api_call(
						"chat.postMessage",
						channel=input["channel"],
						text=answer,
						as_user=True)
		except:
			print "Boink! Exception swallowed :)"
			traceback.print_exc()

	while True:
		for reply in sc.rtm_read():
			handle_input(reply)
		time.sleep(0.01)
else:
	print "Connection Failed, invalid token?"
