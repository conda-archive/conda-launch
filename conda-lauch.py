import conda_api
import subprocess
import sys
import os
import signal
import json
import argparse

def parse_output(std_stream):
	index = len(std_stream)-1
	if index==1 and std_stream[index]:
		print "ERROR MESSAGE"
	else:
		index = 0
	print std_stream[index]

def get_input_file():
	# TODO need to accept tarballs containing package data, and have conda use those
	# presently this will handle a .ipynb file on its own
	# OR a .tar file containing .ipynb and required ancillary data files, etc.
	p = argparse.ArgumentParser(description='Set up conda environment and run ipyapp notebook server')
	p.add_argument('filename', help="Must specify an ipython notebook file with extension .ipynb or a tarball containing a notebook file of the same name")
	p.add_argument('--envname','-e',nargs='?',dest='setenv', help="Optional flag to name the conda environment to be created; if an envirionment of that name already exists a new env will be created with an altered name")
	#p.add_argument('--mode','-m',nargs='?',default="ipynb", dest='setmode')
	args = p.parse_args()

	## handle input file options
	input_file = args.filename
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
		print "Input file",input_file,'''
		"has an extension that is not supported.
		Supported formats are
		ipython notebook with extension .ipynb OR
		tarball containing ipython notebook of the same name'''
		sys.exit(1)
	#return (appfile_ipynb, args.setenv, args.setmode)
	return (appfile_ipynb, args.setenv)

def load_params(fname, override_params=None):
	set_params = {"depends" : [],
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

class ManageServer:
	def __init__(self, launch_cmd):
		#self.process = subprocess.Popen(launch_cmd.split(), preexec_fn=os.setsid)
		self.process = subprocess.Popen(launch_cmd.split())
		self.pid = self.process.pid
		print "Launched process",self.pid

	def terminate(self):
		print "Terminating process",self.pid
		#os.kill(self.pid, signal.SIGTERM)
		self.process.terminate()
		self.process.kill()

if __name__=="__main__":
	## Linux/ OS X only at this point

	## set_root_prefix in conda-api
	## TODO graceful error if conda not found
	conda_path = issue_cmd(["which","conda"])
	path_stem = conda_path.split("/bin/conda")[0]
	conda_api.set_root_prefix(path_stem)
	
	#(appfile_ipynb, override_env, set_mode) = get_input_file()
	(appfile_ipynb, override_env) = get_input_file()
	## get metadata from ipynb (looking for key "app")
	## use defaults where metadata are not provided
	conda_params = load_params(appfile_ipynb)
	## set any default pkg dependencies here (ipython, flask, etc)
	depends_cmd = ['ipython','flask','runipy'] 
	for add_pkg in conda_params['depends']:
		depends_cmd.append(add_pkg)
	# TODO could also try to be smart and look at import statements to suggest packages that should be installed
	## TODO support version specification
	## include a tuple for each package, version req optional
	## depends = ['bokeh',('ipython-notebook','2.0')] # this is just the default
	if override_env:
		conda_params['envname'] = override_env
		print "Overriding envname from command line; using",conda_params['envname']

	## create conda environment
	## if default env exists add necessary packages to it; inform the user of this
	## if the user specified an envname (override_env==True) we'll assume they
	## have a deliberate configuration in mind and will create a unique envname if there is
	## a conflict with an existing env name
	env_list = conda_api.get_envs()
	#print "Existing environments"
	#print env_list
	create_env = True
	# envname already exists
	if conda_params['envname'] in [env_name.split('/')[-1] for env_name in env_list]:
		print "conda environment with the name",conda_params['envname'],"already exists with the following package info"
		parse_output(issue_cmd(["list","-n",conda_params['envname']],conda_api._call_conda))
		if override_env:
			new_envname = conda_params['envname']
			incr = 1
			while new_envname in [env_name.split('/')[-1] for env_name in env_list]:
				new_envname = conda_params['envname'] + '_ipyapp_' + str(incr)
				incr += 1
			print "Generated new environment name",new_envname
			conda_params['envname'] = new_envname
		else: # if necessary add pkgs to existing env
			create_env = False
			print "Installing any relevant packages into existing env"
			conda_config_env_cmd = ['install','-n',conda_params['envname']] + depends_cmd
			print "installing conda packages",depends_cmd
			parse_output(issue_cmd(conda_config_env_cmd, conda_api._call_conda))
	if create_env:
		conda_create_env_cmd = ['create','-n',conda_params['envname']] + depends_cmd
		print "creating conda environment:"	
		print conda_create_env_cmd
		parse_output(issue_cmd(conda_create_env_cmd, conda_api._call_conda))
		print "Hit enter to accept proposed package plan (it is not displayed to you at the moment)."
		## TODO awkward hack here: user doesn't get to interact with conda create and approve the environment

	## need to adjust $PATH to find our environment
	## I think this has to be done by hand...?
	## need to do this in a cross-platform way
	print "activating environment",conda_params['envname']
	add_path = path_stem + "/envs/" + conda_params['envname'] + "/bin"
	curr_path = os.environ['PATH']
	print "adding path",add_path
	os.environ['PATH'] = add_path + ":" + os.environ['PATH']

	set_host = "127.0.0.1"
	set_port = 5000
	print "Launching app server"
	print "GET access at http://"+set_host+":"+str(set_port)+"/"+appfile_ipynb
	print "POST form at http://"+set_host+":"+str(set_port)+"/"+appfile_ipynb+"/form"
	#subprocess.call(["python","ipyapp/server.py"])
	subprocess.call(["python","ipyapp/server_post.py"])

	## clean up
	os.environ['PATH'] = curr_path
