import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)


def generate_olive_oil_dataset(n_samples=5000):
    """
    Generate synthetic dataset for Tunisian olive oil production prediction
    Based on the FAO Tunisia olive sector analysis
    """

    # Define possible values based on the document
    sources = ['Nord', 'Centre', 'Sud', 'Sfax']
    olive_types = ['Chemlali', 'Chétoui', 'Oueslati',
                   'Gerboui', 'Zalmati', 'Zarazi', 'Barouni']
    conditions = ['Rainfed', 'Irrigated']
    olive_sizes = ['Small', 'Medium', 'Large']
    press_methods = ['Traditionnel', 'Super-presses', 'Méthode en continu']

    # TUNISIAN UTILITY PRICES (2024 rates)
    electricity_price_tnd_per_kwh = 0.352  # TND per kWh (industrial rate STEG)
    water_price_tnd_per_m3 = 0.200  # TND per m³ (industrial rate SONEDE)

    # TUNISIAN EMPLOYEE HOURLY WAGES (2024 rates) - TND per hour
    hourly_wages = {
        'Ouvriers': 2.5,      # Basic industrial workers (above minimum wage)
        'Comptables': 6.0,    # Skilled accountants/financial staff
        'Registeurs': 3.5,    # Administrative clerks/registrars
        'Guards': 3.0         # Security guards
    }

    # Regional characteristics based on document analysis
    regional_params = {
        'Nord': {'yield_factor': 1.0, 'quality_factor': 1.2, 'water_factor': 1.1},
        'Centre': {'yield_factor': 0.8, 'quality_factor': 1.0, 'water_factor': 1.0},
        'Sud': {'yield_factor': 0.4, 'quality_factor': 0.9, 'water_factor': 0.8},
        'Sfax': {'yield_factor': 0.7, 'quality_factor': 1.1, 'water_factor': 0.9}
    }

    # Press method efficiency factors
    press_efficiency = {
        'Traditionnel': {'efficiency': 0.7, 'energy': 0.6, 'workers': 1.5, 'time': 1.4},
        'Super-presses': {'efficiency': 0.85, 'energy': 0.8, 'workers': 1.2, 'time': 1.1},
        'Méthode en continu': {'efficiency': 0.95, 'energy': 1.0, 'workers': 0.8, 'time': 0.7}
    }

    data = []

    # Generate date range for 3 years
    start_date = datetime(2021, 1, 1)
    end_date = datetime(2023, 12, 31)

    for i in range(n_samples):
        # Generate random date
        time_between = end_date - start_date
        days_between = time_between.days
        random_days = random.randrange(days_between)
        record_date = start_date + timedelta(days=random_days)

        # Input features
        source = np.random.choice(sources)
        olive_type = np.random.choice(olive_types)
        # 70% rainfed as per document
        condition = np.random.choice(conditions, p=[0.7, 0.3])
        olive_size = np.random.choice(olive_sizes)
        press_method = np.random.choice(
            press_methods, p=[0.25, 0.25, 0.5])

        # Quantity of olives (tons) - based on document ranges
        if source == 'Nord':
            base_quantity = np.random.normal(50, 15)
        elif source == 'Centre' or source == 'Sfax':
            base_quantity = np.random.normal(30, 10)
        else:  # Sud
            base_quantity = np.random.normal(15, 5)

        quantity_olives = max(1, base_quantity)

        # Apply condition factor
        if condition == 'Irrigated':
            quantity_olives *= 1.5

        # Get regional and method parameters
        region_params = regional_params[source]
        method_params = press_efficiency[press_method]

        # Calculate outputs

        # 1. Oil quality (0-100 scale, higher is better)
        base_quality = 70
        if condition == 'Irrigated':
            base_quality += 10
        if olive_type in ['Chétoui', 'Oueslati']:
            base_quality += 8
        if olive_size == 'Large':
            base_quality += 5

        oil_quality = min(
            100, base_quality * region_params['quality_factor'] + np.random.normal(0, 5))
        oil_quality = max(0, oil_quality)

        # 2. Oil quantity (extraction rate 18-22% as per document)
        # Higher quality = better extraction
        extraction_rate = 0.18 + (oil_quality / 500)
        extraction_rate *= method_params['efficiency']
        oil_quantity = quantity_olives * \
            extraction_rate + np.random.normal(0, 0.5)
        oil_quantity = max(0, oil_quantity)

        # 3. Waste production (Fitoura and Margin)
        # Total waste is typically 78-82% of olive input
        total_waste = quantity_olives - oil_quantity
        fitoura_ratio = np.random.uniform(
            0.6, 0.8)  # 60-80% of waste is fitoura
        waste_fitoura = total_waste * fitoura_ratio
        waste_margin = total_waste * (1 - fitoura_ratio)

        # 4. Processing time (hours)
        base_time = quantity_olives * 0.5  # 0.5 hours per ton base
        processing_time = base_time * \
            method_params['time'] + np.random.normal(0, 1)
        processing_time = max(0.5, processing_time)

        # 5. Number of employees by type
        base_workers = max(1, int(quantity_olives / 10))

        # Worker distribution based on method
        if press_method == 'Traditionnel':
            ouvriers = int(base_workers * 2.5)
            comptables = 1
            registeurs = 1
            guards = 1
        elif press_method == 'Super-presses':
            ouvriers = int(base_workers * 1.8)
            comptables = 1
            registeurs = 1
            guards = 1
        else:  # Méthode en continu
            ouvriers = int(base_workers * 1.2)
            comptables = 1
            registeurs = 2
            guards = 1

        # 6. Energy consumption components (kWh)
        base_energy = quantity_olives * 50  
        energy_factor = method_params['energy']

        global_active_power = base_energy * \
            energy_factor * np.random.uniform(0.8, 1.2)
        global_reactive_power = global_active_power * \
            np.random.uniform(0.1, 0.3)
        voltage = np.random.normal(240, 5)  
        global_intensity = global_active_power / voltage * 1000 

        # 7. Water consumption (liters)
        # 800L per ton base (varies by method)
        base_water = quantity_olives * 800
        if press_method == 'Méthode en continu':
            base_water *= 1.5  # More water needed for continuous method

        water_consumption = base_water * \
            region_params['water_factor'] * np.random.uniform(0.8, 1.2)
        water_consumption = max(0, water_consumption)

        # 8. CALCULATE COSTS IN TND (Tunisian Dinars)
        # Convert water from liters to cubic meters (1 m³ = 1000 L)
        water_consumption_m3 = water_consumption / 1000

        # Total energy consumption for billing (active power only - main component)
        total_energy_kwh = global_active_power

        # Calculate utility costs
        electricity_cost_tnd = total_energy_kwh * electricity_price_tnd_per_kwh
        water_cost_tnd = water_consumption_m3 * water_price_tnd_per_m3

        # Calculate labor costs
        ouvriers_cost_tnd = ouvriers * \
            processing_time * hourly_wages['Ouvriers']
        comptables_cost_tnd = comptables * \
            processing_time * hourly_wages['Comptables']
        registeurs_cost_tnd = registeurs * \
            processing_time * hourly_wages['Registeurs']
        guards_cost_tnd = guards * processing_time * hourly_wages['Guards']
        total_labor_cost_tnd = (ouvriers_cost_tnd + comptables_cost_tnd +
                                registeurs_cost_tnd + guards_cost_tnd)

        # Total operational costs
        total_utility_cost_tnd = electricity_cost_tnd + water_cost_tnd
        total_operational_cost_tnd = total_utility_cost_tnd + total_labor_cost_tnd

        # Create record
        record = {
            'Date': record_date,
            'Month': record_date.month,
            'Year': record_date.year,
            'Week': record_date.isocalendar()[1],

            # Inputs
            'Source': source,
            'Olive_Type': olive_type,
            'Condition': condition,
            'Olive_Size': olive_size,
            'Press_Method': press_method,
            'Quantity_Olives_Tons': round(quantity_olives, 2),

            # Outputs
            'Oil_Quality_Score': round(oil_quality, 1),
            'Oil_Quantity_Tons': round(oil_quantity, 2),
            'Waste_Fitoura_Tons': round(waste_fitoura, 2),
            'Waste_Margin_Tons': round(waste_margin, 2),
            'Processing_Time_Hours': round(processing_time, 1),

            # Employees
            'Employees_Comptables': comptables,
            'Employees_Registeurs': registeurs,
            'Employees_Ouvriers': ouvriers,
            'Employees_Guards': guards,
            'Total_Employees': comptables + registeurs + ouvriers + guards,

            # Energy consumption
            'Global_Active_Power_kWh': round(global_active_power, 2),
            'Global_Reactive_Power_kVAr': round(global_reactive_power, 2),
            'Voltage_V': round(voltage, 1),
            'Global_Intensity_A': round(global_intensity, 2),
            'Total_Energy_Consumption_kWh': round(total_energy_kwh, 2),

            # Water consumption
            'Water_Consumption_Liters': round(water_consumption, 0),
            'Water_Consumption_m3': round(water_consumption_m3, 3),

            # UTILITY COSTS
            'Electricity_Price_TND_per_kWh': electricity_price_tnd_per_kwh,
            'Water_Price_TND_per_m3': water_price_tnd_per_m3,
            'Electricity_Cost_TND': round(electricity_cost_tnd, 3),
            'Water_Cost_TND': round(water_cost_tnd, 3),
            'Total_Utility_Cost_TND': round(total_utility_cost_tnd, 3),

            # LABOR COSTS
            'Hourly_Wage_Ouvriers_TND': hourly_wages['Ouvriers'],
            'Hourly_Wage_Comptables_TND': hourly_wages['Comptables'],
            'Hourly_Wage_Registeurs_TND': hourly_wages['Registeurs'],
            'Hourly_Wage_Guards_TND': hourly_wages['Guards'],
            'Ouvriers_Cost_TND': round(ouvriers_cost_tnd, 3),
            'Comptables_Cost_TND': round(comptables_cost_tnd, 3),
            'Registeurs_Cost_TND': round(registeurs_cost_tnd, 3),
            'Guards_Cost_TND': round(guards_cost_tnd, 3),
            'Total_Labor_Cost_TND': round(total_labor_cost_tnd, 3),

            # TOTAL OPERATIONAL COSTS
            'Total_Operational_Cost_TND': round(total_operational_cost_tnd, 3)
        }

        data.append(record)

    # Create DataFrame
    df = pd.DataFrame(data)

    # Sort by date
    df = df.sort_values('Date').reset_index(drop=True)

    return df


