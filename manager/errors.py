#!/usr/bin/env python3
# -*- coding: utf-8 -*-

class Error(Exception):
	'''
	Base class for exceptions occurring in the manager.
	'''

	pass

class SimulationFolderNotFoundError(Error):
	'''
	Exception raised when we try to add a simulation to the manager, but the indicated folder does not exist.
	'''

	def __init__(self, folder):
		'''
		Store the folder's name.

		Parameters
		----------
		folder : str
			The folder which has not been found.
		'''
		self.folder = folder

class CheckersCategoryNotFoundError(Error):
	'''
	Exception raised when we try to access a checkers category which does not exist.
	'''

	def __init__(self, category):
		'''
		Store the category's name.

		Parameters
		----------
		category : str
			The category which has not been found.
		'''

		self.category = category

class CheckerNotFoundError(Error):
	'''
	Exception raised when we try to access a checker which does not exist.
	'''

	def __init__(self, category, checker_name):
		'''
		Store the category and checker names.

		Parameters
		----------
		category : str
			The checker's category.

		checker_name : str
			The name of the checker which has not been found.
		'''

		self.category = category
		self.checker_name = checker_name

class SimulationIntegrityCheckFailedError(Error):
	'''
	Exception raised when a folder fails to pass an integrity check.
	'''

	def __init__(self, folder):
		'''
		Store the folder's name.

		Parameters
		----------
		folder : str
			The folder which has not been found.
		'''

		self.folder = folder

class SimulationNotFoundError(Error):
	'''
	Exception raised when we look for a non existing simulation.
	'''

	def __init__(self, simulation):
		'''
		Store the simulation's name.

		Parameters
		----------
		simulation : str
			The name of the simulation which has not been found.
		'''

		self.simulation = simulation

class SimulationFolderAlreadyExistError(Error):
	'''
	Exception raised when the folder of a simulation already exists.
	'''

	def __init__(self, folder):
		'''
		Store the folder's name.

		Parameters
		----------
		folder : str
			The name of the folder which should not exist.
		'''

		self.folder = folder

class EmptyListError(Error):
	'''
	Exception raised when a specific list is empty.
	'''

	pass

class DestinationFolderExistsError(Error):
	'''
	Exception raised when a destination folder already exists.
	'''

	pass