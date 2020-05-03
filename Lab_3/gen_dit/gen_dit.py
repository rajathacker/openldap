#!/usr/bin/python
############################################################################
#
# $Id$
# Bowe Strickland <bowe@redhat.com>
#
# gendit.py: generate sample DIT entries for randomly generated users
# with randomly assigned groups, with fairly complete (randomly generated)
# contact info, jpeg "face" photos, management ("org chart") heirarchies, 
# etc.
#
# has been used to generate 30,000 entries for redhat-ds server.
#
# currently genereates the following tree.  root and ou entries are
# generated (as needed by openldap) if -b is included.
# 
# (suffix)
#	ou=People
#		uid=(useranme)
#		...
#	ou=Groups
#		cn=(primary group for username)
#		...
#		cn=(secondary groups w/ randomly assigned members)
#
###########################################################################

import os, string, re, time
from random import choice, randint, sample, expovariate, random
from popen2 import popen2
from UserDict import DictMixin

def debug(msg): sys.stderr.write("DEBUG: " + msg + os.linesep)
def info(msg): sys.stderr.write("INFO: " + msg + os.linesep)
def warn(msg): sys.stderr.write("WARN: " + msg + os.linesep)

globals = {
	"create_base_entries": 0,
	"datadir": "lists",
	"facedir": "faces",
	"email_domain": "example.com",
	"suffix": "dc=example,dc=com",
	"nusers": 1000,
}

comment_re = re.compile("^\s*#")
def slurp_file(filename):
	return [ a.strip() for a in file(filename) if not comment_re.match(a) ]

class Attribute:

	"""
		Used to store an attribute nave/value pair, and a
		representation style (standard text, base64, ....)
	"""

	def __init__(self, name, value="", separator=":"):

		self.name = name
		self.value = value
		self.separator = separator

	def __str__(self):
		return "%s%s %s" % (self.name, self.separator, self.value)

class Generator: 

	"""
		Used to generate (often random) data, accessed through
		get method.  
	"""

	def get(self, key, entry=None): pass # subclass responsibility

class PoolGenerator(Generator):

	"""
		Randomly select a member of a list.
	"""

	def __init__(self): self.pool = []
	def get(self, key, entry=None): return Attribute(key, choice(self.pool))

class FilePoolGenerator(PoolGenerator):

	"""
		Randomly select a member of a list, with the list initialized from
		the contents of a file.
	"""

	def __init__(self, filename): 
		self.pool = slurp_file(os.path.join(globals["datadir"], filename))

class WeightedPoolGenerator(Generator):

	"""
		Randomly select a key from a hash, with the choice
		weighted by the integer hash value.   the following hash
		would cause bananas to be chosen twice as often a apples.

		weighted_pool {
			'apple': 100,
			'banana': 200,
		}
	
	"""

	def __init__(self, pool=None): 
		self.weighted_pool = pool or {}

	def update_weights(self):
		self.weights = []
		self.n = 0
		for k,v in self.weighted_pool.items():
			self.n += int(v)
			self.weights.append((k, self.n))

	def get(self, key, entry=None):
		if not hasattr(self, "n"): self.update_weights()
		i = randint(1, self.n)
		for value,weight in self.weights:
			if i < weight: break
		return Attribute(key, value)

class WeightedFilePoolGenerator(WeightedPoolGenerator):

	"""
		Randomly select a key from a hash, with the choice
		weighted by the integer hash value.   The hash is 
		initialized by the contents of a file.

		The following file would would cause "mushy bananas" to be chosen 
		twice as often a "apples".

			100 apple
			200 mushy bananas

	"""

	def __init__(self, filename):

		w = {}
		for line in slurp_file(os.path.join(globals["datadir"], filename)):
			weight,value = line.split(None, 1)
			w[value.strip()] = int(weight)

		WeightedPoolGenerator.__init__(self, w)

class StringGenerator(Generator):

	"""
		Regurgitate a string specified on init.
	"""
	def __init__(self, string=""): self.string = string
	def get(self, key, entry=None): return Attribute(key, self.string)

