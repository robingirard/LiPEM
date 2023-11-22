import os
import sys
sys.path.extend(['.'])
#import highspy # if using highs solver
import linopy
import pandas as pd

pd.options.display.width = 0
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)

from LEAP.f_graphicalTools import *
from LEAP.f_demand_tools import *
from LEAP.f_tools import *
from LEAP.model_single_horizon_multi_energy import build_single_horizon_multi_energy_LEAP_model

graphical_results_folder="case_studies/eu_7_nodes/graphical_results/"
if not os.path.exists(graphical_results_folder):
    os.makedirs(graphical_results_folder)
input_data_folder="case_studies/eu_7_nodes/data/"
download_input_data(input_data_folder)

selected_conversion_technology=['old_nuke','new_nuke','wind_power_on_shore','wind_power_off_shore',
                                'ccgt','ocgt',"demand_not_served",'hydro_river',
                                'hydro_reservoir',"solar",'Curtailement']
selected_storage_technology = ['storage_hydro',"battery"]
scenario="reference" #'Nuke-' build your own scenarios with new excel sheets
parameters = read_EAP_input_parameters(selected_area_to=None,
                                       selected_conversion_technology=selected_conversion_technology,
                                    selected_storage_technology=selected_storage_technology,
                                 input_data_folder=input_data_folder,
                                 file_id = "EU_7_2050_"+scenario,
                             is_storage=True,is_demand_management=True)

parameters["operation_min_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.25
parameters["operation_max_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.25
#parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"old_nuke"}]=80000
parameters["flexible_demand_to_optimise"].to_dataframe().groupby(["flexible_demand","area_to"]).sum()/10**6
list(parameters.keys())

#building model and solving the problem
model = build_single_horizon_multi_energy_LEAP_model(parameters=parameters)
model.solve(solver_name='gurobi') ### gurobi = 7 minutes highs = 24 hours

#print results
print(extractCosts_l(model))
print(extractEnergyCapacity_l(model)['Capacity_GW'])
print(extractEnergyCapacity_l(model)['Energy_TWh'])
Battery_energy_in_TWh = extractEnergyCapacity_l(model)['Energy_TWh'].loc[(slice(None),slice(None),"battery","storage_in")]['Energy_TWh']
Battery_capacity_GW = extractEnergyCapacity_l(model)['Capacity_GW'].loc[(slice(None),slice(None),"battery","storage_capacity")]['Capacity_GW']
Battery_energy_in_TWh*1000/(Battery_capacity_GW*4)

#TODO function to visualise globally Costs, Energy and Installed Capacity
#TODO function to visualise Battery usage.