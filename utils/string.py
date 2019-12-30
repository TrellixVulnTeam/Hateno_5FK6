#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import codecs
import base64
import hashlib
import json

def fromObject(obj):
	'''
	Represent an object as a base64 string.

	Parameters
	----------
	obj : dict|list
		The object to represent.

	Returns
	-------
	obj_str : str
		The corresponding base64 string.
	'''

	obj_str = json.dumps(obj, sort_keys = True)
	obj_str = base64.urlsafe_b64encode(obj_str.encode('utf-8')).decode('ascii')
	return obj_str

def hash(s):
	'''
	Hash a string, mostly to serve as identifier.

	Parameters
	----------
	s : str
		The string to hash.

	Returns
	-------
	hash : str
		The hash.
	'''

	h = hashlib.md5(s.encode('utf-8')).hexdigest()
	b = codecs.encode(codecs.decode(h.encode('utf-8'), 'hex'), 'base64').decode()

	return b[:-1].replace('+', '-').replace('/', '_')[:-2]
