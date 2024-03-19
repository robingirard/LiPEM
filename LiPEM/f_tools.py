import requests
import numpy as np
import pandas as pd
import xarray as xr
# from sklearn.linear_model import LinearRegression
import linopy
# import flox  # Not working for multidim groupby

from LiPEM.f_demand_tools import *



def read_EAP_input_parameters (
        input_data_folder,
        file_id,
        is_storage: bool = True,
        is_demand_management: bool = True,
        selected_area_to = None,
        selected_conversion_technology = None,
        selected_storage_technology = None,
        verbose: bool = False
    ):
    """
    Read the excel file with input data. Modify the demand according to thermal sensitivity targets.
    fills operation_conversion_availability_factor na with "1"
    fills operation_conversion_efficiency na with "0"
    The used table in the excel are :
    conversion_technology, energy_vector_in, operation_conversion_availabili, electricity_demand
    if multiple area reads also interconnexions
    if is_storage also reads storage_technology
    TODO: implement demand management

    :param InputExcelFolder: folder where the excel file can be found. Should finish with "/" if not empty.
    :param excel_file_name: name of the xls file
    :param is_storage: do you want to use storage in the model ? default to True
    :param is_demand_management: do you want demand side management in the model ? default to True
    :param selected_area_to: list of selected areas. If None (default) all existing areas in the excel file are used
    :param selected_conversion_technology: list of selected conversion technologies. If None (default) all existing technologies in the excel file are used
    :param selected_storage_technology: list of selected storage technologies. If None (default) all existing storage technologies in the excel file are used
    :param verbose: default to False. If True print a message for each step.
    :return:
    """

    # Organisation :
    # 1 - convertion -exchange - storage
    # 2 - demand - demand side management


    # List to be filled by the different xarray tables obtained from the excel file
    to_merge = list()

    # Load excel file
    xls_file = pd.ExcelFile(f'{input_data_folder}{file_id}.xlsx')  # TODO: create an excel file with only two country to accelerate the code here
    


    ########
    # Part 1 -- convertion - exchange - storage
    ########

    # Conversion technology (conversion_technology)
    if verbose: print("Reading conversion_technology")
    conversion_technology_parameters = pd.read_excel(xls_file, "conversion_technology").dropna().set_index(["area_to", "conversion_technology", "energy_vector_out"]).to_xarray()
    if selected_area_to == None:
        selected_area_to = list(conversion_technology_parameters["area_to"].to_numpy())
    if selected_conversion_technology == None:
        selected_conversion_technology = list(conversion_technology_parameters["conversion_technology"].to_numpy())
    to_merge.append(conversion_technology_parameters.select({"conversion_technology" : selected_conversion_technology, "area_to": selected_area_to}))

    # Energy vector in (energy_vector_in)
    if verbose: print("Reading energy_vector_in")
    selected_energy_vector_in_value = list(np.unique(conversion_technology_parameters.select({"conversion_technology" : selected_conversion_technology, "area_to": selected_area_to})["energy_vector_in_value"].squeeze().to_numpy()))
    to_merge.append(
        pd.read_excel(xls_file, "energy_vector_in").dropna().set_index(["area_to", "energy_vector_in"]). \
        to_xarray().loc[{"energy_vector_in" : selected_energy_vector_in_value, "area_to": selected_area_to}])

    # Availability time series for conversion means
    if verbose: print("Reading operation_conversion_availabili")
    path_availability = f'{input_data_folder}{file_id}_availability.nc'
    if (os.path.isfile(path_availability)):
        availability = get_subset_netcdf_data(
            file = input_data_folder + "EU_7_2050_availability.nc",  # TODO: replace with path_availability
            subsets= {"conversion_technology": selected_conversion_technology, "area_to": selected_area_to})
    else:
        availability = pd.read_excel(xls_file, "operation_conversion_availabili", parse_dates=['date']). \
            dropna().set_index(["area_to", "date", "conversion_technology"]). \
            to_xarray().select({"conversion_technology": selected_conversion_technology, "area_to": selected_area_to})
    time_stamp_length = xr.DataArray(data=1, dims=["date"], coords=dict(date=availability.get_index("date"))). \
        rename(new_name_or_name_dict="time_stamp_length")
    # availability.to_netcdf("EU_7_2050_availability.nc")
    to_merge.append(time_stamp_length)
    to_merge.append(availability)
    
    # Exchange (interconnections)
    if len(selected_area_to) > 1:
        if verbose: print("Reading interconnexions")
        to_merge.append(
            pd.read_excel(xls_file, "interconnexions").dropna(). \
            set_index(["area_to", "area_from"]).to_xarray(). \
            expand_dims(dim={"energy_vector_out": ["electricity"]}, axis=1).fillna(0). \
            select({"area_to": selected_area_to, "area_from": selected_area_to}))

    # Storage technology
    if is_storage:
        if verbose: print("Reading storage_technology")
        storage_technology= pd.read_excel(xls_file, "storage_technology").set_index(["energy_vector_out", "area_to", "storage_technology"]).to_xarray()
        if selected_storage_technology == None:
            selected_conversion_technology = list(storage_technology["storage_technology"].to_numpy())
        to_merge.append(storage_technology.select({"area_to": selected_area_to, "storage_technology": selected_storage_technology}))



    ########
    # Part 2 -- demand - demand-side management (DSM)
    ########

    # Exogenous energy demand
    if verbose: print("Reading electricity_demand")
    path_exogenous_energy_demand = f'{input_data_folder}{file_id}_exogeneous_energy_demand.nc'  # TODO: typo in filename (exogeneous -> exogenous)
    if os.path.isfile(path_exogenous_energy_demand):
        exogenous_energy_demand = get_subset_netcdf_data(
            file = input_data_folder + "EU_7_2050_exogeneous_energy_demand.nc",  # TODO: replace with path_exogenous_energy_demand
            subsets= {"area_to" : selected_area_to})
    else:
        exogenous_energy_demand = pd.read_excel(xls_file, "electricity_demand", parse_dates=['date']).dropna(). \
            set_index(["area_to", "date"]).to_xarray().expand_dims(dim={"energy_vector_out": ["electricity"]}, axis=1). \
            transpose("energy_vector_out", "area_to", "date").select({"area_to": selected_area_to})

    # Extract year (?)
    years = list(set(exogenous_energy_demand.date.to_numpy().astype('datetime64[Y]').astype(int) + 1970))
    year = years[0]  # TODO: issue warning if several years?

    # Change in thermal sensitivity
    if verbose: print("Reading temperature")
    path_temperature = f'{input_data_folder}{file_id}_temperature.nc'
    if os.path.isfile(path_temperature):
        temperature = get_subset_netcdf_data(
            file = input_data_folder + "EU_7_2050_temperature.nc",  # TODO: replace with path_temperature
            subsets= {"area_to" : selected_area_to})
    else:
        temperature = pd.read_excel(xls_file, "temperature", parse_dates=['date']). \
            set_index(["date", "area_to"]).loc[str(year)].to_xarray(). \
            expand_dims(dim={"energy_vector_out": ["electricity"]}, axis=1).\
            drop_duplicates(dim="date").select({"area_to": selected_area_to})
    thermal_sensitivity = pd.read_excel(xls_file, "thermal_sensitivity").set_index(["area_to"]).to_xarray().expand_dims(dim={"energy_vector_out": ["electricity"]}, axis=1)
    
    warnings.filterwarnings("ignore")  # TODO: remove FutureWarning here
    decomposed_demand = decompose_demand(temperature, exogenous_energy_demand, temperature_threshold=15)
    exogenous_energy_demand = recompose_demand(decomposed_demand,temperature,thermal_sensitivity,temperature_threshold=15)
    warnings.filterwarnings("default")
    # TODO: add temperature_threshold as a global parameter here
    to_merge.append(exogenous_energy_demand)

    # Demand-side management
    if is_demand_management:
        if verbose: print("Reading demand side management")
        flexible_demand_table = pd.read_excel(xls_file, "flexible_demand").set_index(["area_to", "flexible_demand"]).to_xarray().expand_dims(dim={"energy_vector_out": ["electricity"]}, axis=1)
        demand_profile = pd.read_excel(xls_file, "demand_profile")
        warnings.filterwarnings("ignore")  # TODO: remove FutureWarning here
        flexible_demand_to_optimise = compute_flexible_demand_to_optimise(flexible_demand_table, demand_profile, exogenous_energy_demand, temperature)
        # flexible_demand_to_optimise.to_dataframe().groupby(["energy_vector_out", "area_to", "flexible_demand"]).sum()
        warnings.filterwarnings("default")
        to_merge.append(flexible_demand_to_optimise.select({"area_to": selected_area_to}))

        # Generate parameter "max power" and add it to flexible_demand_table
        flexible_demand_table = flexible_demand_table.merge(flexible_demand_to_optimise.to_dataframe().\
            groupby(["energy_vector_out","area_to"]).max().to_xarray().flexible_demand_to_optimise. \
            rename(new_name_or_name_dict="flexible_demand_max_power"))

        to_merge.append(flexible_demand_table)


    # TODO: add chp_production
    # Final merge
    parameters = xr.merge(to_merge)
    parameters["operation_conversion_availability_factor"] = parameters["operation_conversion_availability_factor"].fillna(1) ## 1 is the default value for availability factor
    parameters["operation_conversion_efficiency"] = parameters["operation_conversion_efficiency"].fillna(0)
    
    return parameters


    # TODO: add demand profile decomposition according to sector/usage :
    # (1) part of the demand side management profile should be substracted to exogeneous_demand
    # (2) evolution of consumption could be defined sectorwise.
    # below a piece of code that was used in the past for decomposition
    # Profile_df_sans_chauffage=pd.read_csv(InputConsumptionFolder+"ConsumptionDetailedProfiles.csv").\
    #     rename(columns={'heures':'hour',"WeekDay":"day"}).\
    #     replace({"day" :{"Sat": "Samedi" , "Week":"Semaine"  , "Sun": "Dimanche"}}). \
    #     query('UsagesGroupe != "Chauffage"'). \
    #     assign(is_steel=lambda x: x["Nature"].isin(["MineraiMetal"])).\
    #     set_index(["Mois", "hour",'Nature', 'type',"is_steel", 'UsagesGroupe', 'UsageDetail', "day"]).\
    #     groupby(["Mois","day","hour","type","is_steel"]).sum().\
    #     merge(add_day_month_hour(df=ConsoTempeYear_decomposed_df,semaine_simplifie=True,French=True,to_index=True),
    #           how="outer",left_index=True,right_index=True).reset_index().set_index("date")[["type","is_steel","Conso"]]. \
    #     pivot_table(index="date", columns=["type","is_steel"], values='Conso')
    # Profile_df_sans_chauffage.columns = ["Autre","Ind_sans_acier","Ind_acier","Residentiel","Tertiaire"]
    #
    # Profile_df_sans_chauffage=Profile_df_sans_chauffage.loc[:,Profile_df_sans_chauffage.sum(axis=0)>0]
    # Profile_df_n=Profile_df_sans_chauffage.div(Profile_df_sans_chauffage.sum(axis=1), axis=0) ### normalisation par 1 et multiplication
    # for col in Profile_df_sans_chauffage.columns:
    #     Profile_df_sans_chauffage[col]=Profile_df_n[col]*ConsoTempeYear_decomposed_df["NTS_C"]
    #
    # steel_consumption=Profile_df_sans_chauffage.loc[:,"Ind_acier"]
    # steel_consumption.max()
    # steel_consumption[steel_consumption.isna()]=110
    # steel_consumption.isna().sum()


