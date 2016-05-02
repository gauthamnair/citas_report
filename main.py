
def chunkBySeparator(xs, isSeparator):
	chunks = []
	currentChunk = []
	for x in xs:
		if isSeparator(x):
			if len(currentChunk) > 0:
				chunks.append(currentChunk)
				currentChunk = []
		else:
			currentChunk.append(x)
	if len(currentChunk) > 0:
		chunks.append(currentChunk)
	return chunks

def parseRecordToDict(lines):
	res = dict()
	currentKey = None
	for line in lines:
		keyPart = line[0:3]
		value = line[3:]
		if keyPart == "   ":
			if currentKey != None:
				res[currentKey].append(value)
		else:
			currentKey = keyPart[0:2]
			res[currentKey] = [value]
	return res

def isIgnoredOrSeparatorLine(x):
	return ((x == "ER") 
		or (x.strip() == "") 
		or (x == "EF") 
		# or (x.startswith("FN")) 
		# or (x.startswith("VR"))
		)

def readCiting():
	files = [
		"data/citing_1001_1500.txt",
		"data/citing_1501_2000.txt",
		"data/citing_1_500.txt",
		"data/citing_2001_2493.txt",
		"data/citing_501_1000.txt",
	]
	# files = ["data/citing_1_500.txt",]
	res = []
	for f in files:
		res.extend(x.rstrip("\n") for x in open(f) if x.strip() != "")
	return chunkBySeparator(res, isIgnoredOrSeparatorLine)

def readPapers():
	fileName = "data/papers_time_sorted.txt"
	res = [x.rstrip("\n") for x in open(fileName) if x.strip() != ""]
	return chunkBySeparator(res, isIgnoredOrSeparatorLine)

def mapValues(dicts, f):
	for x in dicts:
		yield {k:f(v) for (k,v) in x.items()}

def dictSum(dicts, valueAdder = lambda x,y: x + y):
	res = {}
	for x in dicts:
		for k in x:
			if k in res:
				res[k] = valueAdder(res[k], x[k])
			else:
				res[k] = x[k]
	return res

def getDOIKey(x):
	if "DI" in x:
		return ("DOI", x["DI"][0])
	else:
		return None

def getJ9BasedKey(x):
	if "J9" in x and "VL" in x and "BP" in x:
		# firstAuthor = x["AU"][0] # present in all records
		# pubYear = x["PY"][0] # present in all records
		journal = x["J9"][0]
		volume = "V" + x["VL"][0]
		page = "P" + x["BP"][0]
		return ("J9", (journal, volume, page))
	else:
		return None

def getSOBasedKey(x):
	if "SO" in x and "BP" in x:
		pubYear = x["PY"][0] # present in all records
		so = ", ".join(x["SO"])
		page = "P" + x["BP"][0]
		return ("SO", (pubYear, so, page))
	else:
		return None

uidGenerators = [getDOIKey,getJ9BasedKey,getSOBasedKey]

def getUID(x):
	for g in uidGenerators:
		uid = g(x)
		if uid != None:
			return uid
	else:
		return None

def assignUID(xs):
	itemsWithoutUID = []
	uidItems = {}
	for x in xs:
		uid = getUID(x)
		if uid == None:
			itemsWithoutUID.append(x)
		else:
			if uid in uidItems:
				uidItems[uid].append(x)
			else:
				uidItems[uid] = [x,]
	return {"withUID": uidItems, "withoutUID": itemsWithoutUID}

citing = [parseRecordToDict(z) for z in readCiting()]
papers = [parseRecordToDict(z) for z in readPapers()]
print(len(citing))
fieldCounts = dictSum(mapValues(citing, lambda x: 1))

# find fields that are always present:
maxFieldCounts = max(fieldCounts.values())
commonFields = {k for k in fieldCounts if fieldCounts[k] == maxFieldCounts}

# are AF and AU different?
z = [r for r in citing if r["AU"] != r["AF"]]

# types of items:
sumByArticleType = dictSum({x['DT'][0]:1} for x in citing)


# uidAssigned = assignUID(citing)
# print(len(uidAssigned["withoutUID"]))
# duplicatedUID = {k:v for (k,v) in uidAssigned["withUID"].items() if len(v) > 1}


print(len(papers))
assignmentResult = assignUID(papers)
print(len(assignmentResult["withoutUID"]))
duplicatedUID = {k:v for (k,v) in assignmentResult["withUID"].items() if len(v) > 1}
assert(len(duplicatedUID) == 0)
papersByUID = {k:v[0] for (k,v) in assignmentResult["withUID"].items()}

