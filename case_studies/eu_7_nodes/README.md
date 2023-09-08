# EU 7 nodes case study

This folder contains a 7 node case study built on the single horizon multi energy model. 

## Single horizon multi energy model.
This model is implemented [here](LEAP/model_single_horizon_multi_energy.py). 
The full set of Equations is made available in [.tex](https://github.com/robingirard/LEAP_equations/blob/4f63c91c8102b8b360e2b16015bcea541d4e68d1/SingleHorizon.tex) [.pdf](https://cloud.minesparis.psl.eu/index.php/s/G3NDZjHwriwa2vX) [html](Documentation/SingleHorizon.html) 

## Case study 
This case study is a seven node electrical model for Europe. 

### Data download 
Data is contained in an excel file available [here](https://cloud.minesparis.psl.eu/index.php/s/cyYnD3nV2BJgYeg) that should be put in data folder. 
It contains all economic and technical data and a convenient interface to modify these (in the firt onglet). 
It also contains times series. The code will run faster if you download a netcdf version of the larges time series : 
 - [Temperature](https://cloud.minesparis.psl.eu/index.php/s/aALUWGnubUUYQ1I)
 - [Demand](https://cloud.minesparis.psl.eu/index.php/s/31tqYN1sndcNirU)
 - [Availability](https://cloud.minesparis.psl.eu/index.php/s/sLpfLJdYQ5ks4YM)

Note that opening netcdf data can be done with the xarray package in python, but a quick and convenient view is obtained with [Panoply](https://www.giss.nasa.gov/tools/panoply/)

### How to run the case study 
Several variant (from the simplest one node case) are proposed as example in file case_planning_step_by_step.py 