# Generate dataset
print("Generating Tunisian Olive Oil Production Dataset with Utility Costs...")
dataset = generate_olive_oil_dataset(5000)

# Save to CSV
dataset.to_csv('tunisian_olive_oil_production_with_costs.csv', index=False)

print(f"Dataset generated successfully!")
print(f"Shape: {dataset.shape}")
print(f"Date range: {dataset['Date'].min()} to {dataset['Date'].max()}")

print(f"\nUtility Prices Used:")
print(
    f"- Electricity: {dataset['Electricity_Price_TND_per_kWh'].iloc[0]} TND per kWh (STEG industrial rate)")
print(
    f"- Water: {dataset['Water_Price_TND_per_m3'].iloc[0]} TND per m³ (SONEDE industrial rate)")

print(f"\nEmployee Hourly Wages Used:")
print(
    f"- Ouvriers: {dataset['Hourly_Wage_Ouvriers_TND'].iloc[0]} TND per hour")
print(
    f"- Comptables: {dataset['Hourly_Wage_Comptables_TND'].iloc[0]} TND per hour")
print(
    f"- Registeurs: {dataset['Hourly_Wage_Registeurs_TND'].iloc[0]} TND per hour")
print(f"- Guards: {dataset['Hourly_Wage_Guards_TND'].iloc[0]} TND per hour")

