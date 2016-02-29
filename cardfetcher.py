import traceback
import slackclient
import json
import requests
import time
import sys

def getCard(name):
	queryUrl = "http://api.deckbrew.com/mtg/cards?name=%s" % name
	print queryUrl
	r = requests.get(queryUrl)
	cards = r.json()

	card = cards[0]
	bestMatch = None
	for cardIter in cards:
		pos = cardIter["name"].lower().find(name)
		if bestMatch is None or (pos != -1 and pos < bestMatch):
			bestMatch = pos
			card = cardIter

	mostRecent = card["editions"][0]
	try:
		card["value"] = getCardValue(card["name"], mostRecent["set"].replace(" ", "+"))
	except:
		print "Price fetch threw up"
		traceback.print_exc()
		card["value"] = {"onlineValue": 0, "paperValue": 0}

	return card

def getCardValue(cardName, set):
	url = "http://www.mtggoldfish.com/price/%s/%s" % (set, cardName.replace(" ", "%20"))
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

def getPlaneswalker(dciNumber):
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
		'Referer': 'http://www.wizards.com/Magic/PlaneswalkerPoints/%s' % dciNumber
	}
	data = {"Parameters":{"DCINumber":dciNumber,"SelectedType":"Yearly"}}
	response = requests.post(url, headers=headers, data=json.dumps(data))

	seasons = []

	responseData = json.loads(response.content)
	markup = responseData["ModalContent"]
	searchPosition = markup.find("SeasonRange")

	while searchPosition != -1:
		pointsvalue = "PointsValue\">"
		searchPosition = markup.find(pointsvalue, searchPosition)
		searchPosition += len(pointsvalue)
		endPosition = markup.find("</div>", searchPosition)
		if endPosition != -1:
			value = markup[searchPosition:endPosition]
			seasons.append(int(value))
		searchPosition = markup.find("SeasonRange", searchPosition)

	return {"currentSeason": seasons[0], "lastSeason": seasons[1]}

def getPlaneswalkerByes(walker):
	if walker["currentSeason"] >= 2250 or walker["lastSeason"] >= 2250:
		return 2
	elif walker["currentSeason"] >= 1300 or walker["lastSeason"] >= 1300:
		return 1

	return 0

def emojiFilter(input):
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

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print "Usage: %s [client_secret_file.json]" % sys.argv[0]
	else:
		slackToken = ""
		with open(sys.argv[1]) as clientSecret:
			data = json.loads(clientSecret.read())
			slackToken = data["slackToken"]

		sc = slackclient.SlackClient(slackToken)
		if sc.rtm_connect():

			def handleInput(input):
				try:
					if input.has_key("text"):
						userinput = input["text"].lower()

						cardTrigger = "!card "
						attachments = ""
						text = ""

						if userinput.find(cardTrigger) > -1:
							searchTerm = userinput[userinput.find(cardTrigger) + len(cardTrigger):]
							card = getCard(searchTerm)
							mostRecentPrinting = card["editions"][0]
							valueinfo = ""
							if card["value"]["paperValue"] > 0:
								valueinfo = "\n\nCurrent market price for most recent printing (%s) $%.1f" % (mostRecentPrinting["set"], card["value"]["paperValue"])

							attachments += '[{"image_url":"%s","title":"%s"}]' % (mostRecentPrinting["image_url"], card["name"])
							text += valueinfo

						oracleTrigger = "!oracle "
						if userinput.find(oracleTrigger) > -1:
							searchTerm = userinput[userinput.find(oracleTrigger) + len(oracleTrigger):]
							card = getCard(searchTerm)
							mostRecentPrinting = card["editions"][0]
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
							answer = "%s\t\t%s\n%s\n%s" % (card["name"], emojiFilter(card["cost"]), typeline, emojiFilter(card["text"]))
							valueinfo = ""
							if card.has_key("power") and card.has_key("toughness"):
								answer += "\n*`%s/%s`*" % (card["power"], card["toughness"])
							if card["value"]["paperValue"] > 0:
								valueinfo = "\n\nCurrent market price for most recent printing (%s) - $%.1f (online) $%.1f (paper)" % (mostRecentPrinting["set"], card["value"]["onlineValue"], card["value"]["paperValue"])

							answer += valueinfo
							text += answer

						priceTrigger = "!price "
						if userinput.find(priceTrigger) > -1:
							searchTerm = userinput[userinput.find(priceTrigger) + len(priceTrigger):]
							card = getCard(searchTerm)
							mostRecentPrinting = card["editions"][0]
							answer = "Unable to find price information for %s" % card["name"]
							if card["value"]["paperValue"] > 0:
								answer = "Current market price for most recent printing of %s (%s) - $%.1f (online) $%.1f (paper)" % (card["name"], mostRecentPrinting["set"], card["value"]["onlineValue"], card["value"]["paperValue"])

							text += answer

						pwpTrigger = "!pwp "
						if userinput.find(pwpTrigger) > -1:
							searchTerm = userinput[userinput.find(pwpTrigger) + len(pwpTrigger):]
							planeswalker = getPlaneswalker(searchTerm)
							answer = "DCI# %s has %s points in the current season, %s points last season\nCurrently " % (searchTerm, planeswalker["currentSeason"], planeswalker["lastSeason"])
							byes = getPlaneswalkerByes(planeswalker)
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
					handleInput(reply)
				time.sleep(0.01)
		else:
			print "Connection Failed, invalid token?"