# TODO: add labour_ratio_cost to demand_side_management
# This is an operation cost
def labour_ratio_cost(df: pd.DataFrame) -> float:  # Higher labour costs at night
    if df.hour in range(7, 17):
        return 1.
    elif df.hour in range(17, 23):
        return 1.5
    else:
        return 2.


def download_file (url: str, filename: str, verbose: bool = False):
    response = requests.get(url)
    with open(filename, mode="wb") as file:
        file.write(response.content)
    if verbose:
        print(f"Downloaded file {filename}")


def get_subset_netcdf_data (file, subsets):
    ds = xr.open_dataset(file)
    subset_with_existing_values = dict()
    for dim_name in subsets.keys():
        if not subsets[dim_name] == None:
            existing_values = ds.get_index(dim_name)
            subset_with_existing_values[dim_name] = [v for v in subsets[dim_name] if v in existing_values]
    return ds.sel(subset_with_existing_values).load()


def period_boolean_table (date, period):
    """
    returns a boolean xarray table with the dimension date x value(period) with date == value(period)
    :param date:
    :param period: "day_of_year", "weekofyear"
    see https://pandas.pydata.org/docs/reference/api/pandas.Period.html
    :return:
    """
    x_of_year = getattr(date.to_period(), period)
    x_of_year_xr = xr.DataArray(x_of_year, coords={'date': date})
    x_of_year_values = pd.DataFrame(x_of_year).date.unique()
    x_of_year_values_xr = xr.DataArray(x_of_year_values, coords={period: x_of_year_values})
    x_of_year_table = (x_of_year_xr == x_of_year_values_xr)
    return x_of_year_table


