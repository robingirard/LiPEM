
#region initialisation
import os
import sys
sys.path.extend(['.'])
#import highspy # if using highs solver
import linopy
import pandas as pd
import requests
pd.options.display.width = 0
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)
pd.set_option('display.width', 1000)

from LEAP.f_graphicalTools import *
from LEAP.f_demand_tools import *
from LEAP.f_tools import *
from LEAP.model_single_horizon_multi_energy import build_single_horizon_multi_energy_LEAP_model
#endregion

#region Download data
graphical_results_folder="case_studies/eu_7_nodes/graphical_results/"
input_data_folder="case_studies/eu_7_nodes/data/"
from urllib.request import urlretrieve

xls_7_nodes_file = input_data_folder+"EU_7_2050.xlsx"
if not os.path.isfile(xls_7_nodes_file):
    response = requests.get("https://cloud.minesparis.psl.eu/index.php/s/cyYnD3nV2BJgYeg")
    with open(xls_7_nodes_file, mode="wb") as file:
        file.write(response.content)
    print(f"Downloaded EU_7_2050 and saved to {xls_7_nodes_file}\n Do not sync excel file with git.")
#endregion

#region I - Simple single area (with ramp) : loading parameters
selected_area_to=["FR"]
selected_conversion_technology=['old_nuke', 'ccgt',"demand_not_served"] #you'll add 'solar' after
#selected_conversion_technology=['old_nuke','wind_power_on_shore', 'ccgt',"demand_not_served",'hydro_river', 'hydro_reservoir',"solar"] ## try adding 'hydro_river', 'hydro_reservoir'

parameters = read_EAP_input_parameters(selected_area_to=selected_area_to,
                                       selected_conversion_technology=selected_conversion_technology,
                                 input_data_folder=input_data_folder,
                                 file_id = "EU_7_2050",
                             is_storage=False,is_demand_management=False)
parameters["operation_min_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.02
parameters["operation_max_1h_ramp_rate"].loc[{"conversion_technology" :"ccgt"}] = 0.05
parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"old_nuke"}]=80000
parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"ccgt"}]=80000

#parameters["exogenous_energy_demand"]
#parameters=parameters.expand_dims(dim={"energy_vector_out": ["electricity"]}, axis=1)

#endregion

#region I - Simple single area (with ramp) : building and solving problem, results visualisation
#building model and solving the problem
model = build_single_horizon_multi_energy_LEAP_model(parameters=parameters)
model.solve(solver_name='gurobi')
## synthèse Energie/Puissance/Coûts
print(extractCosts_l(model))
print(extractEnergyCapacity_l(model))
model.solution["planning_conversion_power_capacity"]
### Check sum Prod = Consumption
abs(model.solution['operation_conversion_power'].sum(['conversion_technology'])-parameters['exogenous_energy_demand']).max()

## visualisation de la série

model.solution['operation_conversion_power'].get_index("date")

production_df=model.solution['operation_conversion_power'].to_dataframe().\
    reset_index().pivot(index="date",columns='conversion_technology', values='operation_conversion_power')
fig=MyStackedPlotly(y_df=production_df,Conso = parameters["exogenous_energy_demand"].to_dataframe())
fig=fig.update_layout(title_text="Production électrique (en KWh)", xaxis_title="heures de l'année")
plotly.offline.plot(fig, filename=graphical_results_folder+'file.html') ## offline
#endregion

#region II - addition of Storage to single area with ramp : loading parameters
selected_area_to=["FR"]
selected_conversion_technology=['old_nuke','wind_power_on_shore','ocgt', 'ccgt',"demand_not_served",'hydro_river', 'hydro_reservoir',"solar"] ## try adding 'hydro_river', 'hydro_reservoir'
selected_storage_technology = ['storage_hydro','battery']
parameters = read_EAP_input_parameters(selected_area_to=selected_area_to,
                                       selected_conversion_technology=selected_conversion_technology,
                                    selected_storage_technology=selected_storage_technology,
                                 input_data_folder=input_data_folder,
                                 file_id = "EU_7_2050",
                                       is_demand_management=False)

parameters["operation_min_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.01
parameters["operation_max_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.02
parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"old_nuke"}]=80000
parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"ccgt"}]=50000

#endregion

#region II -addition of Storage to single area with ramp : building and solving problem, results visualisation
#building model and solving the problem
model = build_single_horizon_multi_energy_LEAP_model(parameters=parameters)
model.solve(solver_name='gurobi')
#res= run_highs(model) #res= linopy.solvers.run_highs(model)

