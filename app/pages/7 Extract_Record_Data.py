# noqa: N999
# Copyright (c) 2024 Microsoft Corporation. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project.
#
import asyncio

import pandas as pd
import streamlit as st
from components.app_loader import load_multipage_app
from util.helper_fn import app_in_dev_mode

import app.workflows.extract_record_data.variables as erd_variables
import app.workflows.extract_record_data.workflow as erd_workflow

workflow = "extract_record_data"

async def main():
    st.set_page_config(
        layout="wide",
        initial_sidebar_state="collapsed",
        page_icon="app/myapp.ico",
        page_title="Intelligence Toolkit | Extract Record Data",
    )
    sv = erd_variables.SessionVariables(workflow)
    load_multipage_app(sv, workflow)

    try:
        await erd_workflow.create(sv, workflow)
    except Exception as e:
        if app_in_dev_mode():
            st.exception(e)
        else:
            st.error(f"An error occurred: {e}")


if __name__ == "__main__":
    asyncio.run(main())
