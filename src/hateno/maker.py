#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import stat
import time
import tempfile

from . import string

from .fcollection import FCollection
from .folder import Folder
from .simulation import Simulation
from .manager import Manager
from .generator import Generator
from .remote import RemoteFolder
from .jobs import JobsManager, JobState
from .errors import *
from .ui import UI

class Maker():
	'''
	Assemble all components to extract simulations and automatically create them if they don't exist.

	Parameters
	----------
	simulations_folder : str
		The simulations folder. Must contain a settings file.

	remote_folder_conf : dict
		Configuration of the remote folder.

	max_corrupted : int
		Maximum number of allowed corruptions. Corruptions counter is incremented each time at least one simulation is corrupted. If negative, there is no limit.

	max_failures : int
		Maximum number of allowed failures in the execution of a job. The counter is incremented each time at least one job fails. If negative, there is no limit.
	'''

	def __init__(self, simulations_folder, remote_folder_conf, *, settings_file = None, max_corrupted = -1, max_failures = 0):
		self._simulations_folder = Folder(simulations_folder)
		self._remote_folder_conf = remote_folder_conf

		self._manager_instance = None
		self._generator_instance = None
		self._remote_folder_instance = None
		self._jobs_manager = JobsManager()

		self._settings_file = settings_file

		self._max_corrupted = max_corrupted
		self._corruptions_counter = 0

		self._max_failures = max_failures
		self._failures_counter = 0

		self._events_callbacks = FCollection(categories = ['close-start', 'close-end', 'remote-open-start', 'remote-open-end', 'delete-scripts', 'run-start', 'run-end', 'extract-start', 'extract-end', 'extract-progress', 'generate-start', 'generate-end', 'wait-start', 'wait-progress', 'wait-end', 'download-start', 'download-progress', 'download-end', 'addition-start', 'addition-progress', 'addition-end'])

	def __enter__(self):
		'''
		Context manager to call `close()` at the end.
		'''

		return self

	def __exit__(self, type, value, traceback):
		'''
		Ensure `close()` is called when exiting the context manager.
		'''

		self.close()

	@property
	def folder(self):
		'''
		Return the `Folder` instance.

		Returns
		-------
		folder : Folder
			The instance used by the maker.
		'''

		return self._simulations_folder

	@property
	def manager(self):
		'''
		Returns the instance of Manager used in the Maker.

		Returns
		-------
		manager : Manager
			Current instance, or a new one if `None`.
		'''

		if not(self._manager_instance):
			self._manager_instance = Manager(self._simulations_folder)

		return self._manager_instance

	@property
	def generator(self):
		'''
		Returns the instance of Generator used in the Maker.

		Returns
		-------
		generator : Generator
			Current instance, or a new one if `None`.
		'''

		if not(self._generator_instance):
			self._generator_instance = Generator(self._simulations_folder)

		return self._generator_instance

	@property
	def _remote_folder(self):
		'''
		Returns the instance of RemoteFolder used in the Maker.

		Returns
		-------
		remote_folder : RemoteFolder
			Current instance, or a new one if `None`.
		'''

		if not(self._remote_folder_instance):
			self._remote_folder_instance = RemoteFolder(self._remote_folder_conf)

			self._triggerEvent('remote-open-start')
			self._remote_folder_instance.open()
			self._triggerEvent('remote-open-end')

		return self._remote_folder_instance

	def close(self):
		'''
		Clear all instances of the modules.
		'''

		self._triggerEvent('close-start')

		self._generator_instance = None

		try:
			self._manager_instance.close()

		except AttributeError:
			pass

		try:
			self._remote_folder_instance.close()

		except AttributeError:
			pass

		self._remote_folder_instance = None

		self._triggerEvent('close-end')

	def addEventListener(self, event, f):
		'''
		Add a callback function to a given event.

		Parameters
		----------
		event : str
			Name of the event.

		f : function
			Function to attach.

		Raises
		------
		EventUnknownError
			The event does not exist.
		'''

		try:
			self._events_callbacks.set(f.__name__, f, category = event)

		except FCollectionCategoryNotFoundError:
			raise EventUnknownError(event)

	def _triggerEvent(self, event, *args):
		'''
		Call all functions attached to a given event.

		Parameters
		----------
		event : str
			Name of the event to trigger.

		args : mixed
			Arguments to pass to the callback functions.

		Raises
		------
		EventUnknownError
			The event does not exist.
		'''

		try:
			functions = self._events_callbacks.getAll(category = event)

		except FCollectionCategoryNotFoundError:
			raise EventUnknownError(event)

		else:
			for f in functions:
				f(*args)

	def parseScriptToLaunch(self, launch_option):
		'''
		Parse the `launch` option of a recipe to determine which skeleton/script must be called.

		Parameters
		----------
		launch_option : str
			Value of the `launch` option to parse.

		Returns
		-------
		script_to_launch : dict
			"Coordinates" of the script to launch.
		'''

		option_split = launch_option.rsplit(':', maxsplit = 2)
		option_split_num = [string.intOrNone(s) for s in option_split]

		cut = max([k for k, n in enumerate(option_split_num) if n is None]) + 1

		coords = option_split_num[cut:]
		coords += [-1] * (2 - len(coords))

		return {
			'name': ':'.join(option_split[:cut]),
			'skeleton': coords[0],
			'script': coords[1]
		}

	def run(self, simulations, generator_recipe):
		'''
		Main loop, run until all simulations are extracted or some jobs failed.

		Parameters
		----------
		simulations : list
			List of simulations to extract/generate.

		generator_recipe : dict
			Recipe to use in the generator to generate the scripts.

		Returns
		-------
		unknown_simulations : list
			List of simulations that failed to be generated.
		'''

		self._triggerEvent('run-start')

		script_coords = self.parseScriptToLaunch(generator_recipe['launch'])

		self._corruptions_counter = 0
		self._failures_counter = 0

		while (self._max_corrupted < 0 or self._corruptions_counter <= self._max_corrupted) and (self._max_failures < 0 or self._failures_counter <= self._max_failures):
			unknown_simulations = self.extractSimulations(simulations)

			if not(unknown_simulations):
				break

			jobs_ids = self.generateSimulations(unknown_simulations, generator_recipe, script_coords)
			success = self.waitForJobs(jobs_ids, generator_recipe)

			if not(success):
				self._failures_counter += 1

			success = self.downloadSimulations(unknown_simulations)

			if not(success):
				self._corruptions_counter += 1

			self._triggerEvent('delete-scripts')
			self._remote_folder.deleteRemote([generator_recipe['basedir']])

		self._triggerEvent('run-end', unknown_simulations)

		return unknown_simulations

	def extractSimulations(self, simulations):
		'''
		Extract a given set of simulations.

		Parameters
		----------
		simulations : list
			The list of simulations to extract.

		Returns
		-------
		unknown_simulations : list
			The list of simulations which do not exist (yet).
		'''

		self._triggerEvent('extract-start', simulations)

		unknown_simulations = self.manager.batchExtract(simulations, settings_file = self._settings_file, callback = lambda : self._triggerEvent('extract-progress'))

		self._triggerEvent('extract-end')

		return unknown_simulations

	def generateSimulations(self, simulations, recipe, script_coords):
		'''
		Generate the scripts to generate some unknown simulations, and run them.

		Parameters
		----------
		simulations : list
			List of simulations to create.

		recipe : dict
			Recipe to use in the generator.

		script_coords : dict
			'Coordinates' of the script to launch.

		Raises
		------
		ScriptNotFoundError
			The script to launch has not been found.

		Returns
		-------
		jobs_ids : list
			IDs of the jobs to wait.
		'''

		self._triggerEvent('generate-start')

		scripts_dir = tempfile.mkdtemp(prefix = 'simulations-scripts_')
		recipe['basedir'] = self._remote_folder.sendDir(scripts_dir)

		self.generator.add(simulations)
		generated_scripts = self.generator.generate(scripts_dir, recipe, empty_dest = True)
		self.generator.clear()

		possible_skeletons_to_launch = [k for k, s in enumerate(recipe['subgroups_skeletons'] + recipe['wholegroup_skeletons']) if s == script_coords['name']]

		try:
			script_to_launch = generated_scripts[possible_skeletons_to_launch[script_coords['skeleton']]][script_coords['script']]

		except IndexError:
			raise ScriptNotFoundError(script_coords)

		script_mode = os.stat(script_to_launch['localpath']).st_mode
		if not(script_mode & stat.S_IXUSR & stat.S_IXGRP & stat.S_IXOTH):
			os.chmod(script_to_launch['localpath'], script_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

		self._remote_folder.sendDir(scripts_dir, delete = True, empty_dest = True)

		output = self._remote_folder.execute(script_to_launch['finalpath'])
		jobs_ids = list(map(lambda l: l.strip(), output.readlines()))

		self._triggerEvent('generate-end')

		return jobs_ids

	def waitForJobs(self, jobs_ids, recipe):
		'''
		Wait for a given list of jobs to finish.

		Parameters
		----------
		jobs_ids : list
			IDs of the jobs to wait.

		recipe : dict
			Generator recipe to use.

		Returns
		-------
		success : bool
			`True` is all jobs were finished normally, `False` if there was at least one failure.
		'''

		self._triggerEvent('wait-start', jobs_ids)

		jobs_by_state = {}
		previous_states = {}

		self._jobs_manager.add(*jobs_ids)
		self._jobs_manager.linkToFile(recipe['jobs_states_filename'], remote_folder = self._remote_folder)

		while True:
			self._jobs_manager.updateFromFile()
			jobs_by_state = {
				state: self._jobs_manager.getJobsWithStates([JobState[state.upper()]])
				for state in ['waiting', 'running', 'succeed', 'failed']
			}

			if jobs_by_state != previous_states:
				self._triggerEvent('wait-progress', jobs_by_state)

				if set(jobs_by_state['succeed'] + jobs_by_state['failed']) == set(jobs_ids):
					break

			previous_states = jobs_by_state
			time.sleep(0.5)

		self._jobs_manager.clear()

		self._triggerEvent('wait-end')

		return not(jobs_by_state['failed'])

	def downloadSimulations(self, simulations):
		'''
		Download the generated simulations and add them to the manager.

		Parameters
		----------
		simulations : list
			List of simulations to download.

		Returns
		-------
		success : bool
			`True` if all simulations has successfully been downloaded and added, `False` if there has been at least one issue.
		'''

		self._triggerEvent('download-start', simulations)

		simulations_to_add = []

		for simulation in simulations:
			simulation = Simulation.ensureType(simulation, self._simulations_folder)

			tmpdir = tempfile.mkdtemp(prefix = 'simulation_')
			try:
				self._remote_folder.receiveDir(simulation['folder'], tmpdir, delete = True)

			except RemotePathNotFoundError:
				pass

			simulation['folder'] = tmpdir
			simulations_to_add.append(simulation)

			self._triggerEvent('download-progress')

		self._triggerEvent('download-end')

		self._triggerEvent('addition-start', simulations_to_add)

		failed_to_add = self.manager.batchAdd(simulations_to_add, callback = lambda : self._triggerEvent('addition-progress'))

		self._triggerEvent('addition-end')

		return not(bool(failed_to_add))

class MakerUI(UI):
	'''
	UI to show the different steps of the Maker.

	Parameters
	----------
	maker : Maker
		Instance of the Maker from which the event are triggered.
	'''

	def __init__(self, maker):
		super().__init__()

		self._state_line = None
		self._main_progress_bar = None

		self._statuses = 'Current statuses: {waiting} waiting, {running} running, {succeed} succeed, {failed} failed'
		self._statuses_line = None

		maker.addEventListener('close-start', self._closeStart)
		maker.addEventListener('close-end', self._closeEnd)
		maker.addEventListener('remote-open-start', self._remoteOpenStart)
		maker.addEventListener('remote-open-end', self._remoteOpenEnd)
		maker.addEventListener('delete-scripts', self._deleteScripts)
		maker.addEventListener('run-start', self._runStart)
		maker.addEventListener('run-end', self._runEnd)
		maker.addEventListener('extract-start', self._extractStart)
		maker.addEventListener('extract-progress', self._extractProgress)
		maker.addEventListener('extract-end', self._extractEnd)
		maker.addEventListener('generate-start', self._generateStart)
		maker.addEventListener('generate-end', self._generateEnd)
		maker.addEventListener('wait-start', self._waitStart)
		maker.addEventListener('wait-progress', self._waitProgress)
		maker.addEventListener('wait-end', self._waitEnd)
		maker.addEventListener('download-start', self._downloadStart)
		maker.addEventListener('download-progress', self._downloadProgress)
		maker.addEventListener('download-end', self._downloadEnd)
		maker.addEventListener('addition-start', self._additionStart)
		maker.addEventListener('addition-progress', self._additionProgress)
		maker.addEventListener('addition-end', self._additionEnd)

	def _updateState(self, state):
		'''
		Text line to display the current state of the Maker.

		Parameters
		----------
		state : str
			State to display.
		'''

		if self._state_line is None:
			self._state_line = self.addTextLine(state)

		else:
			self._state_line.text = state

	def _closeStart(self):
		'''
		Maker starts closing.
		'''

		self._updateState('Closing…')

	def _closeEnd(self):
		'''
		Maker is closed.
		'''

		self._updateState('Closed')

	def _remoteOpenStart(self):
		'''
		Connection to the RemoteFolder is started.
		'''

		self._updateState('Connection…')

	def _remoteOpenEnd(self):
		'''
		Connected to the RemoteFolder.
		'''

		self._updateState('Connected')

	def _deleteScripts(self):
		'''
		Deletion of the scripts.
		'''

		self._updateState('Deleting the scripts…')

	def _runStart(self):
		'''
		The run loop just started.
		'''

		self._updateState('Running the Maker…')

	def _runEnd(self, unknown_simulations):
		'''
		The run loop has ended.

		Parameters
		----------
		unknown_simulations : list
			List of simulations that still do not exist.
		'''

		if unknown_simulations:
			self._updateState(string.plural(len(unknown_simulations), 'simulation still does not exist', 'simulations still do not exist'))

		else:
			self._updateState('All simulations have successfully been extracted')

	def _extractStart(self, simulations):
		'''
		Start the extraction of the simulations.

		Parameters
		----------
		simulations : list
			List of the simulations that will be extracted.
		'''

		self._updateState('Extracting the simulations…')
		self._main_progress_bar = self.addProgressBar(len(simulations))

	def _extractProgress(self):
		'''
		A simulation has just been extracted.
		'''

		self._main_progress_bar.counter += 1

	def _extractEnd(self):
		'''
		All simulations have been extracted.
		'''

		self.removeItem(self._main_progress_bar)
		self._main_progress_bar = None
		self._updateState('Simulations extracted')

	def _generateStart(self):
		'''
		Start the generation of the scripts.
		'''

		self._updateState('Generating the scripts…')

	def _generateEnd(self):
		'''
		Scripts are generated.
		'''

		self._updateState('Scripts generated')

	def _waitStart(self, jobs_ids):
		'''
		Start to wait for some jobs.

		Parameters
		----------
		jobs_ids : list
			IDs of the jobs to wait.
		'''

		self._updateState('Waiting for jobs to finish…')
		self._main_progress_bar = self.addProgressBar(len(jobs_ids))
		self._statuses_line = self.addTextLine(self._statuses.format(waiting = 0, running = 0, succeed = 0, failed = 0))

	def _waitProgress(self, jobs_by_state):
		'''
		The state of at least one job has changed.

		Parameters
		----------
		jobs_by_state : dict
			The jobs IDs, sorted by their state.
		'''

		self._statuses_line.text = self._statuses.format(**{state: len(jobs) for state, jobs in jobs_by_state.items()})
		self._main_progress_bar.counter = len(jobs_by_state['succeed'] + jobs_by_state['failed'])

	def _waitEnd(self):
		'''
		All jobs are finished.
		'''

		self.removeItem(self._statuses_line)
		self.removeItem(self._main_progress_bar)
		self._updateState('Jobs finished')

	def _downloadStart(self, simulations):
		'''
		Start to download the simulations.

		Parameters
		----------
		simulations : list
			Simulations that will be downloaded.
		'''

		self._updateState('Downloading the simulations…')
		self._main_progress_bar = self.addProgressBar(len(simulations))

	def _downloadProgress(self):
		'''
		A simulation has just been downloaded.
		'''

		self._main_progress_bar.counter += 1

	def _downloadEnd(self):
		'''
		All simulations have been downloaded.
		'''

		self.removeItem(self._main_progress_bar)
		self._main_progress_bar = None
		self._updateState('Simulations downloaded')

	def _additionStart(self, simulations):
		'''
		Start to add the simulations.

		Parameters
		----------
		simulations : list
			The simulations that will be added.
		'''

		self._updateState('Adding the simulations to the manager…')
		self._main_progress_bar = self.addProgressBar(len(simulations))

	def _additionProgress(self):
		'''
		A simulation has just been added.
		'''

		self._main_progress_bar.counter += 1

	def _additionEnd(self):
		'''
		All simulations have been added.
		'''

		self.removeItem(self._main_progress_bar)
		self._main_progress_bar = None
		self._updateState('Simulations added')