## synthèse Energie/Puissance/Coûts
print(extractCosts_l(model))
print(extractEnergyCapacity_l(model)['Capacity_GW'])
print(extractEnergyCapacity_l(model)['Energy_TWh'])

### Check sum Prod = Consumption
abs(model.solution['operation_conversion_power'].sum(['conversion_technology'])-parameters['exogenous_energy_demand']).max()

Storage_production_out = (model.solution['operation_storage_power_out']).rename({"storage_technology":"conversion_technology"})
Storage_production_out['conversion_technology']=[st+"_out" for st in selected_storage_technology]
Storage_production_out.name = "operation_conversion_power"
Storage_production_in = (-model.solution['operation_storage_power_in']).rename({"storage_technology":"conversion_technology"})
Storage_production_in['conversion_technology']=[st+"_in" for st in selected_storage_technology]
Storage_production_in.name = "operation_conversion_power"
production_xr = xr.concat([model.solution['operation_conversion_power'],Storage_production_out, Storage_production_in], dim="conversion_technology")
abs(production_xr.sum(['conversion_technology'])-parameters['exogenous_energy_demand']).max()

#TODO add storage in production table
## visualisation de la série
#pays="FR"
#production_xr.sel(area_to=pays).to_dataframe().reset_index().pivot(index="date",columns='conversion_technology', values='operation_conversion_power')
production_df=production_xr.to_dataframe().reset_index().pivot(index="date",columns='conversion_technology', values='operation_conversion_power')

fig=MyStackedPlotly(y_df=production_df,Conso =  parameters["exogenous_energy_demand"].to_dataframe())
fig=fig.update_layout(title_text="Production électrique (en KWh)", xaxis_title="heures de l'année")
plotly.offline.plot(fig, filename=graphical_results_folder+'file.html') ## offline
#endregion

#region III -- multi-zone without storage - loading parameters
selected_area_to=["FR","DE"]
selected_conversion_technology=['old_nuke', 'ccgt','wind_power_on_shore',"demand_not_served"] #you'll add 'solar' after #'new_nuke', 'hydro_river', 'hydro_reservoir','wind_power_on_shore', 'wind_power_off_shore', 'solar', 'Curtailement'}
#selected_conversion_technology=['old_nuke','wind_power_on_shore', 'ccgt',"demand_not_served",'hydro_river', 'hydro_reservoir',"solar"] ## try adding 'hydro_river', 'hydro_reservoir'

parameters = read_EAP_input_parameters(selected_area_to=selected_area_to,
                                       selected_conversion_technology=selected_conversion_technology,
                                 input_data_folder=input_data_folder,
                                 file_id = "EU_7_2050",
                             is_storage=False,is_demand_management=False)

parameters["operation_min_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.01
parameters["operation_max_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.02
parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"old_nuke"}]=80000
parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"ccgt"}]=50000

#endregion

#region III -- multi-zone without storage -: building and solving problem, results visualisation
#building model and solving the problem
model = build_single_horizon_multi_energy_LEAP_model(parameters=parameters)
#model.solve(solver_name='highs',parallel = "on")
model.solve(solver_name='gurobi')
#res= run_highs(model) #res= linopy.solvers.run_highs(model)

## synthèse Energie/Puissance/Coûts
print(extractCosts_l(model))
print(extractEnergyCapacity_l(model))

### Check sum Prod = Consumption
production_df = EnergyAndExchange2Prod(model)
abs(production_df.sum(axis=1)-parameters['exogenous_energy_demand'].to_dataframe()["exogenous_energy_demand"]).max()

## visualisation de la série
#TODO nettoyer le code des fonctions graphiques
fig=MyAreaStackedPlot(df_=production_df,Conso=parameters["exogenous_energy_demand"].to_dataframe())
fig=fig.update_layout(title_text="Production électrique (en KWh)", xaxis_title="heures de l'année")
plotly.offline.plot(fig, filename=graphical_results_folder+'file.html') ## offline
#endregion

#region IV - Simple single area +4 million EV +  demande side management +30TWh H2: loading parameters
#TODO adapter le code ici pour le multi-énergie
#### reading energy_demand operation_conversion_availability_factor and conversion_technology_parameters CSV files
#energy_demand = pd.read_csv(InputConsumptionFolder+'energy_demand'+str(year)+'_'+str(Zones)+'.csv',sep=',',decimal='.',skiprows=0,parse_dates=['date']).set_index(["date"])