class IntegerGenerator(Generator):

	"""
		Provided a format w/ a bunch of "%d"'s, return a string
		w/ each %d substituted by a random integer [0-9]....
	"""
	def __init__(self, format="%d%d%d"):
		self.format = format
		self.n = self.format.count("%d")

	def get(self, key, entry=None):
		a = []
		for i in range(self.n): a.append(randint(0,9))
		return Attribute(key, self.format % tuple(a))

class CounterGenerator(Generator):

	"""
		maintain a hash of class countes, and return the next
		integer on each get().  Useful for uid's, gid's, etc...
	"""
	counters = {}

	def __init__(self, name, init_value=0):

		if name in self.counters:
			raise IndexError, "%s already a counter" % name
		self.counters[name] = init_value

	def get(self, key, entry=None):

		value = self.counters[key]
		self.counters[key] += 1
		
		return Attribute(key, str(value))

class StreetGenerator(FilePoolGenerator): 

	addr = IntegerGenerator("%d%d%d%d")

	def get(self, key, entry=None):
		a = self.addr.get("addr").value
		b = FilePoolGenerator.get(self, "addr").value
		return Attribute(key, "%s %s" % (a,b))

class AddressGenerator(Generator):

	gstreet = StreetGenerator("streets")
	gstate = FilePoolGenerator("states")
	gcity = FilePoolGenerator("cities")
	gzip = IntegerGenerator("%d%d%d%d%d-%d%d%d%d")

	def get(self, key, entry=None):
		street = self.gstreet.get("").value
		state = self.gstate.get("").value
		city = self.gcity.get("").value
		zip = self.gzip.get("").value
		addr = "%s $ %s, %s %s" % (street, city, state, zip)
		return Attribute(key, addr)

class PasswordGenerator(Generator):

	"""
		generatae a MD5 encrypted password w/ random salt.
		currently, every password is "redhat".

	"""

	def get(self, key, entry=None):
		cmdtmpl = "openssl passwd -1 %s" 
		stdout,stdin = popen2(cmdtmpl % "redhat")
		stdin.close()
		pw = stdout.read().strip()
		stdout.close

		return Attribute(key, "{crypt}" + pw)

class CompositeGenerator(Generator):

	"""
		initialized with a fmt string w/ some '%s's, and
		a list of attributes names (one for each %s), 
		return string composed of substitutions from 
		the entry's specified attribute.

		fmt = "%s %s"
		attrs = [ "givenName", "sn" ]

		would return "elvis presly" (assuming givenName=elvis, 
		sn=presley).

		Useful for deriving attributes from already existing attributes.

	"""

	def __init__(self, fmt, attrlist):
		self.fmt = fmt
		self.attrlist = attrlist

	def get(self, key, entry):
		values = [ entry[a].value for a in self.attrlist ]
		return Attribute(key, self.fmt % tuple(values))

class JpegPhotoGenerator(PoolGenerator):

	"""

		choose a random filename from a given directory,
		returning filename as a file:///absoute/path  

	"""
	def __init__(self):
		self.pool = [ os.path.join(globals["facedir"], i) 
								for i in os.listdir(globals["facedir"]) ]

	def get(self, key, entry=None):
		a = PoolGenerator.get(self, key, entry)
		a.value = "file://%s" %  os.path.abspath(a.value)
		a.separator = ":<"
		return a

class UIDGenerator(Generator):

	""" 
		uid must be 7 bit clean... just drop out any non ascii
		alphanumeric chars.  also, add one char of salt (i.e.,
		middle initial) to help avoid uid collisions.
	"""

	ascii = string.ascii_letters + string.digits + "_"

	def get(self, key, entry):

		gn = entry["givenName"].value
		clean_gn = "".join([ i for i in gn[:3] if i in self.ascii ])
		sn = entry["sn"].value
		clean_sn = "".join([ i for i in sn if i in self.ascii ])
		m = choice(string.ascii_lowercase)
		#n = choice(string.ascii_lowercase)
		#s = string.lower("%s%s%s%s" % (gn[:3], m, n, clean_sn))
		s = string.lower("%s%s%s" % (clean_gn, m, clean_sn))
		return Attribute(key, s)