# TODO: move to top of file
def get_index_in (xr, index, subset):
    return xr.get_index(index)[xr.get_index(index).isin(subset)]

# TODO: move to top of file
def select (xr, dict_: dict):
    reduced_index = dict()
    for key in dict_:
        reduced_index[key] = get_index_in(xr, key, dict_[key])
    return xr.sel(reduced_index)

# TODO: move to top of file
xr.Dataset.get_index_in = get_index_in
xr.Dataset.select = select


def extractCosts_l (model):

    # Initialize results dictionary
    res = dict()
    res["operation_energy_cost"] = (model.solution["operation_energy_cost"]/ 10 ** 9).to_dataframe()
    res["operation_energy_cost"].columns = ["Cost_10e9_euros"]
    res["operation_energy_cost"]["type"] = "annual_energy"
    res["planning_conversion_cost"] = (model.solution["planning_conversion_cost"]/ 10 ** 9).to_dataframe()
    res["planning_conversion_cost"].columns = ["Cost_10e9_euros"]
    res["planning_conversion_cost"]["type"] = "installed_capacity"
    
    if "planning_flexible_demand_cost" in model.solution :
        res["flexible_demand_capacity_cost"]= (model.solution["planning_flexible_demand_cost"]/ 10 ** 9).to_dataframe()
        res["flexible_demand_capacity_cost"].columns = ["Cost_10e9_euros"]
        res["flexible_demand_capacity_cost"]["type"] = "flexible_demand_capacity"
    
    if "planning_storage_energy_cost" in model.solution:
        res["planning_storage_energy_cost"] = (model.solution["planning_storage_energy_cost"]/ 10 ** 9).to_dataframe()
        res["planning_storage_energy_cost"].columns = ["Cost_10e9_euros"]
        res["planning_storage_energy_cost"]["type"] = "planning_storage_energy_cost"
    
    return res  # TODO: Implicitly assuming that the second index is conversion_technology... strange


