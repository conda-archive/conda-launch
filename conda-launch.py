import conda_api
import subprocess
import sys
#import os
import json
import argparse

###############################################################
##
##  User Input/ Initialize parameters
##
###############################################################


def get_input_file():
    # TODO need to accept tarballs containing package data, and have conda use those
    # presently this will handle a .ipynb file on its own
    # OR a .tar file containing .ipynb and required ancillary data files, etc.
    # Also eventually this should be integrated with conda search/ install functionality
    # so app packages can be obtained from Binstar
    p = argparse.ArgumentParser(description="Set up conda environment and run "
                                "ipyapp notebook server")
    p.add_argument('filename', help="Must specify an ipython notebook file with extension ipynb "
                   "or a tarball containing a notebook file of the same name")
    p.add_argument('--envname', '-e', nargs='?', dest='setenv', help="Optional flag to name the "
                   "conda environment to be used; if an environment with that name already exists "
                   "and matches required dependencies it will be used.")
    args = p.parse_args()

    ## handle input file options
    input_file = args.filename
    root_fname, extn = input_file.split(".")
    if extn == "ipynb":
        appfile_ipynb = input_file
    elif extn == "tar":
        import tarfile
        tf = tarfile.open(input_file, mode="r:*")
        tf.extractall()
        appfile_ipynb = root_fname + ".ipynb"
        log_output("Opened tarfile. Expecting to use notebook", appfile_ipynb)
        ## need more graceful handling here to inspect tarball contents and identify notebooks
    else:
        log_output("Input file", input_file,
        ''' has an extension that is not supported.
        Supported formats are
        ipython notebook with extension .ipynb OR
        tarball containing ipython notebook of the same name.''')
        sys.exit(1)
    #return (appfile_ipynb, args.setenv, args.setmode)
    return (appfile_ipynb, args.setenv)


def load_params(fname):
    ## this is the ipyapp metadata spec with defaults
    set_params = {"depends": [],
                  "platform_depends": {},
                  "appname": fname,
                  "envname": "ipynb_test",
                  "filesroot": "$HOME",
                  "data": {}
                  }
    with open(fname) as nb_file:
        nb_metadata = json.load(nb_file)["metadata"]
    log_output("Inspecting notebook metadata")
    app_metadata = nb_metadata.get("conda.app")
    if app_metadata:
        # load any from metadata
        for param in app_metadata.keys():
            set_params[param] = app_metadata[param]
            log_output("Assigned parameter", param, set_params[param])
    else:
        log_output("No metadata furnished in notebook.")
    log_output("Using parameters")
    for param in set_params:
        log_output(param, ":", set_params[param])
    return set_params


###############################################################
##
##  conda environment functions
##
###############################################################


def compile_packages(pkg_list, depends_list):
    for add_pkg in depends_list:
        pkg_list.append(add_pkg)
    return pkg_list


def get_unique_name(envname_base, existing_envs):
    L = len(envname_base)
    matches = [envname for envname in existing_envs if envname[:L] == envname_base]
    if not matches:
        return envname_base
    suffix = 1
    while (envname_base + "_" + str(suffix)) in matches:
        suffix += 1
    return (envname_base + "_" + str(suffix))


def call_conda_create(set_envname, depends):
    conda_create_env_cmd = ['create', '-n', set_envname] + depends
    log_output("creating conda environment with command:")
    log_output(conda_create_env_cmd)
    log_output("Hit enter to see the proposed package plan and create the environment.")
    parse_output(issue_cmd(conda_create_env_cmd, conda_api._call_conda))


## if a satisfactory env exists and unique==False, use it
## otherwise create an appropriate env with a unique name
def create_conda_env(set_envname, depends, create_env=True, env_list=None):
    if not env_list:
        env_list = [envname.split('/')[-1] for envname in conda_api.get_envs()]
    # default: just make a new environment
    if create_env:
        unique_name = get_unique_name(set_envname, env_list)
        call_conda_create(unique_name, depends)
        return unique_name
    # try to find a suitable existing env
    else:  # create_env=False
        if set_envname in env_list:
            log_output("conda environment with the name", set_envname, "already exists.")
            try:
                _env_output = issue_cmd(["list", "-n", conda_params['envname']],
                                        conda_api._call_conda)
                env_output = _env_output[0].split('\n')[2:-1]
                existing_env_pkgs = [env_str.split()[0] for env_str in env_output]
                missing = [pkg for pkg in depends if pkg not in existing_env_pkgs]
            except:
                missing = ['force_new_env']
            if missing:
                log_output("Existing environment named", set_envname,
                           "lacks the following required packages", missing)
                log_output("Creating a new env instead.", set_envname)
                return create_conda_env(set_envname, depends, True, env_list)
            else:
                log_output("Existing environment name", set_envname,
                           "satisfies requirements and will be used.")
                return set_envname
        # envname not found, create it
        else:
            return create_conda_env(set_envname, depends, True, env_list)

