import linopy
import xarray as xr
from linopy import Model
import os
import pandas as pd
import subprocess as sub
from LEAP.f_tools import *


def build_single_horizon_multi_energy_LEAP_model(parameters):
    """
    This function creates the pyomo model and initlize the parameters and (pyomo) Set values
    :param parameters is a dictionnary with different panda tables :
        - energy_demand: panda table with consumption
        - operation_conversion_availability_factor: panda table
        - conversion_technology_parameters : panda tables indexed by conversion_technology with eco and tech parameters
    """

    ## Starting with an empty model object
    m = linopy.Model()

    ### Obtaining dimensions values
    date = parameters.get_index('date').unique()
    energy_vector_out = parameters.get_index('energy_vector_out').unique()
    energy_vector_in = parameters.get_index('energy_vector_in').unique()
    area_to = parameters.get_index('area_to')
    conversion_technology = parameters.get_index('conversion_technology').unique()
    #TODO : remove french

    # Variables - Base - Operation & Planning
    operation_conversion_power = m.add_variables(name="operation_conversion_power", lower=0, coords=[energy_vector_out,area_to,date,conversion_technology]) ### Energy produced by a production mean at time t
    operation_energy_cost = m.add_variables(name="operation_energy_cost", lower=0, coords=[area_to,energy_vector_in]) ### Energy total marginal cost for production mean p
    operation_total_hourly_demand = m.add_variables(name="operation_total_hourly_demand",lower=0, coords=[energy_vector_out, area_to,date])
    operation_yearly_importation = m.add_variables(name="operation_yearly_importation",lower=0, coords=[area_to, energy_vector_in])

    planning_conversion_cost = m.add_variables(name="planning_conversion_cost", lower=0, coords=[energy_vector_out,area_to,conversion_technology]) ### Energy produced by a production mean at time t
    planning_conversion_power_capacity = m.add_variables(name="planning_conversion_power_capacity", lower=0, coords=[energy_vector_out,area_to,conversion_technology]) ### Energy produced by a production mean at time t

    #operation_total_yearly_demand = m.add_variables(name="operation_total_yearly_demand",lower=0, coords=[energy_vector_out, area_to])

    # Variable - Storage - Operation & Planning
    # Objective Function (terms to be added later in the code for storage and flexibility)
    cost_function = planning_conversion_cost.sum()+ operation_energy_cost.sum()
    m.add_objective( cost_function)
    #TODO : implement time slices
    #################
    # Constraints   #
    #################

    ## table of content for the constraints definition - Operation (Op) & Planning (Pl)
    # 1 - Main constraints
    # 2 - Optional constraints
    # 3 - Storage constraints
    # 4 - exchange constraints
    # 5 - DSM constraints


    #####################
    # 1 - a - Main Constraints - Operation (Op) & Planning (Pl)

    Ctr_Op_operation_costs = m.add_constraints(name="Ctr_Op_operation_costs",
        # [ area_to x energy_vector_in ]
        lhs = operation_energy_cost == parameters["operation_energy_unit_cost"] * operation_yearly_importation)

    Ctr_Op_conso_hourly = m.add_constraints(name="Ctr_Op_conso_hourly",
        # [area_to x energy_vector_out x date]
        lhs = operation_total_hourly_demand == parameters["exogenous_energy_demand"])

    conversion_mean_energy_vector_in = (parameters['energy_vector_in'] == parameters["energy_vector_in_value"])/parameters["operation_conversion_efficiency"]
    Ctr_Op_conso_yearly_1 = m.add_constraints(#name="Ctr_Op_conso_yearly_1",
        # [energy_vector_in x area_to ]
        ## case where energy_vector_in value is not in energy_vector_out (e.g. all but elec), meaning that there is no Ctr_Op_conso_hourly associated constraint
        operation_yearly_importation == (conversion_mean_energy_vector_in * parameters["time_stamp_length"]*operation_conversion_power).sum(["date","energy_vector_out","conversion_technology"]),
        mask= ~parameters["operation_energy_unit_cost"]['energy_vector_in'].isin(energy_vector_out))

    #parameters["operation_energy_unit_cost"]['energy_vector_in_value']
    #(operation_conversion_power * parameters["operation_conversion_efficiency"]).sum(["conversion_technology"]))
    energy_vector_in_in_energy_vector_out = parameters["operation_energy_unit_cost"]['energy_vector_in']==parameters["energy_vector_out"]
    Ctr_Op_operation_demand = m.add_constraints(name="Ctr_Op_operation_demand",
        # [energy_vector_out x area_to ]
        ## case where energy_vector_in value is in energy_vector_out, meaning that there is Ctr_Op_conso_hourly associated constraint
        lhs =  operation_total_hourly_demand  == operation_conversion_power.sum(["conversion_technology"])
    )
    #(operation_yearly_importation * energy_vector_in_in_energy_vector_out).sum(["energy_vector_in"]) +

    Ctr_Pl_capacity = m.add_constraints(name="Ctr_Pl_capacity", # contrainte de maximum de production
        lhs = operation_conversion_power <= planning_conversion_power_capacity * parameters["operation_conversion_availability_factor"])

    Ctr_Pl_planning_conversion_costs = m.add_constraints(name="Ctr_Pl_planning_conversion_costs", # contrainte de définition de planning_conversion_costs
        lhs = planning_conversion_cost == parameters["planning_conversion_unit_cost"] * planning_conversion_power_capacity )

    Ctr_Pl_planning_max_capacity = m.add_constraints(name="Ctr_Pl_planning_max_capacity",
        lhs = planning_conversion_power_capacity <= parameters["planning_conversion_max_capacity"])

    Ctr_Pl_planning_min_capacity = m.add_constraints(name="Ctr_Pl_planning_min_capacity",
        lhs = planning_conversion_power_capacity >= parameters["planning_conversion_min_capacity"],
        mask=parameters["planning_conversion_min_capacity"] > 0)


    #####################
    # 2 - Optional Constraints - Operation (Op) & Planning (Pl)

    if "operation_conversion_maximum_working_hours" in parameters: Ctr_Op_stock = m.add_constraints(name="stockCtr",
            lhs = parameters["operation_conversion_maximum_working_hours"] * planning_conversion_power_capacity >= (parameters["time_stamp_length"]*operation_conversion_power).sum(["date"]),
            mask = parameters["operation_conversion_maximum_working_hours"] > 0)

    if "operation_max_1h_ramp_rate" in parameters: Ctr_Op_rampPlus = m.add_constraints(name="Ctr_Op_rampPlus",
            lhs = operation_conversion_power.diff("date", n=1) <=planning_conversion_power_capacity
                  * (parameters["operation_max_1h_ramp_rate"] * parameters["operation_conversion_availability_factor"])  ,
            mask= (parameters["operation_max_1h_ramp_rate"] > 0) *
                  (xr.DataArray(date, coords=[date])!=date[0]))

    if "operation_min_1h_ramp_rate" in parameters: Ctr_Op_rampMoins = m.add_constraints(name="Ctr_Op_rampMoins",
            lhs = operation_conversion_power.diff("date", n=1) + planning_conversion_power_capacity
                  * (parameters["operation_min_1h_ramp_rate"] * parameters["operation_conversion_availability_factor"]) >= 0,
            # remark : "-" sign not possible in lhs, hence the inequality alternative formulation
            mask=(parameters["operation_min_1h_ramp_rate"] > 0) *
                 (xr.DataArray(date, coords=[date])!=date[0]))

    if "operation_max_1h_ramp_rate2" in parameters:
        Ctr_Op_rampPlus2 = m.add_constraints(name="Ctr_Op_rampPlus2",
            lhs = operation_conversion_power.diff("date", n=2) <= planning_conversion_power_capacity
                  * (parameters["operation_max_1h_ramp_rate2"] * parameters["operation_conversion_availability_factor"]),
            mask=(parameters["operation_max_1h_ramp_rate2"] > 0) *
                 (xr.DataArray(date, coords=[date])!=date[0]))

    if "operation_min_1h_ramp_rate2" in parameters:
        Ctr_Op_rampMoins2 = m.add_constraints(name="Ctr_Op_rampMoins2",
            lhs = operation_conversion_power.diff("date", n=2)+planning_conversion_power_capacity
                  * (parameters["operation_min_1h_ramp_rate2"] * parameters["operation_conversion_availability_factor"]) >= 0,
            mask=(parameters["operation_min_1h_ramp_rate2"] > 0) *
                 (xr.DataArray(date, coords=[date])!=date[0]))



    #####################
    # 3 -  Storage Constraints - Operation (Op) & Planning (Pl)

    if "storage_technology" in parameters:
        storage_technology = parameters.get_index('storage_technology')

        operation_storage_power_in = m.add_variables(name="operation_storage_power_in", lower=0,coords = [date,area_to,energy_vector_out,storage_technology])  ### Energy stored in a storage mean at time t
        operation_storage_power_out = m.add_variables(name="operation_storage_power_out", lower=0,coords = [date,area_to,energy_vector_out,storage_technology])  ### Energy taken out of a storage mean at time t
        operation_storage_internal_energy_level = m.add_variables(name="operation_storage_internal_energy_level", lower=0,coords = [date,area_to,energy_vector_out,storage_technology])  ### level of the energy stock in a storage mean at time t
        planning_storage_energy_cost = m.add_variables(name="planning_storage_energy_cost",coords = [area_to,energy_vector_out,storage_technology])  ### Cost of storage for a storage mean, explicitely defined by definition planning_storage_capacity_costsDef
        planning_storage_energy_capacity = m.add_variables(name="planning_storage_energy_capacity",coords = [area_to,energy_vector_out,storage_technology])  # Maximum capacity of a storage mean
        planning_storage_power_capacity = m.add_variables(name="planning_storage_power_capacity",coords = [area_to,energy_vector_out,storage_technology])  # Maximum flow of energy in/out of a storage mean
        #storage_op_stockLevel_ini = m.add_variables(name="storage_op_stockLevel_ini",coords = [area_from,storage_technology], lower=0)

        #update of the cost function and of the prod = conso constraint
        m.objective += planning_storage_energy_cost.sum()
        m.constraints['Ctr_Op_operation_demand'].lhs += -operation_storage_power_out.sum(['storage_technology'])+operation_storage_power_in.sum(['storage_technology'])

        Ctr_Pl_planning_storage_capacity_costs = m.add_constraints(name="Ctr_Pl_planning_storage_capacity_costs",
             lhs=planning_storage_energy_cost == parameters["planning_storage_energy_unit_cost"] * planning_storage_energy_capacity)

        Ctr_Op_storage_level_definition = m.add_constraints(name="Ctr_Op_storage_level_definition",
            lhs=operation_storage_internal_energy_level.shift(date=-1) == operation_storage_internal_energy_level * (1 - parameters["operation_storage_dissipation"])+parameters["time_stamp_length"]*operation_storage_power_in* parameters["operation_storage_efficiency_in"]
                                                        - parameters["time_stamp_length"]*operation_storage_power_out / parameters["operation_storage_efficiency_out"],
            mask=xr.DataArray(date, coords=[date]) != date[-1]) # voir si ce filtre est vraiment nécessaire

        Ctr_Op_storage_initial_level = m.add_constraints(name="Ctr_Op_storage_initial_level",
            lhs= operation_storage_internal_energy_level.loc[{"date" : date[0] }] == operation_storage_internal_energy_level.loc[{"date" : date[-1] }])

        Ctr_Op_storage_power_in_max = m.add_constraints(name="Ctr_Op_storage_power_in_max",
            lhs=operation_storage_power_in <= planning_storage_power_capacity)

        Ctr_Op_storage_power_out_max = m.add_constraints(name="Ctr_Op_storage_power_out_max",
            lhs=operation_storage_power_out <= planning_storage_power_capacity)

        Ctr_Op_storage_capacity_max = m.add_constraints(name="Ctr_Op_storage_capacity_max",
            lhs=operation_storage_internal_energy_level <= planning_storage_energy_capacity)

        # TODO problem when parameters["planning_storage_max_capacity"] is set to zero

        Ctr_Pl_storage_max_capacity = m.add_constraints(name="Ctr_Pl_storage_max_capacity",
             lhs=planning_storage_energy_capacity <= parameters["planning_storage_max_energy_capacity"])

        Ctr_Pl_storage_min_capacity = m.add_constraints(name="Ctr_Pl_storage_min_capacity",
             lhs=planning_storage_energy_capacity >= parameters["planning_storage_min_energy_capacity"])

        Ctr_Pl_storage_max_power = m.add_constraints(name="Ctr_Pl_storage_max_power",
             lhs=planning_storage_energy_capacity == planning_storage_power_capacity * parameters["operation_storage_hours_of_stock"])
    #####################
    # 4 -  Exchange Constraints - Operation (Op) & Planning (Pl)

    if len(area_to)>1:
        area_from=  parameters.get_index('area_from')
        exchange_op_power = m.add_variables(name="exchange_op_power", lower=0,coords = [date, area_to,area_from,energy_vector_out])  ### Energy stored in a storage mean at time t
        #TODO utiliser swap_dims https://docs.xarray.dev/en/stable/generated/xarray.Dataset.swap_dims.html#xarray.Dataset.swap_dims
        m.constraints['Ctr_Op_operation_demand'].lhs += - exchange_op_power.sum(['area_from']) + exchange_op_power.rename({'area_to':'area_from','area_from':'area_to'}).sum(['area_from'])
        Ctr_Op_exchange_max = m.add_constraints(name="Ctr_Op_exchange_max",
            lhs=exchange_op_power<= parameters["operation_exchange_max_capacity"])
        m.objective += 0.01 * exchange_op_power.sum()
        #TODO change area_from_1 area_from_from  area_from_to


    # Flex consumption
    if "flexible_demand" in parameters:
        flexible_demand = parameters.get_index('flexible_demand')
        # inscrire les équations ici ?
        # planning_flexible_demand_max_power_increase_cost_costs = "flexible_demand_planning_cost" * planning_flexible_demand_max_power_increase_cost
        # operation_total_hourly_demand <= planning_flexible_demand_max_power_increase_cost + "max_power"
        # operation_flexible_demand +"flexible_demand_to_optimise"*operation_flexible_demand_variation_ratio == "flexible_demand_to_optimise"
        operation_flexible_demand = m.add_variables(name="operation_flexible_demand",
                                             lower=0, coords=[date, area_to,energy_vector_out,flexible_demand])
        planning_flexible_demand_max_power_increase = m.add_variables(name="planning_flexible_demand_max_power_increase",
                                                 lower=0, coords=[area_to,energy_vector_out,flexible_demand])
        planning_flexible_demand_cost = m.add_variables(name="planning_flexible_demand_cost",
                                                        lower=0,   coords=[area_to,energy_vector_out,flexible_demand])
        operation_flexible_demand_variation_ratio = m.add_variables(name="operation_flexible_demand_variation_ratio",coords=[date,area_to,energy_vector_out,flexible_demand])

        # update of the cost function and of the prod = conso constraint
        m.objective += planning_flexible_demand_cost.sum()
        m.constraints['Ctr_Op_operation_demand'].lhs += operation_flexible_demand.sum(['flexible_demand'])

        Ctr_Op_planning_flexible_demand_max_power_increase_def = m.add_constraints(name="Ctr_Op_planning_flexible_demand_max_power_increase_def",
            lhs=planning_flexible_demand_cost == parameters["flexible_demand_planning_unit_cost"] * planning_flexible_demand_max_power_increase)

        Ctr_Oplanning_storage_max_power_power = m.add_constraints(name="Ctr_Oplanning_storage_max_power_power",
            lhs=operation_flexible_demand <= planning_flexible_demand_max_power_increase + parameters["flexible_demand_max_power"])

        Ctr_Op_conso_flex = m.add_constraints(name="Ctr_Op_conso_flex",
            lhs=operation_flexible_demand +parameters["flexible_demand_to_optimise"]*operation_flexible_demand_variation_ratio == parameters["flexible_demand_to_optimise"])

        Ctr_Op_conso_flex_sup_rule = m.add_constraints(name="Ctr_Op_conso_flex_sup_rule",
            lhs=operation_flexible_demand_variation_ratio <= parameters["flexible_demand_ratio_max"])

        Ctr_Op_conso_flex_inf_rule = m.add_constraints(name="Ctr_Op_conso_flex_inf_rule",
            lhs=operation_flexible_demand_variation_ratio + parameters["flexible_demand_ratio_max"] >= 0 )


        week_of_year_table = period_boolean_table(date, period="weekofyear")
        Ctr_Op_consum_eq_week = m.add_constraints(name="Ctr_Op_consum_eq_week",
            lhs=(operation_flexible_demand*week_of_year_table).sum(["date"])
                == (parameters["flexible_demand_to_optimise"]*week_of_year_table).sum(["date"]),
            mask = parameters["flexible_demand_period"] == "week")

        day_of_year_table = period_boolean_table(date, period="day_of_year")
        Ctr_Op_consum_eq_day = m.add_constraints(name="Ctr_Op_consum_eq_day",
            lhs=(operation_flexible_demand*day_of_year_table).sum(["date"])
                == (parameters["flexible_demand_to_optimise"]*day_of_year_table).sum(["date"]),
            mask = parameters["flexible_demand_period"] == "day")

        Ctr_Op_consum_eq_year = m.add_constraints(name="Ctr_Op_consum_eq_year",
            lhs=(operation_flexible_demand).sum(["date"])
                == (parameters["flexible_demand_to_optimise"]).sum(["date"]),
            mask = parameters["flexible_demand_period"] == "year")


    return m;



