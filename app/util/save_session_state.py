import json
import os
import time

import pandas as pd
import polars as pl
import streamlit as st
from numpy import ndarray

from toolkit.detect_case_patterns.record_counter import RecordCounter

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


def save_state(
    workflow, state: dict, state_path: str = "state", is_child_object=False
) -> dict:
    path = f"{state_path}/{workflow}"
    values_to_store = {}
    if not os.path.exists(path):
        os.makedirs(path)
    for key, value in state.items():
        if not key.startswith(workflow) and not is_child_object:
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
                if save_df(key + ".obj." + dict_key, value[dict_key], path):
                    continue
                vals = save_state(workflow, value_only, state_path, True)
                if key not in values_to_store:
                    values_to_store[key] = {}
                values_to_store[key].update(vals)
            continue
        if isinstance(value, RecordCounter | ndarray):
            continue
        values_to_store[key] = value

    return values_to_store


def save_session_state(workflow, state_path: str = "state") -> None:
    session_state = st.session_state.to_dict()
    if not session_state.items():
        return
    values_to_store = save_state(workflow, session_state)
    filename = f"{state_path}/{workflow}.json"
    # get date and time
    metadata = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}
    values_to_store["metadata"] = metadata
    with open(filename, "w") as f:
        json.dump(values_to_store, f)
    st.success(f"Session state saved to {filename}")


def last_session_metadata(workflow):
    filename = f"{state_path}/{workflow}.json"

    with open(filename) as f:
        state = json.load(f)
        if "metadata" in state:
            return state["metadata"]
        return {}


def load_session_state(workflow):
    # load dataframes from state folder
    path = f"{state_path}/{workflow}"
    filename = f"{state_path}/{workflow}.json"
    if not os.path.exists(filename):
        st.error(f"Session state file {filename} not found")
        return

    with open(filename) as f:
        session_state = json.load(f)
        session_state.pop("metadata", None)
        for key, value in session_state.items():
            if key in st.session_state:
                del st.session_state[key]
            st.session_state[key] = value

    for file in os.listdir(path):
        if file.startswith(workflow):
            if file.endswith(".csv"):
                key = file.replace(".csv", "")
                if ".obj." in key:
                    child_key = key.split(".obj.")[1]
                    parent_key = key.split(".obj.")[0]
                    readdd = pd.read_csv(f"{path}/{file}")
                    if parent_key not in st.session_state:
                        st.session_state[parent_key] = {}
                        # st.session_state[parent_key] = {
                        #     child_key: = pd.read_csv(
                        #     f"{path}/detect_case_patterns_self.detect_case_patterns_input_df.csv"
                        # )
                        # updase session state
                    st.session_state[parent_key]["input"] = readdd
                else:
                    st.session_state[key] = pd.read_csv(f"{path}/{file}")

    st.success(f"Session state loaded from {filename}")