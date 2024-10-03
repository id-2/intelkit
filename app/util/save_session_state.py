import json
import os

import pandas as pd
import polars as pl
import streamlit as st

pathA = "state"


def save_session_state(workflow):
    session_state = st.session_state.to_dict()
    print("session_state", session_state)
    path = f"{pathA}/{workflow}"
    if not os.path.exists(path):
        os.makedirs(path)
    values_to_store = {}
    for key, value in session_state.items():
        if not key.startswith(workflow) or key.startswith(
            "detect_case_patterns_intermediate_dfs"
        ):
            continue
        if isinstance(value, pd.DataFrame):
            print("is pandas")
            if value.empty:
                continue
            filename = f"{path}/{key}.csv"
            value.to_csv(filename, index=False)
        elif isinstance(value, pl.DataFrame):
            print("is polars")
            if value.is_empty():
                continue
            filename = f"{path}/{key}.csv"
            value.write_csv(filename)
            # what if its an array of dataframes?
        elif isinstance(value, list):
            print("is list")
            for i, df in enumerate(value):
                if isinstance(df, pd.DataFrame):
                    if value.empty:
                        continue
                    filename = f"{path}/{key}_{i}.csv"
                    df.to_csv(filename, index=False)
                elif isinstance(df, pl.DataFrame):
                    if value.is_empty():
                        continue
                    filename = f"{path}/{key}_{i}.csv"
                    df.write_csv(filename)
        else:
            values_to_store[key] = value

    filename = f"{path}/{workflow}.json"
    with open(filename, "w") as f:
        json.dump(values_to_store, f)
    st.success(f"Session state saved to {filename}")


# Function to load session state from a JSON file
def load_session_state(workflow):
    # load dataframes from state folder
    path = f"{pathA}/{workflow}"
    filename = f"{path}/{workflow}.json"
    if not os.path.exists(filename):
        st.error(f"Session state file {filename} not found")
        return

    for file in os.listdir(path):
        if file.startswith(workflow):
            if file.endswith(".csv"):
                key = file.replace(".csv", "")
                if key in st.session_state:
                    del st.session_state[key]
                st.session_state[key] = pd.read_csv(f"{path}/{file}")

    with open(filename) as f:
        session_state = json.load(f)
    for key, value in session_state.items():
        print("key", key)
        if key in st.session_state:
            del st.session_state[key]
        st.session_state[key] = value
        print("loaded polars", st.session_state[key])

    st.success(f"Session state loaded from {filename}")