selected_area_to=["FR","DE"]
selected_conversion_technology=['old_nuke', 'ccgt','wind_power_on_shore',"demand_not_served"] #you'll add 'solar' after #'new_nuke', 'hydro_river', 'hydro_reservoir','wind_power_on_shore', 'wind_power_off_shore', 'solar', 'Curtailement'}
#selected_conversion_technology=['old_nuke','wind_power_on_shore', 'ccgt',"demand_not_served",'hydro_river', 'hydro_reservoir',"solar"] ## try adding 'hydro_river', 'hydro_reservoir'
selected_storage_technology = ['storage_hydro']
parameters = read_EAP_input_parameters(selected_area_to=selected_area_to,
                                       selected_conversion_technology=selected_conversion_technology,
                                    selected_storage_technology=selected_storage_technology,
                                 input_data_folder=input_data_folder,
                                 file_id = "EU_7_2050",
                             is_storage=True,is_demand_management=True)

parameters["operation_min_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.01
parameters["operation_max_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.02
parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"old_nuke"}]=80000
parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"ccgt"}]=50000
# endregion

#region IV -- Simple single area +4 million EV +  demande side management +30TWh H2 : building and solving problem, results visualisation
#building model and solving the problem
model = build_single_horizon_multi_energy_LEAP_model(parameters=parameters)
model.solve(solver_name='gurobi')# highs not faster than cbc
#res= run_highs(model) #res= linopy.solvers.run_highs(model)

## synthèse Energie/Puissance/Coûts
print(extractCosts_l(model))
print(extractEnergyCapacity_l(model))

### Check sum Prod == sum Consumption
Prod_minus_conso = model.solution['operation_conversion_power'].sum(['conversion_technology']) - parameters['exogenous_energy_demand'] + model.solution['operation_storage_power_out'].sum(['storage_technology']) - model.solution['operation_storage_power_in'].sum(['storage_technology']) ## Storage
abs(Prod_minus_conso).max()

Storage_production = (model.solution['operation_storage_power_out'] - model.solution['operation_storage_power_in']).rename({"storage_technology":"conversion_technology"})
Storage_production.name = "operation_conversion_power"
production_xr = xr.combine_by_coords([model.solution['operation_conversion_power'],Storage_production])

## visualisation de la série
production_df=production_xr.to_dataframe().reset_index().pivot(index="date",columns='conversion_technology', values='operation_conversion_power')
fig=MyStackedPlotly(y_df=production_df,Conso = parameters['exogenous_energy_demand'].to_dataframe())
fig=fig.update_layout(title_text="Production électrique (en KWh)", xaxis_title="heures de l'année")
plotly.offline.plot(fig, filename=graphical_results_folder+'file.html') ## offline
#endregion

#region V - 7 node EU model - loading parameters
graphical_results_folder="case_studies/Basic_France_Germany_models/Planning_optimisation/GraphicalResults/"
#selected_conversion_technology=['old_nuke', 'ccgt','wind_power_on_shore',"demand_not_served"] #you'll add 'solar' after #'new_nuke', 'hydro_river', 'hydro_reservoir','wind_power_on_shore', 'wind_power_off_shore', 'solar', 'Curtailement'}
selected_conversion_technology=['old_nuke','wind_power_on_shore', 'ccgt','ocgt',"demand_not_served",'hydro_river', 'hydro_reservoir',"solar"] ## try adding 'hydro_river', 'hydro_reservoir'
selected_storage_technology = ['storage_hydro',"battery"]
pays='FR'
scenario='Nuke-'
parameters = read_EAP_input_parameters(selected_area_to=None,
                                       selected_conversion_technology=selected_conversion_technology,
                                    selected_storage_technology=selected_storage_technology,
                                 input_data_folder=input_data_folder,
                                 file_id = "EU_7_2050_"+scenario,
                             is_storage=True,is_demand_management=True)