###############################################################
##
##  utils/ helper functions
##
###############################################################


def parse_output(std_stream):
    index = len(std_stream) - 1
    if index == 1 and std_stream[index]:
        log_output("ERROR MESSAGE")
    else:
        index = 0
    log_output(std_stream[index])


def log_output(*args):
    for s in args:
        print str(s),
    print ''


def issue_cmd(cmd_list, call_func=subprocess.check_output):
    try:
        result = call_func(cmd_list)
        return result
    except:
        log_output("Unable to execute command", " ".join(cmd_list))

###############################################################
##
##  __main__
##
###############################################################


if __name__ == "__main__":
    ## set_root_prefix in conda-api
    ## TODO graceful error if conda not found
    conda_path = issue_cmd(["which", "conda"])
    path_stem = conda_path.split("/bin/conda")[0]
    conda_api.set_root_prefix(path_stem)

    (appfile_ipynb, override_envname) = get_input_file()
    conda_params = load_params(appfile_ipynb)
    # if user names the env from command line
    create_new_env = True
    if override_envname:
        conda_params['envname'] = override_envname
        log_output("Received envname from command line:", conda_params['envname'])
        create_new_env = False

    # provide default packages here
    # TODO could also try to be smart and look at import statements to suggest packages
    # that should be installed
    ## TODO support version specification
    ## include a tuple for each package, version req optional
    ## depends = ['bokeh',('ipython-notebook','2.0')] # this is just the default
    default_pkgs = ['ipython', 'flask', 'runipy']
    pkg_list = compile_packages(default_pkgs, conda_params['depends'])
    env_str = '_'.join(pkg_list)

    base_envname = conda_params['envname']
    if create_new_env:
        base_envname = base_envname + "_ipyapp_" + env_str + "_" + appfile_ipynb
    use_envname = create_conda_env(base_envname, pkg_list, create_new_env)
    use_path = path_stem + "/envs/" + use_envname + "/bin"

    log_output("Conda environment configured")
    log_output("ipyapp file:", appfile_ipynb)
    log_output("conda environment:", use_envname)
    log_output("python path:", use_path)
    log_output("Done.")

###############################################################
##
##  Scrapheap // Some pieces may be useful for ipyapp server?
##
###############################################################

## wrapper class to manage server...
#class ManageServer:
#	def __init__(self, launch_cmd):
#		#self.process = subprocess.Popen(launch_cmd.split(), preexec_fn=os.setsid)
#		self.process = subprocess.Popen(launch_cmd.split())
#		self.pid = self.process.pid
#		log_output( "Launched process",self.pid )
#
#	def terminate(self):
#		log_output( "Terminating process",self.pid )
#		#os.kill(self.pid, signal.SIGTERM)
#		self.process.terminate()
#		self.process.kill()

## adjust conda python path
##
## need to adjust $PATH to find our environment
## I think this has to be done by hand...?
## need to do this in a cross-platform way
#log_output( "activating environment",conda_params['envname'] )
#add_path = path_stem + "/envs/" + conda_params['envname'] + "/bin"
#curr_path = os.environ['PATH']
#log_output( "adding path",add_path )
#os.environ['PATH'] = add_path + ":" + os.environ['PATH']

## launch app server
##
#set_host = "127.0.0.1"
#set_port = 5000
#log_output( "Launching app server" )
#log_output( "GET access at http://"+set_host+":"+str(set_port)+"/"+appfile_ipynb )
#log_output( "POST form at http://"+set_host+":"+str(set_port)+"/"+appfile_ipynb+"/form" )
##subprocess.call(["python","ipyapp/server.py"])
#subprocess.call(["python","ipyapp/server_post.py"])