class DescriptionGenerator(FilePoolGenerator):

	""" 
		Throw together some gibberish chosen from a dictionary.
	"""

	dictionary = "/usr/share/dict/words"

	def __init__(self):
		FilePoolGenerator.__init__(self, self.dictionary)

	def get(self, key, entry=None):
		s = " ".join(sample(self.pool, randint(10,20)))
		return Attribute(key, s)

class HomeDirectoryGenerator(Generator):

	""" 
		Return a "two level" home directory:  /home/e/elvis for elvis.
	"""

	def get(self, key, entry=None):
		uname = entry["uid"].value
		return Attribute(key, "/home/%s/%s" % (uname[0], uname))

class ManagerGenerator(Generator):

	""" 
		given a list of all usernames, throw them into tiers, w/ an 
		exponentially decreasing number of members in each teir.
		Then, for every member, choose a "manager" from one teir up.
	"""

	def __init__(self, nlevels):

		self.nlevels = nlevels

	def init_levels(self, uid_list):

		n = self.nlevels
		self.uid_levels = []
		for i in range(n): self.uid_levels.append({})

		samples = []
		for i in range(len(uid_list)): 
			samples.append(expovariate(1.0))
		biggest = max(samples)

		for u in uid_list:
			uname = u["uid"].value
			bin = samples.pop(0) / (biggest+1) * n
			self.uid_levels[int(bin)][uname] = u
			
		#for i in self.uid_levels: print i.keys()

	def get(self, key, entry):

		n = self.nlevels
		uname = entry["uid"].value

		# i = level of current entry
		for i in range(n):
			if uname in self.uid_levels[i]: break

		# j = level of first populated level above i 
		# (or -1 for the big cheese)
		j = i
		for j in range(i+1,n):
			if len(self.uid_levels[j]): break
		if not (len(self.uid_levels[j])): j = -1

		if j == -1 or j == i: return None
		mlvl = self.uid_levels[j]
		manager = mlvl[choice(mlvl.keys())]

		#print "%d %d %d %s" % (i,j, n, manager)

		return Attribute("manager", manager.dn())

	def dump_levelmap(self, stream):
		for i in range(self.nlevels):
			a = self.uid_levels[i].keys()
			stream.write("%d %d %s\n" % (i, len(a), str(a)))

#########################################################################
#
# object class 'definitions' - note that any derived attrs need to be
# listed after the 'primary' attrs!
#
#########################################################################

class LDAPObjectClass: 

	"""
		A Abstract superclass representing an LDAP object class, with
		a list of possible attributes (no distinction is made between
		MUST and MAY). 

		The generator_map hash maps attribute name keys to Generator instance
		values, so that a given Entry's attributes can be initialized
		to some (often randomly genarted) value.

		The derived_generator_map hash is consulted on a second
		pass, and so may refer to attributes generated by the
		generator_map.


	"""

	objectclass = ""
	attrs = []

	generator_map = {}
	derived_generator_map = {}

	def _generate_attrs(self, entry, generator_map):
		for attr in self.attrs:
			generator = generator_map.get(attr)
			if not generator: continue
			entry.add_attr(generator.get(attr, entry))
		return entry

	def generate_attrs(self, entry):
		return self._generate_attrs(entry, self.generator_map)

	def generate_derived_attrs(self, entry):
		return self._generate_attrs(entry, self.derived_generator_map)


class Domain(LDAPObjectClass):

	objectclass = "domain"
	attrs = """
        dc associatedName  organizationName  description 
        businessCategory  seeAlso  searchGuide  userPassword 
        localityName  stateOrProvinceName  streetAddress 
        physicalDeliveryOfficeName  postalAddress  postalCode 
        postOfficeBox  streetAddress 
        facsimileTelephoneNumber  internationalISDNNumber 
        telephoneNumber  teletexTerminalIdentifier  telexNumber 
        preferredDeliveryMethod  destinationIndicator 
        registeredAddress  x121Address 
	""".split()

