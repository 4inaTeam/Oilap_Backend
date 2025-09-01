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
    sources = ['Nord', 'Centre', 'Sud', 'Sfax']  # Regions from document
    olive_types = ['Chemlali', 'Chétoui', 'Oueslati',
                   'Gerboui', 'Zalmati', 'Zarazi', 'Barouni']
    conditions = ['Rainfed', 'Irrigated']
    olive_sizes = ['Small', 'Medium', 'Large']
    press_methods = ['Traditionnel', 'Super-presses', 'Méthode en continu']

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
            press_methods, p=[0.25, 0.25, 0.5])  # Modern methods more common

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
        base_energy = quantity_olives * 50  # 50 kWh per ton base
        energy_factor = method_params['energy']

        global_active_power = base_energy * \
            energy_factor * np.random.uniform(0.8, 1.2)
        global_reactive_power = global_active_power * \
            np.random.uniform(0.1, 0.3)
        voltage = np.random.normal(240, 5)  # Standard voltage with variation
        global_intensity = global_active_power / voltage * 1000  # Convert to amperes

        # 7. Water consumption (liters)
        # 800L per ton base (varies by method)
        base_water = quantity_olives * 800
        if press_method == 'Méthode en continu':
            base_water *= 1.5  # More water needed for continuous method

        water_consumption = base_water * \
            region_params['water_factor'] * np.random.uniform(0.8, 1.2)
        water_consumption = max(0, water_consumption)

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
            'Total_Energy_Consumption_kWh': round(global_active_power + global_reactive_power, 2),

            # Water consumption
            'Water_Consumption_Liters': round(water_consumption, 0)
        }

        data.append(record)

    # Create DataFrame
    df = pd.DataFrame(data)

    # Sort by date
    df = df.sort_values('Date').reset_index(drop=True)

    return df


# Generate dataset
print("Generating Tunisian Olive Oil Production Dataset...")
dataset = generate_olive_oil_dataset(5000)

# Save to CSV
dataset.to_csv('tunisian_olive_oil_production.csv', index=False)

print(f"Dataset generated successfully!")
print(f"Shape: {dataset.shape}")
print(f"Date range: {dataset['Date'].min()} to {dataset['Date'].max()}")
print("\nFirst 5 rows:")
print(dataset.head())

print("\nDataset info:")
print(dataset.info())

print("\nDataset description:")
print(dataset.describe())
