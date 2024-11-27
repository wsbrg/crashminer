# Miner
This part of the project implements:
1) reproducing crashes found in OSS-Fuzz project,
2) extracting the stack traces of the crashes as well as the post-preprocessor code of the respective projects,
3) calculating the scores for the target selection methods for each extracted function,
4) evaluating the the quality of the target selection methods.

## Run
If you only want to run the evaluation from the paper you can find the according scripts to do so in the `scripts/` directory. Before running any of them, make sure to setup your environment by running:
```
./build.sh
```

### Run the evaluation
If your environment is all setup you can proceed by running:
```
# Reproduce the crashes and extract the source code
./scripts/build_targets.sh

# Calculate the scores for each function
./scripts/scores.sh

# Reproduce the data for the plots in the paper
./scripts/eval.sh
```

### Run manually
Each part of the pipeline, from reproducing the OSS-Fuzz crashes to generating the data for the plots of the paper, is implemented as a module in `src/modules` and can be executed through a command line interface. Assuming the environment is set up through the `build.sh` script, you can get a list of available commands through:
```
python src/cli.py --help
# -> make sure your python virtual environment is activated: source env/bin/activate
```