print(f"\nCost Statistics:")
print(
    f"- Average Electricity Cost: {dataset['Electricity_Cost_TND'].mean():.3f} TND per batch")
print(
    f"- Average Water Cost: {dataset['Water_Cost_TND'].mean():.3f} TND per batch")
print(
    f"- Average Labor Cost: {dataset['Total_Labor_Cost_TND'].mean():.3f} TND per batch")
print(
    f"- Average Total Utility Cost: {dataset['Total_Utility_Cost_TND'].mean():.3f} TND per batch")
print(
    f"- Average Total Operational Cost: {dataset['Total_Operational_Cost_TND'].mean():.3f} TND per batch")
print(
    f"- Maximum Total Operational Cost: {dataset['Total_Operational_Cost_TND'].max():.3f} TND per batch")

print("\nFirst 5 rows of cost columns:")
cost_columns = ['Electricity_Cost_TND', 'Water_Cost_TND', 'Total_Labor_Cost_TND',
                'Total_Utility_Cost_TND', 'Total_Operational_Cost_TND']
print(dataset[cost_columns].head())

print("\nFirst 5 rows of individual labor costs:")
labor_columns = ['Ouvriers_Cost_TND', 'Comptables_Cost_TND',
                 'Registeurs_Cost_TND', 'Guards_Cost_TND']
print(dataset[labor_columns].head())

print("\nDataset info:")
print(dataset.info())

print("\nNew cost columns description:")
all_cost_columns = ['Electricity_Cost_TND', 'Water_Cost_TND', 'Total_Labor_Cost_TND',
                    'Total_Utility_Cost_TND', 'Total_Operational_Cost_TND']
print(dataset[all_cost_columns].describe())
