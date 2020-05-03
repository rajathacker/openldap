#!/usr/bin/python

import libxml2

d = libxml2.htmlReadFile("names.html", None, 0)

rows = d.xpathEval("//tr")
print len(rows)

for r in rows:
	td = r.xpathEval("td")
	if len(td) != 12: continue
	print td[1].content.strip()

