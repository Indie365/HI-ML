#  ------------------------------------------------------------------------------------------
#  Copyright (c) Microsoft Corporation. All rights reserved.
#  Licensed under the MIT License (MIT). See LICENSE in the repo root for license information.
#  ------------------------------------------------------------------------------------------
"""
Tests for the functions in health.azure.azure_util
"""
import os
import time
from pathlib import Path
from typing import Optional
from unittest import mock
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from azureml.core.authentication import ServicePrincipalAuthentication
from azureml.core.conda_dependencies import CondaDependencies
from testhiml.health.azure.util import repository_root

import health.azure.azure_util as util
from health.azure.azure_util import (merge_conda_files, run_duration_string_to_seconds)
from health.azure.himl import AML_IGNORE_FILE, append_to_amlignore

RUN_ID = uuid4().hex
RUN_NUMBER = 42
EXPERIMENT_NAME = "fancy-experiment"


def oh_no() -> None:
    """
    Raise a simple exception. To be used as a side_effect for mocks.
    """
    raise ValueError("Throwing an exception")


@patch("health.azure.azure_util.Run")
def test_create_run_recovery_id(mock_run: MagicMock) -> None:
    """
    The recovery id created for a run
    """
    mock_run.id = RUN_ID
    mock_run.experiment.name = EXPERIMENT_NAME
    recovery_id = util.create_run_recovery_id(mock_run)
    assert recovery_id == EXPERIMENT_NAME + util.EXPERIMENT_RUN_SEPARATOR + RUN_ID


@pytest.mark.parametrize("on_azure", [True, False])
def test_is_running_on_azure_agent(on_azure: bool) -> None:
    with mock.patch.dict(os.environ, {"AGENT_OS": "LINUX" if on_azure else ""}):
        assert on_azure == util.is_running_on_azure_agent()


@patch("health.azure.azure_util.Workspace")
@patch("health.azure.azure_util.Experiment")
@patch("health.azure.azure_util.Run")
def test_fetch_run(mock_run: MagicMock, mock_experiment: MagicMock, mock_workspace: MagicMock) -> None:
    mock_run.id = RUN_ID
    mock_run.experiment = mock_experiment
    mock_experiment.name = EXPERIMENT_NAME
    recovery_id = EXPERIMENT_NAME + util.EXPERIMENT_RUN_SEPARATOR + RUN_ID
    mock_run.number = RUN_NUMBER
    with mock.patch("health.azure.azure_util.get_run", return_value=mock_run):
        run_to_recover = util.fetch_run(mock_workspace, recovery_id)
        # TODO: should we assert that the correct string is logged?
        assert run_to_recover.number == RUN_NUMBER
    mock_experiment.side_effect = oh_no
    with pytest.raises(Exception) as e:
        util.fetch_run(mock_workspace, recovery_id)
    assert str(e.value).startswith(f"Unable to retrieve run {RUN_ID}")


@patch("health.azure.azure_util.Run")
@patch("health.azure.azure_util.Experiment")
@patch("health.azure.azure_util.get_run")
def test_fetch_run_for_experiment(get_run: MagicMock, mock_experiment: MagicMock, mock_run: MagicMock) -> None:
    get_run.side_effect = oh_no
    mock_run.id = RUN_ID
    mock_experiment.get_runs = lambda: [mock_run, mock_run, mock_run]
    mock_experiment.name = EXPERIMENT_NAME
    with pytest.raises(Exception) as e:
        util.fetch_run_for_experiment(mock_experiment, RUN_ID)
    exp = f"Run {RUN_ID} not found for experiment: {EXPERIMENT_NAME}. Available runs are: {RUN_ID}, {RUN_ID}, {RUN_ID}"
    assert str(e.value) == exp


@patch("health.azure.azure_util.InteractiveLoginAuthentication")
def test_get_authentication(mock_interactive_authentication: MagicMock) -> None:
    with mock.patch.dict(os.environ, {}, clear=True):
        util.get_authentication()
        assert mock_interactive_authentication.called
    service_principal_id = "1"
    tenant_id = "2"
    service_principal_password = "3"
    with mock.patch.dict(
            os.environ,
            {
                util.SERVICE_PRINCIPAL_ID: service_principal_id,
                util.TENANT_ID: tenant_id,
                util.SERVICE_PRINCIPAL_PASSWORD: service_principal_password
            },
            clear=True):
        spa = util.get_authentication()
        assert isinstance(spa, ServicePrincipalAuthentication)
        assert spa._service_principal_id == service_principal_id
        assert spa._tenant_id == tenant_id
        assert spa._service_principal_password == service_principal_password


def test_get_secret_from_environment() -> None:
    env_variable_name = uuid4().hex.upper()
    env_variable_value = "42"
    with pytest.raises(ValueError) as e:
        util.get_secret_from_environment(env_variable_name)
    assert str(e.value) == f"There is no value stored for the secret named '{env_variable_name}'"
    assert util.get_secret_from_environment(env_variable_name, allow_missing=True) is None
    with mock.patch.dict(os.environ, {env_variable_name: env_variable_value}):
        assert util.get_secret_from_environment(env_variable_name) == env_variable_value