def extractEnergyCapacity_l (model):

    # Initialize results dictionary
    res = dict()
    res["production"] = (model.solution["operation_conversion_power"]/ 10 ** 6).sum(["date"]).to_dataframe()
    res["production"].columns = ["Energy_TWh"]
    res["production"]["type"] = "annual_energy"
    res["capacity"] = (model.solution["planning_conversion_power_capacity"]/ 10 ** 3).to_dataframe()
    res["capacity"].columns = ["Capacity_GW"]
    res["capacity"]["type"] = "installed_capacity"

    if "planning_flexible_demand_max_power_increase" in model.solution:
        res["flexconso_capacity"]= (model.solution["planning_flexible_demand_cost"]/ 10 ** 3).to_dataframe()
        res["flexconso_capacity"].columns = ["Capacity_GW"]
        res["flexconso_capacity"]["type"] = "flexible_demand_capacity"
    
    if "planning_storage_energy_cost" in model.solution:
        res["storage_capacity"] = (model.solution["planning_storage_power_capacity"]/ 10 ** 3).to_dataframe()
        res["storage_capacity"].columns = ["Capacity_GW"]
        res["storage_capacity"]["type"] = "storage_capacity"
        res["Variable_storage_in"] = (model.solution["operation_storage_power_in"] / 10 ** 6).sum(["date"]).to_dataframe()
        res["Variable_storage_in"].columns = ["Energy_TWh"]
        res["Variable_storage_in"]["type"] = "storage_in"
        res["Variable_storage_out"] = (model.solution["operation_storage_power_out"] / 10 ** 6).sum(["date"]).to_dataframe()
        res["Variable_storage_out"].columns = ["Energy_TWh"]
        res["Variable_storage_out"]["type"] = "storage_out"

    Myres = dict()
    Myres["Capacity_GW"] = pd.concat([res[r] for r in res]).set_index(["type"], append=True)[["Capacity_GW"]].dropna() .rename({"Capacity_GW": "Capacity_GW"})
    Myres["Energy_TWh"]  = pd.concat([res[r] for r in res]).set_index(["type"], append=True)[["Energy_TWh"]] .dropna() .rename({"Capacity_GW": "Energy_TWh"})
    return Myres


