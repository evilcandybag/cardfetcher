import traceback
import slackclient
import json
import requests
import time

slack_token = ""

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

def get_planeswalker(dci_number):
	url = "http://www.wizards.com/Magic/PlaneswalkerPoints/JavaScript/GetPointsHistoryModal"
	headers = {
		'Pragma': 'no-cache',
		'Origin': 'http://www.wizards.com',
		'Accept-Encoding': 'gzip, deflate',
		'Accept-Language': 'en-US,en;q=0.8,de;q=0.6,sv;q=0.4',
		'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.109 Safari/537.36',
		'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
		'Accept': '*/*',
		'Cache-Control': 'no-cache',
		'X-Requested-With': 'XMLHttpRequest',
		'Cookie': 'f5_cspm=1234; BIGipServerWWWPWPPOOL01=353569034.20480.0000; __utmt=1; BIGipServerWWWPool1=3792701706.20480.0000; PlaneswalkerPointsSettings=0=0&lastviewed=9212399887; __utma=75931667.1475261136.1456488297.1456488297.1456488297.1; __utmb=75931667.5.10.1456488297; __utmc=75931667; __utmz=75931667.1456488297.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none)',
		'Connection': 'keep-alive',
		'Referer': 'http://www.wizards.com/Magic/PlaneswalkerPoints/%s' % dci_number
	}
	data = {"Parameters":{"DCINumber":dci_number,"SelectedType":"Yearly"}}
	response = requests.post(url, headers=headers, data=json.dumps(data))

	seasons = []

	response_data = json.loads(response.content)
	markup = response_data["ModalContent"]
	search_position = markup.find("SeasonRange")

	while search_position != -1:
		pointsvalue = "PointsValue\">"
		search_position = markup.find(pointsvalue, search_position)
		search_position += len(pointsvalue)
		end_position = markup.find("</div>", search_position)
		if end_position != -1:
			value = markup[search_position:end_position]
			seasons.append(int(value))
		search_position = markup.find("SeasonRange", search_position)

	return {"current_season": seasons[0], "last_season": seasons[1]}

def get_planeswalker_byes(walker):
	if walker["current_season"] >= 2250 or walker["last_season"] >= 2250:
		return 2
	elif walker["current_season"] >= 1300 or walker["last_season"] >= 1300:
		return 1

	return 0

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
				attachments = ""
				text = ""

				if userinput.find(card_trigger) > -1:
					search_term = userinput[userinput.find(card_trigger) + len(card_trigger):]
					card = get_card(search_term)
					most_recent_printing = card["editions"][0]
					valueinfo = ""
					if card["value"]["paperValue"] > 0:
						valueinfo = "\n\nCurrent market price for most recent printing (%s) $%.1f" % (most_recent_printing["set"], card["value"]["paperValue"])

					attachments += '[{"image_url":"%s","title":"%s"}]' % (most_recent_printing["image_url"], card["name"])
					text += valueinfo

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
					text += answer

				price_trigger = "!price "
				if userinput.find(price_trigger) > -1:
					search_term = userinput[userinput.find(price_trigger) + len(price_trigger):]
					card = get_card(search_term)
					most_recent_printing = card["editions"][0]
					answer = "Unable to find price information for %s" % card["name"]
					if card["value"]["paperValue"] > 0:
						answer = "Current market price for most recent printing of %s (%s) - $%.1f (online) $%.1f (paper)" % (card["name"], most_recent_printing["set"], card["value"]["onlineValue"], card["value"]["paperValue"])

					text += answer

				pwp_trigger = "!pwp "
				if userinput.find(pwp_trigger) > -1:
					search_term = userinput[userinput.find(pwp_trigger) + len(pwp_trigger):]
					planeswalker = get_planeswalker(search_term)
					answer = "DCI# %s has %s points in the current season, %s points last season\nCurrently " % (search_term, planeswalker["current_season"], planeswalker["last_season"])
					byes = get_planeswalker_byes(planeswalker)
					if not byes:
						answer += "not eligible for GP byes"
					else:
						answer += "eligible for %d GP byes" % byes

					text += answer

				if text or attachments:
					sc.api_call(
						"chat.postMessage",
						channel=input["channel"],
						attachments=attachments,
						text=text,
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