class OrganizationalUnit(LDAPObjectClass):

	objectclass = "organizationalUnit"
	attrs = """
	    ou userPassword  searchGuide  seeAlso  businessCategory 
        x121Address  registeredAddress  destinationIndicator 
        preferredDeliveryMethod  telexNumber  teletexTerminalIdentifier 
        telephoneNumber  internationaliSDNNumber 
        facsimileTelephoneNumber  street  postOfficeBox  postalCode
        postalAddress  physicalDeliveryOfficeName  st  l  description 
	""".split()

class Person(LDAPObjectClass):

	objectclass = "person"
	attrs = "sn cn userPassword telephoneNumber seeAlso description".split()

	generator_map = {
		'sn': FilePoolGenerator("last_names"), 
		'userPassword': PasswordGenerator(),
		'telephoneNumber': IntegerGenerator("%d%d%d %d%d%d %d%d%d%d"),
		'description': DescriptionGenerator(),
	}

	derived_generator_map = {
		# dependency problem here.... cn of Person depends on 
		# givenname of inetOrgPerson
		'cn': CompositeGenerator("%s %s", ["givenName", "sn"])
	}

class OrganizationalPerson(LDAPObjectClass):

	objectclass = "organizationalPerson"
	attrs = """ title x121Address registeredAddress destinationIndicator 
                preferredDeliveryMethod telexNumber teletexTerminalIdentifier 
                telephoneNumber internationaliSDNNumber 
                facsimileTelephoneNumber street postOfficeBox postalCode 
				postalAddress physicalDeliveryOfficeName ou st l """.split()

	generator_map = {
		'postOfficeBox': IntegerGenerator("%d%d%d%d"),
		'postalCode': IntegerGenerator("%d%d%d%d%d-%d%d%d%d"),
		#'title': TitleGenerator(),
		'facsimileTelephoneNumber': IntegerGenerator("%d%d%d %d%d%d %d%d%d%d"),
		'street': StreetGenerator("streets"),
		'st': FilePoolGenerator("states"), 
		'l': FilePoolGenerator("cities"), 
		'o': StringGenerator("Red Hat, Inc."),
		'ou': StringGenerator("Global Learning Services"),
	}

	derived_generator_map = {
	}

class InetOrgPerson(LDAPObjectClass):

	objectclass = "inetOrgPerson"
	attrs = """ 
		audio businessCategory carLicense departmentNumber 
		displayName employeeNumber employeeType givenName 
		homePhone homePostalAddress initials jpegPhoto 
		labeledURI manager mobile o pager 
		photo roomNumber secretary uid userCertificate 
		x500uniqueIdentifier preferredLanguage 
		userSMIMECertificate userPKCS12  mail
				""".split()

	generator_map = {
		'givenName': FilePoolGenerator("first_names"), 
		'employeeNumber': IntegerGenerator("%d%d%d-%d%d-%d%d%d%d"),
		'homePhone': IntegerGenerator("%d%d%d %d%d%d %d%d%d%d"),
		'mobile': IntegerGenerator("%d%d%d %d%d%d %d%d%d%d"),
		'pager': IntegerGenerator("%d%d%d %d%d%d %d%d%d%d"),
		'jpegPhoto': JpegPhotoGenerator(),
		'homePostalAddress': AddressGenerator(),
		'employeeType': 
			WeightedFilePoolGenerator("employee_types"),
	}

	derived_generator_map = {
		# uid must come before mail in attrlist
		'uid': UIDGenerator(),
		'mail': CompositeGenerator("%s@" + globals["email_domain"], ["uid"])
#		'manager': ManagerGenerator(),
	}

class PosixAccount(LDAPObjectClass):

	objectclass = "posixAccount"
	attrs = """ 
		cn  uid  uidNumber  gidNumber  homeDirectory 
		userPassword  loginShell  gecos  description
				""".split()

	generator_map = {
		'uidNumber': CounterGenerator("uidNumber", 32000),
		'gidNumber': CounterGenerator("gidNumber", 32000),
		'loginShell': 
			WeightedFilePoolGenerator("shells"),
	}

	derived_generator_map = {
		'homeDirectory': HomeDirectoryGenerator(),
	}