# TODO: rename function, rename input parameters to snake_case
def EnergyAndExchange2Prod (model, EnergyName: str = 'energy', exchangeName: str = 'Exchange'):

    # Create variables dictionary
    variables_dict = {name: model.solution[name].to_dataframe().reset_index() for name in list(model.solution.keys())}
    # variables_dict['exchange_op_power'].columns = ['area_from', 'area_from_1', 'exchange_op_power']
    # area_to = variables_dict['operation_conversion_power'].area_to.unique()

    # Compute production dataframe
    production_df = variables_dict['operation_conversion_power'].pivot(
        index=["area_to", "date"],
        columns='conversion_technology',
        values='operation_conversion_power'
    )
    
    # Calculate import - export
    import_export = \
        variables_dict['exchange_op_power'].groupby(["area_to", "date"])[['exchange_op_power']].sum() - \
        variables_dict['exchange_op_power'].groupby(["area_from", "date"])[['exchange_op_power']].sum()
    
    # # Check
    # if ((variables_dict['exchange_op_power'].groupby(["area_to", "date"]).sum() * variables_dict['exchange_op_power'].rename(columns={"area_from": "area_from_1", "area_from_1": "area_from"}).groupby(["area_from", "date"]).sum()).sum() > 0).bool():
    #     print("Problem with import - export")

    # Update production dataframe
    production_df = production_df.merge(import_export, how='inner', left_on=['area_to', 'date'], right_on=['area_to', 'date'])
    
    return (production_df)


def download_input_data (input_data_folder: str = "case_studies/eu_7_nodes/data/", verbose: bool = False):
    # TODO: move static dictionary to top of file
    INPUT_FILES_DICT = {
        "EU_7_2050.xlsx": "https://cloud.minesparis.psl.eu/index.php/s/cyYnD3nV2BJgYeg",
        "EU_7_2050_exogeneous_energy_demand.nc": "https://cloud.minesparis.psl.eu/index.php/s/31tqYN1sndcNirU",
        "EU_7_2050_availability.nc": "https://cloud.minesparis.psl.eu/index.php/s/sLpfLJdYQ5ks4YM",
        "EU_7_2050_temperature.nc": "https://cloud.minesparis.psl.eu/index.php/s/aALUWGnubUUYQ1I",
        "EU_7_2050_reference.xlsx": "https://cloud.minesparis.psl.eu/index.php/s/kSU57U0nq9cSMKy",
        "EU_7_2050_Nuke-.xlsx": "https://cloud.minesparis.psl.eu/index.php/s/tu92ikbzjD7DWt3",
        "EU_7_2050_Flex+.xlsx": "https://cloud.minesparis.psl.eu/index.php/s/SAV46N1dhw2Xxew",
        "EU_7_2050_Nuke+.xlsx": "https://cloud.minesparis.psl.eu/index.php/s/ni3wkVlnmIRuiHD"
    }

    # Build input data directory
    if not os.path.exists(input_data_folder):
        os.makedirs(input_data_folder)

    for file_name in INPUT_FILES_DICT:
        file_to_download = input_data_folder + file_name

        # Check if file already downloaded
        if os.path.isfile(file_to_download):
            continue
        
        # TODO: use f_tools.download_file()
        # Download file
        response = requests.get(INPUT_FILES_DICT[file_name] + '/download')
        with open(file_to_download, mode='wb') as file:
            file.write(response.content)
        
        # Print success message
        if verbose:
            print(f'Downloaded {file_name} and saved to {file_to_download}\nDo not sync excel/nc files with git.')
