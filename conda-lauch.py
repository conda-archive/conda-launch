#!/home/gergely/code/miniconda/bin/python

import conda_api
import subprocess
import sys
import os

def get_input_file(argv):
	# TODO need to accept tarballs and handle appropriately
	if len(argv) == 1:
		print("ERROR: You didn't specify an input file\nUsage: conda-launch <notebook_name>.ipynb")
		sys.exit(1)
	appfile_ipynb = sys.argv[1]
	if appfile_ipynb[-5:] != 'ipynb':
		print("Input file doesn't have extension ipynb. That's all that is supported right now.")
		sys.exit(1)
	return (appfile_ipynb, None)

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
	
	## parameters to create conda environment
	# TODO parse 'app' metadata from *ipynb
	# TODO could also try to be smart and look at import statements to suggest packages that should be installed
	
	## TODO add to this from ipynb metadata
	## include a tuple for each package, version req optional
	depends = [('ipython-notebook','2.0')] # this is just the default
	
	## optional parameters with defaults
	# TODO handle params appname, platform_depends, filesroot, data
	conda_params = {'envname':'ipynb_test'}

	(appfile_ipynb, other_files) = get_input_file(sys.argv)
	## TODO handle other_files from cl here

	## create conda environment
	create_env = True
	## first see if the name exists
	env_output = issue_cmd(["info","-e"],conda_api._call_conda)[0].split("\n")
	## this is some clumsy string munging
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
		for add_pkg in depends:
			add_str = add_pkg[0]
			if len(add_pkg) > 1:
				add_str += "=" + str(add_pkg[1])
			conda_create_env_cmd.append(add_str)

		print("creating conda environment...")	
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
