#!/home/gergely/code/miniconda/bin/python

import conda_api
import subprocess
import sys
import os
import json

def get_input_file(argv):
	# TODO need to accept tarballs containing package data, and have conda use those
	# presently this will handle a .ipynb file on its own
	# OR a .tar file containing .ipynb and required ancillary data files, etc.
	if len(argv) == 1:
		print("ERROR: You didn't specify an input file\nUsage: conda-launch <notebook_name>.ipynb")
		sys.exit(1)
	other_input = None
	if len(argv) > 2:
		other_input = argv[2:]
		## TODO parse this (probably use conda's parser?)

	## handle input file options
	input_file = sys.argv[1]
	root_fname,extn = input_file.split(".")
	print "INPUT FILE",root_fname,extn
	if extn == "ipynb":
		appfile_ipynb = input_file
	elif extn == "tar":
		import tarfile
		tf = tarfile.open(input_file, mode="r:*")
		tf.extractall()
		appfile_ipynb = root_fname + ".ipynb"
		print "Opened tarfile. Expecting to use notebook",appfile_ipynb
		## need more graceful handling here to inspect tarball contents and identify notebooks
	else:	
		print "Input file",input_file,"has an extension that is not supported.\nSupported formats are\nipython notebook with extension .ipynb OR\ntarball containing ipython notebook of the same name"
		sys.exit(1)
	return (appfile_ipynb, None)

def load_params(fname, override_params=None):
	# default parameters here
	set_params = {"depends" : ["ipython-notebook"],
								"platform_depends" : {},
								"appname" : fname,
								"envname" : "ipynb_test",
								"filesroot" : "$HOME",
								"data" : {}
								}
	with open(fname) as nb_file:
		nb_metadata = json.load(nb_file)["metadata"]
	print "Inspecting notebook metadata"
	app_metadata = nb_metadata.get("app")
	if app_metadata:
		# load any from metadata
		for param in app_metadata.keys():
			set_params[param] = app_metadata[param]
			print "Assigned parameter",param,set_params[param]
	else:
		print "No metadata furnished in notebook."
	# this would be stuff from the command line
	if override_params:
		for param in override_params.keys():
			set_params[param] = override_params[param]
			print "Overriding parameter",param,set_params[param]
	print "Using parameters"
	for param in set_params:
		print param,":",set_params[param]
	return set_params

def issue_cmd(cmd_list, call_func=subprocess.check_output):	
	try:
		result = call_func(cmd_list)
		return result
	except:
		print "Unable to execute command"," ".join(cmd_list)

if __name__=="__main__":
	## linux only at this point

	## set_root_prefix in conda-api
	## TODO graceful error if conda not found
	conda_path = issue_cmd(["which","conda"])
	path_stem = conda_path.split("/bin/conda")[0]
	conda_api.set_root_prefix(path_stem)
	
	(appfile_ipynb, other_input) = get_input_file(sys.argv)
	## TODO accept additional parameters contained in other_input
	if other_input:
		print "Received from command line:",other_input
		print "Not supported yet; Ignored for now"

	## get metadata from ipynb (looking for key "app")
	## use defaults where metadata are not provided
	conda_params = load_params(appfile_ipynb)
	# TODO could also try to be smart and look at import statements to suggest packages that should be installed
	## TODO support version specification
	## include a tuple for each package, version req optional
	## depends = ['bokeh',('ipython-notebook','2.0')] # this is just the default
	
	## create conda environment
	create_env = True
	## first see if the name exists
	## this is some clumsy string munging
	env_output = issue_cmd(["info","-e"],conda_api._call_conda)[0].split("\n")
	for envline in env_output:
		if len(envline)>1:
			envfound = envline.split()[0]
			if envfound  == conda_params['envname']:
				print "conda environment with the name",conda_params['envname'],"already exists with the following package info"
				print issue_cmd(["list","-n",conda_params['envname']],conda_api._call_conda)[0]
				## TODO here the user should be given a choice to use
				## use the found environment
				## OR create a new one with another name
				## we should compare dependencies against the env list
				## and notify of those missing
				print "For now, we'll just use this env and hope it's right for you."
				create_env = False
				break
	if create_env:
		## assemble the command string to pass to conda
		conda_create_env_cmd = ['create','-n',conda_params['envname']]
		for add_pkg in conda_params['depends']:
			conda_create_env_cmd.append(add_pkg)
			#add_str = add_pkg[0]
			#if len(add_pkg) > 1:
			#	add_str += "=" + str(add_pkg[1])
			#conda_create_env_cmd.append(add_str)

		print "creating conda environment..."	
		print "Hit enter to accept proposed package plan (it is not displayed to you at the moment)."
		## awkward hack here: user doesn't get to interact with conda create and approve the environment
		comm = issue_cmd(conda_create_env_cmd, conda_api._call_conda)
		print comm[0]

	## extra hacky
	## need to adjust $PATH to find our environment
	## I think this has to be done by hand...?
	print "activating environment",conda_params['envname']
	add_path = path_stem + "/envs/" + conda_params['envname'] + "/bin"
	curr_path = os.environ['PATH']
	print "adding path",add_path
	os.environ['PATH'] = add_path + ":" + os.environ['PATH']
	print "checking for ipython"
	comm = issue_cmd(['which','ipython'],subprocess.call)
	## need to handle cases where ipython not found or environment was not set up correctly...

	## launch ipynb
	print "launching..."
	run_cmd = ['ipython','notebook',appfile_ipynb]
	comm = issue_cmd(run_cmd)
	print comm

	## clean up
	os.environ['PATH'] = curr_path
	## more graceful exit here would be nice?
