import json
import os
from collections import defaultdict

import pandas as pd
import polars as pl
import streamlit as st

state_path = "state"


def save_df(key, value, path):
    if isinstance(value, pd.DataFrame):
        if not value.empty:
            filename = f"{path}/{key}.csv"
            value.to_csv(filename, index=False)
        return True
    if isinstance(value, pl.DataFrame):
        if not value.is_empty():
            filename = f"{path}/{key}.csv"
            value.write_csv(filename)
        return True
    return False


def save_state(workflow, state: dict, state_path: str = "state"):
    path = f"{state_path}/{workflow}"
    values_to_store = {}
    if not os.path.exists(path):
        os.makedirs(path)
    for key, value in state.items():
        if not key.startswith(workflow) or key.startswith(
            "detect_case_patterns_intermediate_dfs"
        ):
            continue
        if save_df(key, value, path):
            continue
        if isinstance(value, list):
            for i, v in enumerate(value):
                value_only = {}
                value_only[f"{key}_{i}"] = v
                save_state(workflow, value_only, state_path)
            continue
        if isinstance(value, dict):
            for dict_key in value:
                value_only = {}
                value_only[dict_key] = value[dict_key]
                vals = save_state(workflow, value_only, state_path)
                if key not in values_to_store:
                    values_to_store[key] = {}
                values_to_store[key].update(vals)
            continue
        values_to_store[key] = value

    return values_to_store


def save_session_state(workflow, state_path: str = "state") -> None:
    session_state = st.session_state.to_dict()
    if not session_state.items():
        return
    values_to_store = save_state(workflow, session_state)
    filename = f"{state_path}/workflow/{workflow}.json"
    with open(filename, "w") as f:
        json.dump(values_to_store, f)
    st.success(f"Session state saved to {filename}")


def load_session_state(workflow):
    # load dataframes from state folder
    path = f"{state_path}/{workflow}"
    filename = f"{state_path}/{workflow}.json"
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
                print("key", key)
                print(st.session_state[key])
    with open(filename) as f:
        session_state = json.load(f)
    for key, value in session_state.items():
        if key in st.session_state:
            del st.session_state[key]
        print("value", value)
        st.session_state[key] = value

    st.success(f"Session state loaded from {filename}")