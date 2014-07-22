rm -Rf ~/anaconda/envs/adder*
conda build conda.recipe
binstar upload --force /Users/ijstokes/anaconda/conda-bld/osx-64/conda-launch-0.2-py27_0.tar.bz2
conda install /Users/ijstokes/anaconda/conda-bld/osx-64/conda-launch-0.2-py27_0.tar.bz2
conda launch examples/adder.ipynb
conda launch examples/does_not_exist x='zip' y='zap'
conda launch examples/adderenv.ipynb a='three' b='ping'
conda appserver start
