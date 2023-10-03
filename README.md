# Linopy Energy Alternative Planning (LEAP)
Multi-energy system planning tools based on [linopy](https://github.com/PyPSA/linopy)

This project contains code and data to model the energy system. 
It relies mainly on a combined use of [linopy](https://github.com/PyPSA/linopy) (part of [PyPSA](https://pypsa.org/))
for linear programming adapted for the specific use of energy system modeling.

The installation relies on the use of a conda environment. Instruction is below
#TODO : add links to illustrative exemples here. 

### Table of content

* [1. Installation](#installations)
* [2. Models Folder](#CasDEtude)
* [3. Functions Folder](#functions)
* [4. Pycharm tips](#pycharm)
* [5. Getting help](#GettingH)
* [6. Getting involved](#GettingI)

## 1 - Installations  <a class="anchor" id="installations"></a>

You need to have conda installed and to clone le project 
(either by cloning [Git folder](https://github.com/robingirard/LEAP) or just by downloading the [zip](https://github.com/robingirard/LEAP/archive/refs/heads/main.zip) file associated to the project)

* [Anaconda 3.8 distribution](https://www.anaconda.com/distribution/) or [Miniconda3 distribution](https://docs.conda.io/en/latest/miniconda.html)
* To clone LEAP's Gitlab repository, [Git](https://git-scm.com/downloads) (On Windows, [Git for Windows](https://git-for-windows.github.io/) is preferred)


Once you have downloaded the LEAP folder, you need to open a terminal in order to create the conda environment thanks to the conda.yml file:

    conda env create --file conda.yml
    conda activate LEAP


## 2- Case_studies Folder <a class="anchor" id="CasDEtude"></a>

Contains folders with case studies. Each folder in case_studies Folder contains a set of data and code to run a case study with available models.  
An example first case study is the [7 nodes european case study](case_studies/eu_7_nodes/README.md) that runs a multi-energy single horizon model (but centered on the electricity vector).
See the corresponding [README](case_studies/README.md). You can add your own case study folder to contribute. 


## 3- LEAP folder <a class="anchor" id="functions"></a>
Contains:  
 - [tools](LEAP/f_tools.py) that can be used to facilitate the interface between optimisation models results and parameters and panda. 
 - a set of generic models : 
   - [model_single_horizon_multi_energy.py](LEAP/model_single_horizon_multi_energy.py), used in case study [eu_7_nodes](case_studies/eu_7_nodes/README.md)
   - multi-horizon multienergy comming soon
   - you can add you own models here
 - demand modeling tools in ([f_consumptionModels.py](LEAP/f_demand_tools.py)) 
 - [graphical tools](LEAP/f_graphicalTools.py).

## 4 Pycharm tips  <a class="anchor" id="pycharm"></a>
If you're using PyCharm you should fix the environement in settings by choosing the right "python interpreter"

I strongly recommend to use the keyboard shortcut "crtl+enter" for action "Execute selection". This can be set in PyCharm Settings -> keymap
This project also contains Jupyter Notebook. 

## 5 Getting help <a class="anchor" id="GettingH"></a>

If you have questions, concerns, bug reports, etc, please file an issue in this repository's Issue Tracker.

## 6 Getting involved <a class="anchor" id="GettingI"></a>

BuildingModel is looking for users to provide feedback and bug reports on the initial set of functionalities as well as
developers to contribute to the next versions, with a focus on validation of models, cooling need simulation,
adaptation to other countries' datasets and building usages.

Instructions on how to contribute are available at [CONTRIBUTING](CONTRIBUTING.md).


## Open source licensing info
1. [LICENSE](LICENSE)

----

## Credits and references
Energy-Alternatives-Planning models are directly derived from work performes for several courses given at MINES ParisTech by Robin Girard, and by students. 

### Main contributors : 
- [Robin Girard](https://www.minesparis.psl.eu/Services/Annuaire/robin-girard) -- [blog](https://www.energy-alternatives.eu/) [gitHub](https://github.com/robingirard) [LinkedIn](https://www.linkedin.com/in/robin-girard-a88baa4/) [google Scholar](https://scholar.google.fr/citations?user=cEYGStIAAAAJ&hl=fr)
- Antoine Rogeau
- Quentin Raillard Cazanove
- Pierrick Dartois
- Anaelle Jodry

