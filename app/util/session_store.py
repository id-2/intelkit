import json
import os
import time

import pandas as pd
import polars as pl
import streamlit as st
from numpy import ndarray

from toolkit.helpers.decorators import ToolkitWorkflow

state_path = "state"


def store_df(key, value, path):
    filename = f"{path}/{key}.csv"
    if isinstance(value, pd.DataFrame):
        if not value.empty:
            value.to_csv(filename, index=False)
        return True
    if isinstance(value, pl.DataFrame):
        if not value.is_empty():
            value.write_csv(filename)
        return True
    return False


def delete_store(workflow, state_path: str = "state"):
    path = f"{state_path}/{workflow}"
    filename = f"{state_path}/{workflow}.json"
    if os.path.exists(filename):
        os.remove(filename)
    if os.path.exists(path):
        for file in os.listdir(path):
            os.remove(f"{path}/{file}")
        os.rmdir(path)
        st.success(f"Session state deleted for {workflow}")
    else:
        st.error(f"Session state folder {path} not found")


def generate_store_values(
    workflow, state: dict, state_path: str = "state", is_child_object=False
) -> dict:
    path = f"{state_path}/{workflow}"
    values_to_store = {}
    if not os.path.exists(path):
        os.makedirs(path)

    for key, value in state.items():
        if not key.startswith(workflow) and not is_child_object:
            continue
        if isinstance(value, ToolkitWorkflow | ndarray):
            continue
        if store_df(key, value, path):
            continue
        if isinstance(value, list):
            if not value:
                values_to_store[key] = []
            else:
                for i, v in enumerate(value):
                    value_only = {f"{key}_{i}": v}
                    generate_store_values(workflow, value_only, state_path)
            continue
        if isinstance(value, dict):
            for dict_key, dict_value in value.items():
                if store_df(f"{key}.obj.{dict_key}", dict_value, path):
                    continue
                nested_values = generate_store_values(
                    workflow, {dict_key: dict_value}, state_path, True
                )
                if key not in values_to_store:
                    values_to_store[key] = {}
                values_to_store[key].update(nested_values)
            continue

        values_to_store[key] = value

    return values_to_store


def store(workflow, state_path: str = "state") -> None:
    session_state = st.session_state.to_dict()
    if not session_state:
        st.warning("No session state to store.")
        return

    values_to_store = generate_store_values(workflow, session_state, state_path)

    filename = f"{state_path}/{workflow}.json"
    metadata = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}
    values_to_store["metadata"] = metadata

    try:
        with open(filename, "w") as f:
            json.dump(values_to_store, f, indent=4)
    except Exception as e:
        st.error(f"Error saving session state: {e}")


def last_session_metadata(workflow):
    filename = f"{state_path}/{workflow}.json"
    if os.path.exists(filename):
        with open(filename) as f:
            state = json.load(f)
            if "metadata" in state:
                return state["metadata"]
    return {}


def load_store(workflow):
    path = f"{state_path}/{workflow}"
    filename = f"{state_path}/{workflow}.json"
    if not os.path.exists(filename):
        st.error(f"Session state file {filename} not found")
        return

    try:
        with open(filename) as f:
            session_state = json.load(f)
            session_state.pop("metadata", None)
            for key, value in session_state.items():
                st.session_state[key] = value

        for file in os.listdir(path):
            if file.endswith(".csv"):
                key = file.replace(".csv", "")
                file_path = f"{path}/{file}"
                if ".obj." in key:
                    parent_key, child_key = key.split(".obj.")
                    df = pd.read_csv(file_path)
                    if parent_key not in st.session_state:
                        st.session_state[parent_key] = {}
                    st.session_state[parent_key][child_key] = df
                else:
                    st.session_state[key] = pd.read_csv(file_path)
    except Exception as e:
        st.error(f"Error loading session state: {e}")