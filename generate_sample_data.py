import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import time
import os

def simulate_csv_updates(csv_file="retail_store_inventory.csv", update_interval=3, max_updates=10):
    if not os.path.exists(csv_file):
        print(f"CSV file '{csv_file}' not found!")
        return False
    
    print(f"Starting updates to: {csv_file}")
    update_count = 0
    
    try:
        while max_updates is None or update_count < max_updates:
            time.sleep(update_interval)
            
            try:
                df = pd.read_csv(csv_file)
            except Exception as e:
                print(f"Error reading CSV: {e}")
                continue
            
            updated_df = simulate_data_changes(df)
            
            try:
                updated_df.to_csv(csv_file, index=False)
                update_count += 1
                timestamp = datetime.now().strftime('%H:%M:%S')
                print(f"[{timestamp}] Update #{update_count}")
            except Exception as e:
                print(f"Error saving CSV: {e}")
                continue
                
    except KeyboardInterrupt:
        print(f"Simulation stopped after {update_count} updates")
    
    print(f"Completed. Total updates: {update_count}")
    return True

def simulate_data_changes(df):
    updated_df = df.copy()
    np.random.seed(int(time.time()))
    random.seed(int(time.time()))
    
    # Inventory level changes
    for i in range(len(updated_df)):
        if np.random.random() < 0.4:
            current_inventory = updated_df.loc[i, 'Inventory Level']
            if current_inventory < 15:
                restock_amount = np.random.randint(20, 100)
                updated_df.loc[i, 'Inventory Level'] = min(200, current_inventory + restock_amount)
            elif current_inventory > 0:
                sales_amount = np.random.randint(1, min(10, current_inventory))
                updated_df.loc[i, 'Inventory Level'] = max(0, current_inventory - sales_amount)
    
    # Sales updates
    for i in range(len(updated_df)):
        if np.random.random() < 0.2:
            current_sales = updated_df.loc[i, 'Units Sold']
            new_sales = np.random.randint(1, 8)
            updated_df.loc[i, 'Units Sold'] = current_sales + new_sales
    
    # Demand forecast updates
    for i in range(len(updated_df)):
        if np.random.random() < 0.3:
            current_sales = updated_df.loc[i, 'Units Sold']
            forecast_factor = np.random.uniform(0.8, 1.3)
            updated_df.loc[i, 'Demand Forecast'] = int(current_sales * forecast_factor)
    
    # Price changes
    for i in range(len(updated_df)):
        if np.random.random() < 0.1:
            current_price = updated_df.loc[i, 'Price']
            current_discount = updated_df.loc[i, 'Discount']
            
            if np.random.random() < 0.6:
                new_discount = min(0.4, current_discount + np.random.uniform(0.02, 0.08))
                updated_df.loc[i, 'Discount'] = new_discount
                updated_df.loc[i, 'Price'] = current_price * (1 - new_discount)
            else:
                price_change = np.random.uniform(0.95, 1.05)
                updated_df.loc[i, 'Price'] = current_price * price_change
    
    # Units ordered updates
    for i in range(len(updated_df)):
        if np.random.random() < 0.25:
            inventory = updated_df.loc[i, 'Inventory Level']
            demand = updated_df.loc[i, 'Demand Forecast']
            if inventory < 20:
                order_amount = max(0, demand - inventory + np.random.randint(10, 30))
                updated_df.loc[i, 'Units Ordered'] = order_amount
    
    # Weather condition updates
    weather_conditions = ["Sunny", "Cloudy", "Rainy", "Snowy", "Windy"]
    for i in range(len(updated_df)):
        if np.random.random() < 0.15:
            updated_df.loc[i, 'Weather Condition'] = random.choice(weather_conditions)
    
    # Competitor pricing updates
    for i in range(len(updated_df)):
        if np.random.random() < 0.2:
            our_price = updated_df.loc[i, 'Price']
            competitor_variation = np.random.uniform(0.85, 1.15)
            updated_df.loc[i, 'Competitor Pricing'] = our_price * competitor_variation
    
    # Seasonality updates
    seasons = ["Spring", "Summer", "Autumn", "Winter"]
    for i in range(len(updated_df)):
        if np.random.random() < 0.1:
            current_season = updated_df.loc[i, 'Seasonality']
            available_seasons = [s for s in seasons if s != current_season]
            if available_seasons:
                updated_df.loc[i, 'Seasonality'] = random.choice(available_seasons)
    
    return updated_df

if __name__ == "__main__":
    csv_file = "retail_store_inventory.csv"
    if os.path.exists(csv_file):
        simulate_csv_updates(csv_file)
    else:
        print(f"CSV file '{csv_file}' not found!")
    