parameters["operation_min_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.25
parameters["operation_max_1h_ramp_rate"].loc[{"conversion_technology" :"old_nuke"}] = 0.25
#parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"old_nuke"}]=80000
#parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"ccgt"}]=50000
#parameters["planning_conversion_max_capacity"].loc[{"conversion_technology" :"old_nuke"}]

parameters["flexible_demand_to_optimise"].to_dataframe().groupby(["flexible_demand","area_to"]).sum()/10**6

list(parameters.keys())
year=2018
#endregion

#region V -- 7node EU model : building and solving problem, results visualisation
#building model and solving the problem
model = build_single_horizon_multi_energy_LEAP_model(parameters=parameters)
#model.solve(solver_name='highs',parallel = "on")
#model.solve(solver_name='cplex')
model.solve(solver_name='gurobi') ### gurobi = 7 minutes highs = 24 hours
#res= run_highs(model) #res= linopy.solvers.run_highs(model)

## synthèse Energie/Puissance/Coûts
print(extractCosts_l(model))
print(extractEnergyCapacity_l(model)['Capacity_GW'])
print(extractEnergyCapacity_l(model)['Energy_TWh'])
Battery_energy_in_TWh = extractEnergyCapacity_l(model)['Energy_TWh'].loc[(slice(None),slice(None),"battery","storage_in")]['Energy_TWh']
Battery_capacity_GW = extractEnergyCapacity_l(model)['Capacity_GW'].loc[(slice(None),slice(None),"battery","storage_capacity")]['Capacity_GW']
Battery_energy_in_TWh*1000/(Battery_capacity_GW*4)
### Check sum Prod == sum Consumption

Storage_production_out = (model.solution['operation_storage_power_out']).rename({"storage_technology":"conversion_technology"})
Storage_production_out['conversion_technology']=[st+"_out" for st in selected_storage_technology]
Storage_production_out.name = "operation_conversion_power"
Storage_production_in = (-model.solution['operation_storage_power_in']).rename({"storage_technology":"conversion_technology"})
Storage_production_in['conversion_technology']=[st+"_in" for st in selected_storage_technology]
Storage_production_in.name = "operation_conversion_power"
production_xr = xr.concat([model.solution['operation_conversion_power'],Storage_production_out, Storage_production_in], dim="conversion_technology")

production_xr = xr.concat([model.solution['operation_conversion_power'],Storage_production_out, Storage_production_in], dim="conversion_technology")
production_df = EnergyAndExchange2Prod(model)
abs(production_df.sum(axis=1)-parameters['exogenous_energy_demand'].to_dataframe()["exogenous_energy_demand"]).max()

iii = model.solution['exchange_op_power'].sum(['area_to']).rename({"area_from": "area_to"})
Exchange_pos = (model.solution['exchange_op_power'].sum(['area_from'])).rename(
    {"energy_vector_out": "conversion_technology"})
Exchange_pos["conversion_technology"] = ["import"]
Exchange_neg = (-iii).rename({"energy_vector_out": "conversion_technology"})
Exchange_neg["conversion_technology"] = ["export"]

Exchange_pos.name = "operation_conversion_power"
Exchange_neg.name = "operation_conversion_power"
production_xr_ex=xr.concat([production_xr, Exchange_pos, Exchange_neg], dim="conversion_technology")


model.solution['operation_total_hourly_demand']
model.solution["planning_flexible_demand_max_power_increase"].max()

Prod_minus_conso = production_xr_ex - model.solution['operation_total_hourly_demand'] ## Storage
abs(Prod_minus_conso).max()

Storage_production = (model.solution['operation_storage_power_out'] - model.solution['operation_storage_power_in']).rename({"storage_technology":"conversion_technology"})
Storage_production.name = "operation_conversion_power"
production_xr = xr.combine_by_coords([model.solution['operation_conversion_power'],Storage_production])


Storage_production.loc[{"area_to" :"FR","conversion_technology":"battery"}].min()
Storage_production.loc[{"area_to" :"FR","conversion_technology":"battery"}].max()


## visualisation de la série
production_df=production_xr.to_dataframe().reset_index().pivot(index="date",columns='conversion_technology', values='operation_conversion_power')
fig=MyStackedPlotly(y_df=production_df,Conso = parameters['exogenous_energy_demand'].to_dataframe())
fig=fig.update_layout(title_text="Production électrique (en KWh)", xaxis_title="heures de l'année")
plotly.offline.plot(fig, filename=graphical_results_folder+'file.html') ## offline
#endregion


## sur le nombre de contraintes
A_T = 4; A_ST = 3; D_A = 2; D_A_T = 4; D_A_ST = 5
A = 7 ; ST =2 ; D = 8760 ; T = 10

A*T*A_T + A*ST*A_ST+D*A*D_A+D*A*T*D_A_T+D*A*ST*D_A_ST