class ShadowAccount(LDAPObjectClass):

	today = str(int(time.time())/(3600*24))

	objectclass = "shadowAccount"
	attrs = """ 
	uid userPassword  shadowLastChange  shadowMin 
	      shadowMax  shadowWarning  shadowInactive 
	      shadowExpire  shadowFlag  description
				""".split()
	
	generator_map = {
		'shadowLastChange': StringGenerator(today),
		'shadowMin': StringGenerator("0"),
		'shadowMax': StringGenerator("90"),
		'shadowWarning': StringGenerator("14"),
		'shadowInactive': StringGenerator("0"),
#		'shadowExpire': StringGenerator("0"),
	}

class PosixGroup(LDAPObjectClass):

	objectclass = "posixGroup"
	attrs = "cn gidNumber userPassword  memberUid  description".split()

class GroupOfUniqueNames(LDAPObjectClass):

	objectclass = "groupOfUniqueNames"
	attrs = """ uniqueMember cn businessCategory  seeAlso  
				owner  ou  o  description 
				""".split()

class MultivaluedDict(DictMixin):

	"""
		stores data as an array of (key,value) tuples

		"a[key] = value" appends (key,value) to the dict
		"a[key]" generates one of the following:

			value                   (if only one instance of key)
		    [value1, value2,...]    (if multiple instance of keys)
			IndexError exception    (if no instance of keys)

		"del a[key]" deletes all instances of keys

		The __getitem__ accessor tries to "do the right thing", but 
		can cause problems if an attribute acquies more than one
		value unexpectedly.

	"""

	def __init__(self): self.data = []

	def __setitem__(self, key, value): self.data.append((key, value))

	def __getitem__(self, key):
		r = [ a[1] for a in self.data if a[0] == key ]
		if r == []:
			raise IndexError, key
		if len(r) == 1: return r[0]
		return r

	def __delitem__(self, key):
		# is iteration safe against removal?
		for i in [ a for a in self.data if a[0] == key ]:
			self.data.remove(i)

	def keys(self): 
		k = []
		for i in self.data: 
			if i[0] not in k: k.append(i[0])
		return k
		

	# thought this would be handled by DictMixin... hmmm...
	def get(self, key, dflt=None):
		try:
			return self[key]
		except IndexError:
			return dflt

# abstract superclass
class Entry(MultivaluedDict):

	"""
		Abastract superclass representing an LDAP entry.
		
		klasses array is a list of object class objects relevent for 
		the entry.

		Upon instantiation, attributes listed in object_class maps 
		will be "filled out" with appropriate values.

		suffix is an intermediate suffix to be added to the 
		RDN of the entry.  The global suffix is also appended.

	"""
	name = "Entry"
	rdn = "uid"
	rdn_hash = None  # child classes instantiate class hash
	klasses = []

	def __init__(self, suffix=None):

		MultivaluedDict.__init__(self)
		self.n = n
		self.suffix = suffix

		self.derive_attrs()

	def derive_attrs(self):

		for k in self.klasses: 
			self.add_attr(Attribute("objectclass", k.objectclass))
			k.generate_attrs(self)
		for k in self.klasses: k.generate_derived_attrs(self)

	def register(self):
		rdnvalue = self[self.rdn].value
		if rdnvalue in self.rdn_hash: return 0
		self.rdn_hash[rdnvalue] = self
		return 1

	def add_attr(self, attr): self[attr.name] = attr

	def dn(self):

		a = self.get(self.rdn)
		if not a: rdnstr = "%s=(new %s)," % (self.rdn, self.name)
		else: rdnstr = "%s=%s," % (self.rdn, a.value)

		if self.suffix: rdnstr += "%s," % self.suffix

		return rdnstr + globals["suffix"]

	def __str__(self):

		s = [ "dn: %s" % self.dn(), ]
		for key,value in self.data: s.append(str(value))
		return os.linesep.join(s)

class PersonEntry(Entry):

	name = "PersonEntry"
	rdn = "uid"
	rdn_hash = {}

	klasses = [ Person(), OrganizationalPerson(), InetOrgPerson(), 
		PosixAccount(), ShadowAccount(), ]

