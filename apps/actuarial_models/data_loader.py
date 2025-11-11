# data_loader.py

"""
Purpose:
  Read & validate the three input files: temperature, bank holidays, demand.

Each loader returns (raw_df, aug_df) where aug_df has extra columns needed downstream.

Functions:
  - load_temperature_data
  - GWA_adjustment
  - load_bank_holidays_data
  - load_demand_data

Update if file formats change or you need new validation rules.
"""

import pandas as pd
import numpy as np
from datetime import datetime
import streamlit as st

@st.cache_data
def load_temperature_data(file_input):
    raw = pd.read_csv(file_input, sep=None, engine='python')
    if 'Date' not in raw.columns or 'Value' not in raw.columns:
        raise ValueError("Temperature file needs 'Date' & 'Value'")
    df = raw.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    if df['Date'].isnull().any(): raise ValueError("Invalid dates")
    current = datetime.now().year
    yrs = df['Date'].dt.year
    if (current-1) not in yrs.unique(): raise ValueError(f"Missing year {current-1}")
    if (yrs > current).any():        raise ValueError("Future dates found")
    # Add modeling columns
    df['Cal Year']   = df['Date'].dt.year
    df['Month']      = df['Date'].dt.month
    df['Month_Name'] = df['Month'].apply(lambda m: datetime(1900,m,1).strftime("%b"))
    df['DayOfWeek']  = df['Date'].dt.strftime("%a")
    df['Weekend']    = df['DayOfWeek'].isin(['Sat','Sun']).astype(int)
    df['Year']       = df['Cal Year'] + (df['Month'] >= 7).astype(int)
    for i in range(1,5):
        df[f'Temp_Lag_{i}_Day'] = df['Value'].shift(i)
    cold = df['Value'] < -1
    grp  = (cold != cold.shift()).cumsum()
    df['Cold_Spell'] = (cold.groupby(grp).transform('sum')>=3).astype(int)
    return raw, df

def GWA_adjustment(df_aug, industrial_age_end=1880, winter_toggle=False, winter_months=None):
    raw = df_aug.copy()
    base = raw[raw['Cal Year'] >= industrial_age_end]
    if winter_toggle and winter_months:
        base = base[base['Date'].dt.strftime("%b").isin(winter_months)]
    slope, _ = np.polyfit(base['Cal Year'], base['Value'], 1)
    ref = raw['Cal Year'].max()
    fixed = (ref - industrial_age_end)*slope
    def adj(r):
        return (r['Value'] + (ref-r['Cal Year'])*slope) if r['Cal Year']>=industrial_age_end else (r['Value']+fixed)
    raw['Temperature'] = raw.apply(adj, axis=1).round(3)
    for i in range(1,5):
        raw[f'Temp_Lag_{i}_Day'] = raw['Temperature'].shift(i)
    raw['Temp_Band']      = raw['Temperature'].round().astype(int).astype('category')
    raw['Temp_Lag1_Band'] = raw['Temp_Lag_1_Day'].round().astype(int).astype('category')
    raw['Temp_Lag2_Band'] = raw['Temp_Lag_2_Day'].round().astype(int).astype('category')
    cold2 = raw['Temperature'] < -1
    grp2  = (cold2 != cold2.shift()).cumsum()
    raw['Cold_Spell'] = (cold2.groupby(grp2).transform('sum')>=3).astype(int)
    return raw

@st.cache_data
def load_bank_holidays_data(file_input):
    raw = pd.read_csv(file_input)
    if 'Date' not in raw.columns: raise ValueError("Need 'Date'")
    df = raw.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    if df['Date'].isnull().any(): raise ValueError("Invalid dates")
    return raw, df

@st.cache_data
def load_demand_data(file_input):
    raw = pd.read_csv(file_input)
    if 'Date' not in raw.columns or 'ClaimFreq' not in raw.columns:
        raise ValueError("Need 'Date' & 'ClaimFreq'")
    df = raw.copy()
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    if df['Date'].isnull().any(): raise ValueError("Invalid dates")
    current = datetime.now().year
    yrs = df['Date'].dt.year
    if (yrs > current).any(): raise ValueError("Future dates")
    if (current-1) not in yrs.unique(): raise ValueError(f"Missing {current-1}")
    return raw, df
