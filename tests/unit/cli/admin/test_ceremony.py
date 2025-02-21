# SPDX-FileCopyrightText: 2022 VMware Inc
#
# SPDX-License-Identifier: MIT

from unittest.mock import MagicMock

import pretend  # type: ignore
import pytest
from click import ClickException
from securesystemslib.keys import generate_ed25519_key

from repository_service_tuf.cli.admin import ceremony
from repository_service_tuf.cli.admin.ceremony import _key_is_duplicated
from repository_service_tuf.helpers.tuf import KeyInput, RoleSettingsInput


class TestCeremonyGroupCLI:
    def test__key_is_duplicated_different_key(self, fake_key):
        """
        Tests the existence of duplicates with a different given key and a
        different filepath.
        """

        duplicate_key = fake_key(key=generate_ed25519_key())
        rand_key_1 = fake_key(key=generate_ed25519_key())
        rand_key_2 = fake_key(key=generate_ed25519_key())
        rand_key_3 = fake_key(key=generate_ed25519_key())

        key_input_1 = KeyInput(
            filepath="filepath_1", password="passwd_1", key=rand_key_1
        )
        key_input_2 = KeyInput(
            filepath="filepath_2", password="passwd_2", key=rand_key_2
        )
        key_input_3 = KeyInput(
            filepath="filepath_3", password="passwd_3", key=rand_key_3
        )

        role_1_keys_inputs = {"root_1": key_input_1, "root_2": key_input_2}
        role_2_keys_inputs = {"bin_1": key_input_3}

        role1 = RoleSettingsInput(keys=role_1_keys_inputs)
        role2 = RoleSettingsInput(keys=role_2_keys_inputs)

        assert (
            _key_is_duplicated(
                [role1, role2], duplicate_key.key, "unique_filepath"
            )
            is False
        )

    def test__key_is_duplicated_same_key(self, fake_key):
        """
        Tests the existence of duplicates with the same given key and a
        different filepath.
        """
        duplicate_key = fake_key(key=generate_ed25519_key())
        rand_key_2 = fake_key(key=generate_ed25519_key())
        rand_key_3 = fake_key(key=generate_ed25519_key())

        key_input_1 = KeyInput(
            filepath="filepath_1", password="passwd_1", key=duplicate_key
        )
        key_input_2 = KeyInput(
            filepath="filepath_2", password="passwd_2", key=rand_key_2
        )
        key_input_3 = KeyInput(
            filepath="filepath_3", password="passwd_3", key=rand_key_3
        )

        role_1_keys_inputs = {"root_1": key_input_1, "root_2": key_input_2}
        role_2_keys_inputs = {"bin_1": key_input_3}

        role1 = RoleSettingsInput(keys=role_1_keys_inputs)
        role2 = RoleSettingsInput(keys=role_2_keys_inputs)

        assert (
            _key_is_duplicated(
                [role1, role2], duplicate_key.key, "unique_filepath"
            )
            is True
        )

        # testing when the duplicate key is in another item of the roles list
        assert (
            _key_is_duplicated(
                [role1, role2], rand_key_3.key, "unique_filepath"
            )
            is True
        )

    def test__key_is_duplicated_same_filepath(self, fake_key):
        """
        Tests the existence of duplicates with a different given key and the
        same filepath.
        """
        duplicate_key = fake_key(key=generate_ed25519_key())
        rand_key_1 = fake_key(key=generate_ed25519_key())
        rand_key_2 = fake_key(key=generate_ed25519_key())
        rand_key_3 = fake_key(key=generate_ed25519_key())

        key_input_1 = KeyInput(
            filepath="filepath_1", password="passwd_1", key=rand_key_1
        )
        key_input_2 = KeyInput(
            filepath="filepath_2", password="passwd_2", key=rand_key_2
        )
        key_input_3 = KeyInput(
            filepath="filepath_3", password="passwd_3", key=rand_key_3
        )

        role_1_keys_inputs = {"root_1": key_input_1, "root_2": key_input_2}
        role_2_keys_inputs = {"bin_1": key_input_3}

        role1 = RoleSettingsInput(keys=role_1_keys_inputs)
        role2 = RoleSettingsInput(keys=role_2_keys_inputs)

        assert (
            _key_is_duplicated([role1, role2], duplicate_key.key, "filepath_1")
            is True
        )

        # testing when duplicate filepath is in another item of the roles list
        assert (
            _key_is_duplicated([role1, role2], duplicate_key.key, "filepath_3")
            is True
        )

    def test__load_key(self):
        ceremony.import_ed25519_privatekey_from_file = pretend.call_recorder(
            lambda *a: {"k": "v"}
        )
        result = ceremony._load_key("fake_file", "fake_pass")

        assert result == ceremony.KeySchema(key={'k': 'v'}, error=None)
        assert ceremony.import_ed25519_privatekey_from_file.calls == [
            pretend.call("fake_file", "fake_pass")
        ]

    def test__load_key_crypto_error(self):
        ceremony.import_ed25519_privatekey_from_file = pretend.raiser(
            ceremony.CryptoError("Crypto Error tests")
        )
        result = ceremony._load_key("fake_file", "fake_pass")

        assert result == ceremony.KeySchema(
            key=None, error=(
                f":cross_mark: [red]Failed[/]: Crypto Error"
                " tests Check the password."
            )
        )

    def test__bootstrap(self, monkeypatch):
        mocked_request_server = pretend.stub(
            status_code=202,
            json=pretend.call_recorder(
                lambda: {
                    "data": {"task_id": "task_id_123"},
                    "message": "Bootstrap accepted.",
                }
            ),
        )
        monkeypatch.setattr(
            ceremony, "request_server", lambda *a, **kw: mocked_request_server
        )

        result = ceremony._bootstrap("http://fake-rstuf", {}, {})
        assert result == "task_id_123"
        assert mocked_request_server.json.calls == [pretend.call()]

    def test__bootstrap_not_202(self, monkeypatch):
        mocked_request_server = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(
                lambda: {
                    "data": {"task_id": "task_id_123"},
                    "message": "Bootstrap accepted.",
                }
            ),
        )
        monkeypatch.setattr(
            ceremony, "request_server", lambda *a, **kw: mocked_request_server
        )

        with pytest.raises(ClickException) as err:
            ceremony._bootstrap("http://fake-rstuf", {}, {})

        assert "Error 200" in str(err)
        assert mocked_request_server.json.calls == [pretend.call()]

    def test__bootstrap_not_no_message(self, monkeypatch):
        mocked_request_server = pretend.stub(
            status_code=202,
            json=pretend.call_recorder(
                lambda: {
                    "data": {"task_id": "task_id_123"},
                }
            ),
            text="No message available.",
        )
        monkeypatch.setattr(
            ceremony, "request_server", lambda *a, **kw: mocked_request_server
        )

        with pytest.raises(ClickException) as err:
            ceremony._bootstrap("http://fake-rstuf", {}, {})

        assert "No message available." in str(err)
        assert mocked_request_server.json.calls == [pretend.call()]

    def test__bootstrap_state(self, monkeypatch):
        fake_response_started = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(
                lambda: {
                    "data": {
                        "state": "STARTED",
                    }
                }
            ),
        )
        fake_response_success = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(
                lambda: {
                    "data": {
                        "state": "SUCCESS",
                        "result": {"details": {"bootstrap": True}},
                    }
                }
            ),
        )
        mocked_request_server = MagicMock()
        mocked_request_server.side_effect = [
            fake_response_started,
            fake_response_success,
        ]
        monkeypatch.setattr(ceremony, "request_server", mocked_request_server)

        result = ceremony._bootstrap_state(
            "task_id_123", "http://fake-server", {}
        )
        assert result is None
        assert fake_response_started.json.calls == [pretend.call()]
        assert fake_response_success.json.calls == [pretend.call()]

    def test__bootstrap_state_without_bootstrap_true(self, monkeypatch):
        fake_response_started = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(
                lambda: {
                    "data": {
                        "state": "STARTED",
                    }
                }
            ),
        )
        fake_response_success = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(
                lambda: {
                    "data": {
                        "state": "SUCCESS",
                    }
                }
            ),
        )
        mocked_request_server = MagicMock()
        mocked_request_server.side_effect = [
            fake_response_started,
            fake_response_success,
        ]
        monkeypatch.setattr(ceremony, "request_server", mocked_request_server)

        with pytest.raises(ClickException) as err:
            ceremony._bootstrap_state("task_id_123", "http://fake-server", {})

        assert "Something went wrong, result:" in str(err)
        assert fake_response_started.json.calls == [pretend.call()]
        assert fake_response_success.json.calls == [pretend.call()]

    def test__bootstrap_state_task_failure(self, monkeypatch):
        fake_response_started = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(
                lambda: {
                    "data": {
                        "state": "STARTED",
                        "result": {"details": {"bootstrap": True}},
                    }
                }
            ),
        )
        fake_response_success = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(
                lambda: {
                    "data": {
                        "state": "FAILURE",
                        "result": "SomeException: bla bla bla",
                    }
                }
            ),
            text="{'data': {'state': 'FAILURE','result': 'SomeException'}}",
        )
        mocked_request_server = MagicMock()
        mocked_request_server.side_effect = [
            fake_response_started,
            fake_response_success,
        ]
        monkeypatch.setattr(ceremony, "request_server", mocked_request_server)

        with pytest.raises(ClickException) as err:
            ceremony._bootstrap_state("task_id_123", "http://fake-server", {})

        assert "Failed:" in str(err)
        assert fake_response_started.json.calls == [pretend.call()]
        assert fake_response_success.json.calls == [pretend.call()]

    def test__bootstrap_state_not_200(self, monkeypatch):
        fake_response_started = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(
                lambda: {
                    "data": {
                        "state": "STARTED",
                        "result": {"details": {"bootstrap": True}},
                    }
                }
            ),
        )
        fake_response_success = pretend.stub(
            status_code=400,
            text="Bad request",
        )
        mocked_request_server = MagicMock()
        mocked_request_server.side_effect = [
            fake_response_started,
            fake_response_success,
        ]
        monkeypatch.setattr(ceremony, "request_server", mocked_request_server)

        with pytest.raises(ClickException) as err:
            ceremony._bootstrap_state("task_id_123", "http://fake-server", {})
        assert "Unexpected response Bad request" in str(err)
        assert fake_response_started.json.calls == [pretend.call()]

    def test__bootstrap_state_bootstrap_no_data(self, monkeypatch):
        fake_response = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(lambda: {"data": {}}),
            text=str("{'data': {}}"),
        )

        monkeypatch.setattr(
            ceremony, "request_server", lambda *a, **kw: fake_response
        )

        with pytest.raises(ClickException) as err:
            ceremony._bootstrap_state("task_id_123", "http://fake-server", {})

        assert "No data received" in str(err)
        assert fake_response.json.calls == [pretend.call()]

    def test__bootstrap_state_bootstrap_no_state(self, monkeypatch):
        fake_response = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(lambda: {"data": {"state": None}}),
            text=str("{'data': {}}"),
        )

        monkeypatch.setattr(
            ceremony, "request_server", lambda *a, **kw: fake_response
        )

        with pytest.raises(ClickException) as err:
            ceremony._bootstrap_state("task_id_123", "http://fake-server", {})

        assert "No state in data received" in str(err)
        assert fake_response.json.calls == [pretend.call()]

    def test_ceremony(self, client, test_context):
        test_result = client.invoke(ceremony.ceremony, obj=test_context)
        assert test_result.exit_code == 1
        assert (
            "Repository Metadata and Settings for the Repository Service "
            "for TUF"
        ) in test_result.output

    def test_ceremony_start_no(self, client, test_context):
        test_result = client.invoke(
            ceremony.ceremony, input="n\nn\n", obj=test_context
        )
        assert "Ceremony aborted." in test_result.output
        assert test_result.exit_code == 1

    def test_ceremony_start_not_ready_load_the_keys(
        self, client, test_context
    ):
        input_step1 = [
            "n",
            "y",
            "",
            "",
            "",
            "",
            "",
            "",
            "y",
            "http://www.example.com/repository",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
        input_step2 = ["n"]
        test_result = client.invoke(
            ceremony.ceremony,
            input="\n".join(input_step1 + input_step2),
            obj=test_context,
        )
        assert "Ceremony aborted." in test_result.output
        assert test_result.exit_code == 1

    def test_ceremony_start_default_values(
        self, client, fake_key, monkeypatch, test_context
    ):
        input_step1 = [
            "y",
            "y",
            "",
            "",
            "",
            "",
            "",
            "",
            "y",
            "https://github.com/vmware",
            "*, */*, */*/*, */*/*/*, */*/*/*/*, */*/*/*/*/*",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "4",
            "",
        ]
        input_step2 = [
            "Y",
            "tests/files/JimiHendrix.key",
            "strongPass",
            "tests/files/JanisJoplin.key",
            "strongPass",
            "tests/files/ChrisCornel.key",
            "strongPass",
            "tests/files/KurtCobain.key",
            "strongPass",
            "tests/files/snapshot1.key",
            "strongPass",
            "tests/files/timestamp1.key",
            "strongPass",
            "tests/files/JoeCocker.key",
            "strongPass",
            "tests/files/bins1.key",
            "strongPass",
            "y",
            "y",
            "y",
            "y",
            "y",
            "y",
        ]

        from securesystemslib.keys import generate_ed25519_key

        fake__load_key = pretend.call_recorder(
            lambda *a, **kw: fake_key(key=generate_ed25519_key())
        )
        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony._load_key",
            fake__load_key,
        )

        test_result = client.invoke(
            ceremony.ceremony,
            input="\n".join(input_step1 + input_step2),
            obj=test_context,
        )

        assert test_result.exit_code == 0
        assert "Role: root" in test_result.output
        assert "Number of Keys: 1" in test_result.output
        assert "Threshold: 1" in test_result.output
        assert "Keys Type: offline" in test_result.output
        assert "JimiHendrix.key" in test_result.output
        assert "Role: targets" in test_result.output
        assert "Number of Keys: 1" in test_result.output
        assert "JanisJoplin.key" in test_result.output
        assert "ChrisCornel.key" in test_result.output
        assert "Role: snapshot" in test_result.output
        assert "Keys Type: online" in test_result.output
        assert "Role: timestamp" in test_result.output
        assert "KurtCobain.key" in test_result.output
        assert "JoeCocker.key" in test_result.output
        assert "bins1.key" in test_result.output
        # passwords not shown in output
        assert "strongPass" not in test_result.output

    def test_ceremony_start_default_values_reconfigure_one_role(
        self, client, fake_key, monkeypatch, test_context
    ):
        input_step1 = [
            "y",
            "y",
            "",
            "",
            "",
            "",
            "",
            "",
            "y",
            "http://www.example.com/repository",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
        input_step2 = [
            "Y",
            "tests/files/JimiHendrix.key",
            "strongPass",
            "tests/files/JanisJoplin.key",
            "strongPass",
            "tests/files/ChrisCornel.key",
            "strongPass",
            "tests/files/KurtCobain.key",
            "strongPass",
            "tests/files/snapshot1.key",
            "strongPass",
            "tests/files/timestamp1.key",
            "strongPass",
            "tests/files/JoeCocker.key",
            "strongPass",
            "tests/files/bins1.key",
            "strongPass",
            "y",
            "y",
            "n",
            "",
            "",
            "",
            "tests/files/snapshot1.key",
            "strongPass",
            "y",
            "y",
            "y",
            "y",
        ]

        fake__load_key = pretend.call_recorder(
            lambda *a, **kw: fake_key(key=generate_ed25519_key())
        )
        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony._load_key",
            fake__load_key,
        )

        test_result = client.invoke(
            ceremony.ceremony,
            input="\n".join(input_step1 + input_step2),
            obj=test_context,
        )
        assert test_result.exit_code == 0
        assert "Role: root" in test_result.output
        assert "Number of Keys: 1" in test_result.output
        assert "Threshold: 1" in test_result.output
        assert "Keys Type: offline" in test_result.output
        assert "JimiHendrix.key" in test_result.output
        assert "Role: targets" in test_result.output
        assert "Number of Keys: 1" in test_result.output
        assert "JanisJoplin.key" in test_result.output
        assert "ChrisCornel.key" in test_result.output
        assert "Role: snapshot" in test_result.output
        assert "Keys Type: online" in test_result.output
        assert "Role: timestamp" in test_result.output
        assert "KurtCobain.key" in test_result.output
        assert "JoeCocker.key" in test_result.output
        assert "bins1.key" in test_result.output
        # passwords not shown in output
        assert "strongPass" not in test_result.output

    def test_ceremony_with_flag_bootstrap(
        self, client, fake_key, monkeypatch, test_context
    ):
        input_step1 = [
            "y",
            "y",
            "",
            "",
            "",
            "",
            "",
            "",
            "y",
            "http://www.example.com/repository",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
        input_step2 = [
            "Y",
            "tests/files/JimiHendrix.key",
            "strongPass",
            "tests/files/JanisJoplin.key",
            "strongPass",
            "tests/files/ChrisCornel.key",
            "strongPass",
            "tests/files/KurtCobain.key",
            "strongPass",
            "tests/files/snapshot1.key",
            "strongPass",
            "tests/files/timestamp1.key",
            "strongPass",
            "tests/files/JoeCocker.key",
            "strongPass",
            "tests/files/bins1.key",
            "strongPass",
            "y",
            "y",
            "y",
            "y",
            "y",
            "y",
        ]

        mocked_check_server = pretend.call_recorder(
            lambda s: {"Authorization": "Bearer test"}
        )
        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony._check_server",
            mocked_check_server,
        )

        fake_response_get = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(lambda: {"bootstrap": False}),
        )
        fake_response_post = pretend.stub(
            status_code=202,
            json=pretend.call_recorder(
                lambda: {"message": "Bootstrap accepted."}
            ),
        )
        mocked_request_server = MagicMock()
        mocked_request_server.side_effect = [
            fake_response_get,
            fake_response_post,
        ]

        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony.request_server",
            mocked_request_server,
        )

        fake__load_key = pretend.call_recorder(
            lambda *a, **kw: fake_key(key=generate_ed25519_key())
        )
        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony._load_key",
            fake__load_key,
        )

        # simulate the settings file
        test_context["settings"].SERVER = "fake-server"
        test_context["settings"].TOKEN = "test-token"
        # write settings
        test_result = client.invoke(
            ceremony.ceremony,
            ["--bootstrap"],
            input="\n".join(input_step1 + input_step2),
            obj=test_context,
        )

        assert test_result.exit_code == 0
        assert "Ceremony done." in test_result.output
        # passwords not shown in output
        assert "strongPass" not in test_result.output

    def test_ceremony_with_flag_bootstrap_already_done(
        self, client, monkeypatch, test_context
    ):
        mocked_check_server = pretend.call_recorder(
            lambda s: {"Authorization": "Bearer test"}
        )
        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony._check_server",
            mocked_check_server,
        )

        mocked_request_server = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(
                lambda: {
                    "bootstrap": True,
                    "message": "System already has a Metadata.",
                }
            ),
        )

        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony.request_server",
            lambda *a, **kw: mocked_request_server,
        )

        # simulate the settings file
        test_context["settings"].SERVER = "fake-server"
        test_context["settings"].TOKEN = "test-token"

        test_result = client.invoke(
            ceremony.ceremony, ["--bootstrap"], obj=test_context
        )

        assert test_result.exit_code == 1
        assert "System already has a Metadata." in test_result.output

    def test_ceremony_with_flag_bootstrap_forbidden(
        self, client, monkeypatch, test_context
    ):
        mocked_check_server = pretend.call_recorder(
            lambda s: {"Authorization": "Bearer test"}
        )
        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony._check_server",
            mocked_check_server,
        )

        mocked_request_server = pretend.stub(
            status_code=401,
            json=pretend.call_recorder(
                lambda: {
                    "detail": "Unauthorized.",
                }
            ),
        )

        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony.request_server",
            lambda *a, **kw: mocked_request_server,
        )

        # simulate the settings file
        test_context["settings"].SERVER = "fake-server"
        test_context["settings"].TOKEN = "test-token"

        test_result = client.invoke(
            ceremony.ceremony, ["--bootstrap"], obj=test_context
        )

        assert test_result.exit_code == 1
        assert "Error 401 Unauthorized." in test_result.output

    def test_ceremony_with_flag_bootstrap_failed_post(
        self, client, fake_key, monkeypatch, test_context
    ):
        input_step1 = [
            "y",
            "y",
            "",
            "",
            "",
            "",
            "",
            "",
            "y",
            "http://www.example.com/repository",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
        input_step2 = [
            "Y",
            "tests/files/JimiHendrix.key",
            "strongPass",
            "tests/files/JanisJoplin.key",
            "strongPass",
            "tests/files/ChrisCornel.key",
            "strongPass",
            "tests/files/KurtCobain.key",
            "strongPass",
            "tests/files/snapshot1.key",
            "strongPass",
            "tests/files/timestamp1.key",
            "strongPass",
            "tests/files/JoeCocker.key",
            "strongPass",
            "tests/files/bins1.key",
            "strongPass",
            "y",
            "y",
            "y",
            "y",
            "y",
            "y",
        ]

        mocked_check_server = pretend.call_recorder(
            lambda s: {"Authorization": "Bearer test"}
        )
        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony._check_server",
            mocked_check_server,
        )

        fake_response_get = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(lambda: {"bootstrap": False}),
        )
        fake_response_post = pretend.stub(
            status_code=403,
            json=pretend.call_recorder(lambda: {"detail": "Forbidden"}),
        )
        mocked_request_server = MagicMock()
        mocked_request_server.side_effect = [
            fake_response_get,
            fake_response_post,
        ]

        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony.request_server",
            mocked_request_server,
        )

        fake__load_key = pretend.call_recorder(
            lambda *a, **kw: fake_key(key=generate_ed25519_key())
        )
        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony._load_key",
            fake__load_key,
        )

        # simulate the settings file
        test_context["settings"].SERVER = "fake-server"
        test_context["settings"].TOKEN = "test-token"
        # write settings
        test_result = client.invoke(
            ceremony.ceremony,
            ["--bootstrap"],
            input="\n".join(input_step1 + input_step2),
            obj=test_context,
        )

        assert test_result.exit_code == 1
        assert "Error 403 Forbidden" in test_result.output

    def test_ceremony_with_flag_bootstrap_unexpected_error(
        self, client, fake_key, monkeypatch, test_context
    ):
        input_step1 = [
            "y",
            "y",
            "",
            "",
            "",
            "",
            "",
            "",
            "y",
            "http://www.example.com/repository",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ]
        input_step2 = [
            "Y",
            "tests/files/JimiHendrix.key",
            "strongPass",
            "tests/files/JanisJoplin.key",
            "strongPass",
            "tests/files/ChrisCornel.key",
            "strongPass",
            "tests/files/KurtCobain.key",
            "strongPass",
            "tests/files/snapshot1.key",
            "strongPass",
            "tests/files/timestamp1.key",
            "strongPass",
            "tests/files/JoeCocker.key",
            "strongPass",
            "tests/files/bins1.key",
            "strongPass",
            "y",
            "y",
            "y",
            "y",
            "y",
            "y",
        ]

        mocked_check_server = pretend.call_recorder(
            lambda s: {"Authorization": "Bearer test"}
        )
        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony._check_server",
            mocked_check_server,
        )

        fake_response_get = pretend.stub(
            status_code=200,
            json=pretend.call_recorder(lambda: {"bootstrap": False}),
        )
        fake_response_post = pretend.stub(
            status_code=202,
            json=pretend.call_recorder(
                lambda: {
                    "detail": "Unexpected error, message queue connection"
                }
            ),
            text="<200> 'detail': 'Unexpected error, queue connection'",
        )
        mocked_request_server = MagicMock()
        mocked_request_server.side_effect = [
            fake_response_get,
            fake_response_post,
        ]

        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony.request_server",
            mocked_request_server,
        )

        fake__load_key = pretend.call_recorder(
            lambda *a, **kw: fake_key(key=generate_ed25519_key())
        )
        monkeypatch.setattr(
            "repository_service_tuf.cli.admin.ceremony._load_key",
            fake__load_key,
        )

        # simulate the settings file
        test_context["settings"].SERVER = "fake-server"
        test_context["settings"].TOKEN = "test-token"
        # write settings
        test_result = client.invoke(
            ceremony.ceremony,
            ["--bootstrap"],
            input="\n".join(input_step1 + input_step2),
            obj=test_context,
        )

        assert test_result.exit_code == 1
        assert "Unexpected error, queue connection" in test_result.output