dictSum({k: 1} for (k, v) in papersByUID.keys())

def getDOIUIDFromCR(cr):
	lastPart = cr.split(", ")[-1]
	if lastPart.startswith("DOI "):
		doi = lastPart[4:]
		return ("DOI", doi)
	else:
		return None

def crMatcherByDOI(papersByUID):
	def matcher(cr):
		doiUID = getDOIUIDFromCR(cr)
		if doiUID != None and doiUID in papersByUID:
			return doiUID
		else:
			return None
	return matcher

def paperToCRGuess(x):
	parts = []
	firstAuthor = x["AU"][0] # present in all records
	parts.append(firstAuthor.replace(",",""))
	pubYear = x["PY"][0] # present in all records
	parts.append(pubYear)
	if "J9" and "VL" in x:
		parts.append(", ".join(x["J9"]))
		parts.append("V" + x["VL"][0])
	elif "SO" in x:
		# this one is untested!
		parts.append(", ".join(x["SO"]))
	if "BP" in x:
		parts.append("P" + x["BP"][0])
	if "DI" in x:
		parts.append("DOI " + x["DI"][0])
	return ", ".join(parts).lower() # lowercased!

def constructiveMatcher(papersByUID):
	crGuesses = [(paperToCRGuess(paper),uid) for (uid,paper) in papersByUID.items()]
	assert(len({crGuess for (crGuess, uid) in crGuesses}) == len(crGuesses))
	uidByCRGuess = dict(crGuesses)
	def matcher(cr):
		stripped = cr.strip().lower()
		return uidByCRGuess.get(stripped, None)
	return matcher

def combinedMatchers(*matchers):
	fs = list(matchers)
	def matcher(cr):
		for f in fs:
			m = f(cr)
			if m != None:
				return m
		else:
			return None
	return matcher

def calcCitations(papersByUID, citing):
	res = {uid:[] for uid in papersByUID}
	# matcher = crMatcherByDOI(papersByUID)
	matcher = combinedMatchers(
		crMatcherByDOI(papersByUID),
		constructiveMatcher(papersByUID))
		
	for record in citing:
		crs = record.get("CR",[])
		alreadyCited = set()
		for cr in crs:
			uid = matcher(cr)
			if uid != None and uid not in alreadyCited:
				res[uid].append(record)
				alreadyCited.add(uid)
	return res

citationsByUID = calcCitations(papersByUID, citing)

citationCountByUID = {uid:len(rs) for (uid, rs) in citationsByUID.items()}
print(sum(len(rs) for rs in citationsByUID.values()))
# def crMatcherByJ9(cr, papersByUID):


def renderPaper(p):
	parts = []
	parts.append("; ".join(p["AU"]) + ":")
	parts.append(" ".join(p["TI"]) + ",")
	if "J9" and "VL" in p:
		parts.append(", ".join(p["J9"]))
		parts.append(p["VL"][0])
	elif "SO" in p:
		# this one is untested!
		parts.append(", ".join(p["SO"]))
	parts.append("(" + p["PY"][0] + ")")
	if "BP" in p:
		parts.append("p." + p["BP"][0])
	if "DI" in p:
		parts.append(p["DI"][0])
	return " ".join(parts)

countByYear = {}
for p in papers:
	uid = getUID(p)
	citations = citationsByUID.get(uid, [])
	for cr in citations:
		countByYear[cr["PY"][0]] = countByYear.get(cr["PY"][0], 0) + 1


outLines = []
outLines.append(u"PK Nair UNAM")
outLines.append("citas anuales, sin auto-citas:")
for (year, citations) in reversed(sorted(list(countByYear.items()), key = lambda x: int(x[0]))):
	outLines.append(year + "\t" + str(citations))

outLines.append("")
for p in papers:
	outLines.append("__________________________________________")
	uid = getUID(p)
	assert(uid != None)
	outLines.append(renderPaper(p))
	citedBy = list(reversed(sorted(citationsByUID.get(uid, []), key = lambda x : x["PY"])))
	outLines.append("")
	outLines.append("Fue citado por: " + str(len(citedBy)))
	reverseCitationNumber = reversed([x+1 for x in range(len(citedBy))])
	for (citingP, num) in zip(citedBy, reverseCitationNumber):
		outLines.append("Cita " + str(num) + ":\t" + renderPaper(citingP))
	outLines.append("")
	outLines.append("")

import io

with io.open("data/out.txt", "w", newline="\r\n") as f:
	f.writelines(unicode(l + "\n") for l in outLines)




