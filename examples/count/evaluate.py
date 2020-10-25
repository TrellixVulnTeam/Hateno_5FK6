#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os

def evaluateSingle(simulation):
	with open(os.path.join(simulation['folder'], simulation.settings['output'][0]['file']), 'r') as f:
		numbers_sum = sum(map(int, f.readlines()))

	return numbers_sum

def evaluateMultiple(simulations):
	return sum([evaluateSingle(s) for s in simulations])

evaluate = evaluateMultiple

def save(simulation, save_dir):
	with open(os.path.join(simulation['folder'], simulation.settings['output'][0]['file']), 'r') as f:
		numbers = f.readlines()

	with open(os.path.join(save_dir, 'half.txt'), 'w') as f:
		f.write(''.join(numbers[::2]))