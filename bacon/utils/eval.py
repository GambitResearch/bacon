"""Utilities to deal with code evaluation."""


def clean_whitespaces(script):
	"""clean up a script in a string

	Remove the amount of whitelines found in the first nonblank line
	"""
	script = script.splitlines(True)
	while script and script[0].isspace():
		script.pop(0)

	if not script:
		raise ValueError("empty script")

	spaces = script[0][:-len(script[0].lstrip())]
	assert spaces.isspace()

	for i, line in enumerate(script):
		if line.isspace():
			continue
		if line.find(spaces) != 0:
			raise ValueError("inconsistent spaces at line %d (%s)"
					% (i + 1, line.strip()))
		script[i] = line[len(spaces):]

	assert not script[0][0].isspace(), script[0]

	# Drop trailing blank lines: exec doesn't like them
	while script[-1].isspace():
		script.pop()

	return ''.join(script)