class DomainEntry(Entry):

	name = "DomainEntry"
	rdn = "dc"
	rdn_hash = {}

	klasses = [ Domain(), ]

	def __init__(self, dc=None):
		Entry.__init__(self)
		if dc: self.add_attr(Attribute("dc", dc))

class RootDomainEntry(DomainEntry):

	def dn(self): return globals["suffix"]

class OrganizationalUnitEntry(Entry):

	name = "organizationalUnit"
	rdn = "ou"
	rdn_hash = {}

	klasses = [ OrganizationalUnit(), ]

	def __init__(self, ou=None):
		Entry.__init__(self)
		if ou: self.add_attr(Attribute("ou", ou))

class GroupEntry(Entry):

	name = "GroupEntry"
	rdn = "cn"
	rdn_hash = {}

	klasses = [ PosixGroup(), ]

	def __init__(self, cn, gid=None, suffix=""):

		Entry.__init__(self, suffix=suffix)
		self.add_attr(Attribute("cn", cn))
		if gid: self.add_attr(Attribute("gidNumber", gid))

	def add_members(self, member_list, ratio=0.1):

		r = float(ratio)
		for i in member_list:
			if random() < r:
				self.add_attr(Attribute("memberUid", i["uid"].value))

		# alternate method - quicker but less fuzzy
		#for i in sample(member_list, int(float(ratio)*len(member_list))):
		#	self.add_attr(Attribute("memberUid", i["uid"].value))


if __name__ == '__main__':

	
	import sys
	from optparse import OptionParser

	parser = OptionParser()
	parser.add_option("-b", "--create-base-entries", 
					action="store_true", help="create dc and ou entries")
	parser.add_option("-s", "--suffix", help="directory suffix")
	parser.add_option("-n", "--nusers", help="num entries to generate")
	parser.add_option("-e", "--email-domain", help="email address domain")
	(options, args) = parser.parse_args()
	
	d = options.__dict__
	for k in d:
		if d[k] != None: globals[k] = d[k]

	n = int(globals["nusers"])
	suffix = globals["suffix"]

	if globals["create_base_entries"]:
		info("generating dc and ou entries...")
		rdn = suffix.split(",")[0]
		rdn_value = rdn.split("=",1)[1]

		e = RootDomainEntry(rdn_value)
		print e
		print 

		e = OrganizationalUnitEntry("People")
		print e
		print 

		e = OrganizationalUnitEntry("Groups")
		print e
		print 
		
	# users
	info("generating %d users..." % n)
	for i in range(n): 
		if not i%1000: sys.stderr.write("\n\t%d" % i),
		if not i%100: sys.stderr.write(".")
		p = PersonEntry(suffix="ou=People")
		p.register()
	sys.stderr.write(os.linesep)

	info("building management heirarchy...")
	gmanager = ManagerGenerator(6)
	gmanager.init_levels(PersonEntry.rdn_hash.values())

	for p in PersonEntry.rdn_hash.values():

		mgr = gmanager.get("manager", p)
		if mgr: p.add_attr(gmanager.get("manager", p))

		print p
		print

	gmanager.dump_levelmap(file("/tmp/dump","w"))

	info("building primary groups...")
	# primary groups
	for p in PersonEntry.rdn_hash.values():
		gname = p["uid"].value
		gid = p["gidNumber"].value
		g = GroupEntry(gname, gid, suffix="ou=Groups")
		g.register()
		g.add_attr(Attribute("memberUid", p["uid"].value))

		print g
		print


	info("building secondary groups...")
	# secondary groups
	groupidx = 2000
	for line in slurp_file(os.path.join(globals["datadir"], "groups")):

		ratio, name = line.split(None, 1)	
		
		g = GroupEntry(name, groupidx, suffix="ou=Groups")
		g.register()
		groupidx += 1
		
		g.add_members(PersonEntry.rdn_hash.values(), ratio)
		
		print g
		print

	info("done.")
	#sys.stderr.write(str(PersonEntry.rdn_hash))


# vi: ts=4