def test_to_azure_friendly_string() -> None:
    """
    Tests the to_azure_friendly_string function which should replace everything apart from a-zA-Z0-9_ with _, and
    replace multiple _ with a single _
    """
    bad_string = "full__0f_r*bb%sh"
    good_version = util.to_azure_friendly_string(bad_string)
    assert good_version == "full_0f_r_bb_sh"
    good_string = "Not_Full_0f_Rubbish"
    good_version = util.to_azure_friendly_string(good_string)
    assert good_version == good_string
    optional_string = None
    assert optional_string == util.to_azure_friendly_string(optional_string)


def test_split_recovery_id_fails() -> None:
    """
    Other tests test the main branch of split_recovery_id, but they do not test the exceptions
    """
    with pytest.raises(ValueError) as e:
        id = util.EXPERIMENT_RUN_SEPARATOR.join([str(i) for i in range(3)])
        util.split_recovery_id(id)
    assert str(e.value) == f"recovery_id must be in the format: 'experiment_name:run_id', but got: {id}"
    with pytest.raises(ValueError) as e:
        id = "foo_bar"
        util.split_recovery_id(id)
    assert str(e.value) == f"The recovery ID was not in the expected format: {id}"


@pytest.mark.parametrize(["id", "expected1", "expected2"],
                         [("foo:bar", "foo", "bar"),
                          ("foo:bar_ab_cd", "foo", "bar_ab_cd"),
                          ("a_b_c_00_123", "a_b_c", "a_b_c_00_123"),
                          ("baz_00_123", "baz", "baz_00_123"),
                          ("foo_bar_abc_123_456", "foo_bar_abc", "foo_bar_abc_123_456"),
                          # This is the run ID of a hyperdrive parent run. It only has one numeric part at the end
                          ("foo_bar_123", "foo_bar", "foo_bar_123"),
                          # This is a hyperdrive child run
                          ("foo_bar_123_3", "foo_bar", "foo_bar_123_3"),
                          ])
def test_split_recovery_id(id: str, expected1: str, expected2: str) -> None:
    """
    Check that run recovery ids are correctly parsed into experiment and run id.
    """
    assert util.split_recovery_id(id) == (expected1, expected2)


def test_merge_conda(random_folder: Path) -> None:
    """
    Tests the logic for merging Conda environment files.
    """
    env1 = """
channels:
  - defaults
  - pytorch
dependencies:
  - conda1=1.0
  - conda2=2.0
  - conda_both=3.0
  - pip:
      - azureml-sdk==1.7.0
      - foo==1.0
"""
    env2 = """
channels:
  - defaults
dependencies:
  - conda1=1.1
  - conda_both=3.0
  - pip:
      - azureml-sdk==1.6.0
      - bar==2.0
"""
    # Spurious test failures on Linux build agents, saying that they can't write the file. Wait a bit.
    time.sleep(0.5)
    file1 = random_folder / "env1.yml"
    file1.write_text(env1)
    file2 = random_folder / "env2.yml"
    file2.write_text(env2)
    # Spurious test failures on Linux build agents, saying that they can't read the file. Wait a bit.
    time.sleep(0.5)
    files = [file1, file2]
    merged_file = random_folder / "merged.yml"
    merge_conda_files(files, merged_file)
    assert merged_file.read_text().splitlines() == """channels:
- defaults
- pytorch
dependencies:
- conda1=1.0
- conda1=1.1
- conda2=2.0
- conda_both=3.0
- pip:
  - azureml-sdk==1.6.0
  - azureml-sdk==1.7.0
  - bar==2.0
  - foo==1.0
""".splitlines()
    conda_dep = CondaDependencies(merged_file)
    # We expect to see the union of channels.
    assert list(conda_dep.conda_channels) == ["defaults", "pytorch"]
    # Package version conflicts are not resolved, both versions are retained.
    assert list(conda_dep.conda_packages) == ["conda1=1.0", "conda1=1.1", "conda2=2.0", "conda_both=3.0"]
    assert list(conda_dep.pip_packages) == ["azureml-sdk==1.6.0", "azureml-sdk==1.7.0", "bar==2.0", "foo==1.0"]


@pytest.mark.parametrize(["s", "expected"],
                         [
                             ("1s", 1),
                             ("0.5m", 30),
                             ("1.5h", 90 * 60),
                             ("1.0d", 24 * 3600),
                             ("", None),
                         ])
def test_run_duration(s: str, expected: Optional[float]) -> None:
    actual = run_duration_string_to_seconds(s)
    assert actual == expected
    if expected:
        assert isinstance(actual, int)


def test_run_duration_fails() -> None:
    with pytest.raises(Exception):
        run_duration_string_to_seconds("17b")


def test_repository_root() -> None:
    root = repository_root()
    assert (root / "SECURITY.md").is_file()


def test_nonexisting_amlignore(random_folder: Path) -> None:
    """
    Test that we can create an .AMLignore file, and it gets deleted after use.
    """
    folder1 = "Added1"
    added_folders = [folder1]
    cwd = Path.cwd()
    amlignore = random_folder / AML_IGNORE_FILE
    assert not amlignore.is_file()
    os.chdir(random_folder)
    with append_to_amlignore(added_folders):
        new_contents = amlignore.read_text()
        for f in added_folders:
            assert f in new_contents
    assert not amlignore.is_file()
    os.chdir(cwd)