# Copyright (c) 2024 Microsoft Corporation. All rights reserved.
# Licensed under the MIT license. See LICENSE file in the project.
#
# ruff: noqa: S101
import os
import tempfile

import pandas as pd
import polars as pl

from app.util.session_generate_store_values import (
    generate_store_values,
    generate_store_values_df,
)

temp_folder_name = "temp"
workflow_name = "test_workflow"


class Testgenerate_store_valuesDF:
    def test_empty_pd(self) -> None:
        pd_empty = pd.DataFrame()
        with tempfile.TemporaryDirectory() as temp_folder:
            result = generate_store_values_df(workflow_name, pd_empty, temp_folder)
            assert result is True
            assert not os.path.exists(f"{temp_folder}/{workflow_name}/workflow.csv")

    def test_empty_pl(self) -> None:
        pl_empty = pl.DataFrame()
        with tempfile.TemporaryDirectory() as temp_folder:
            result = generate_store_values_df(workflow_name, pl_empty, temp_folder)
            assert result is True
            assert not os.path.exists(f"{temp_folder}/workflow.csv")

    def test_not_df(self) -> None:
        with tempfile.TemporaryDirectory() as temp_folder:
            result = generate_store_values_df(workflow_name, "", temp_folder)
            assert not os.path.exists(f"{temp_folder}/workflow.csv")
            assert result is False

    def test_pandas(self) -> None:
        pd_df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        key = "key_df_pd"
        with tempfile.TemporaryDirectory() as temp_folder:
            result = generate_store_values_df(key, pd_df, temp_folder)
            df = pd.read_csv(f"{temp_folder}/{key}.csv")
            assert result is True
            assert df.equals(pd_df)

    def test_polars(self) -> None:
        pl_df = pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        key = "key_df_pl"
        with tempfile.TemporaryDirectory() as temp_folder:
            result = generate_store_values_df(key, pl_df, temp_folder)
            df = pl.read_csv(f"{temp_folder}/{key}.csv")
            assert result is True
            assert df.equals(pl_df)


class TestSaveState:
    def test_empty(self) -> None:
        state = {}
        result = generate_store_values(workflow_name, state)
        assert result == {}

    def test_pandas(self) -> None:
        key = "workflow_df"
        state = {key: pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})}
        with tempfile.TemporaryDirectory() as temp_folder:
            result = generate_store_values(workflow_name, state, temp_folder)
            assert result == {}
            assert os.path.exists(f"{temp_folder}/{workflow_name}/{key}.csv")
            df = pd.read_csv(f"{temp_folder}/{workflow_name}/{key}.csv")
            assert df.equals(state[key])

    def test_polars(self) -> None:
        key = "workflow_df"
        state = {key: pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})}
        with tempfile.TemporaryDirectory() as temp_folder:
            result = generate_store_values(workflow_name, state, temp_folder)
            assert result == {}
            assert os.path.exists(f"{temp_folder}/{workflow_name}/{key}.csv")
            df = pl.read_csv(f"{temp_folder}/{workflow_name}/{key}.csv")
            assert df.equals(state[key])

    def test_array_pandas(self) -> None:
        key = "workflow_df_arr"
        state = {
            key: [
                pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}),
                pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}),
            ]
        }
        with tempfile.TemporaryDirectory() as temp_folder:
            path = f"{temp_folder}/{workflow_name}"
            result = generate_store_values(workflow_name, state, temp_folder)
            df0 = pd.read_csv(f"{path}/{key}_0.csv")
            df1 = pd.read_csv(f"{path}/{key}_1.csv")

            assert result == {}
            assert df0.equals(state[key][0])
            assert df1.equals(state[key][1])

    def test_array_polars(self) -> None:
        key = "workflow_df_arr"
        state = {
            key: [
                pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}),
                pl.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}),
            ]
        }
        with tempfile.TemporaryDirectory() as temp_folder:
            path = f"{temp_folder}/{workflow_name}"
            result = generate_store_values(workflow_name, state, temp_folder)
            df0 = pl.read_csv(f"{path}/{key}_0.csv")
            df1 = pl.read_csv(f"{path}/{key}_1.csv")

            assert result == {}
            assert df0.equals(state[key][0])
            assert df1.equals(state[key][1])

    def test_int(self) -> None:
        state = {"any_int": 1}
        result = generate_store_values(workflow_name, state)
        assert result == state

    def test_str(self) -> None:
        state = {"str_test": "test"}
        result = generate_store_values(workflow_name, state)
        assert result == state

    def test_dict(self) -> None:
        state = {"str_test": {"key1": "value1", "key2": "value2"}}
        result = generate_store_values(workflow_name, state)
        assert result == state

    def test_int_with_df(self) -> None:
        state = {"any_int": 1, "df0": pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})}
        with tempfile.TemporaryDirectory() as temp_folder:
            result = generate_store_values(workflow_name, state, temp_folder)
            assert result == {"any_int": 1}
            assert os.path.exists(f"{temp_folder}/{workflow_name}/df0.csv")
