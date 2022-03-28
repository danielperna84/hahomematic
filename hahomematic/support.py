"""Module to support hahomematic eco system."""
from __future__ import annotations

from copy import copy
import json
import logging
import os
import random
from typing import Any

import hahomematic.client as hm_client
from hahomematic.const import (
    ATTR_HM_ADDRESS,
    ATTR_HM_CHILDREN,
    ATTR_HM_PARENT,
    ATTR_HM_TYPE,
    DATA_NO_SAVE,
    DATA_SAVE_SUCCESS,
    DEFAULT_ENCODING,
)
from hahomematic.helpers import check_or_create_directory

_LOGGER = logging.getLogger(__name__)
DEVICE_DESCRIPTIONS_DIR = "export_device_descriptions"
PARAMSET_DESCRIPTIONS_DIR = "export_paramset_descriptions"


class DeviceExporter:
    """Export Devices from Cache."""

    def __init__(
        self, client: hm_client.Client, interface_id: str, device_address: str
    ):
        self._client = client
        self._central = client.central
        self._storage_folder = self._central.central_config.storage_folder
        self._interface_id = interface_id
        self._device_address = device_address
        self._random_id = "VCU%i" % random.randint(1000000, 9999999)

    async def export_data(self) -> None:
        """Export data."""
        device_descriptions: dict[
            str, Any
        ] = self._central.device_descriptions.get_device_with_channels(
            interface_id=self._interface_id, device_address=self._device_address
        )
        paramset_descriptions: dict[
            str, Any
        ] = await self._client.get_all_paramset_descriptions(
            list(device_descriptions.values())
        )
        device_type = device_descriptions[self._device_address][ATTR_HM_TYPE]
        filename = f"{device_type}.json"

        # anonymize device_descriptions
        anonymize_device_descriptions: list[Any] = []
        for device_description in device_descriptions.values():
            if device_description == {}:
                continue
            new_device_description = copy(device_description)
            new_device_description[ATTR_HM_ADDRESS] = self._anonymize_address(
                address=new_device_description[ATTR_HM_ADDRESS]
            )
            if new_device_description.get(ATTR_HM_PARENT):
                new_device_description[ATTR_HM_PARENT] = new_device_description[
                    ATTR_HM_ADDRESS
                ].split(":")[0]
            elif new_device_description.get(ATTR_HM_CHILDREN):
                new_device_description[ATTR_HM_CHILDREN] = [
                    self._anonymize_address(a)
                    for a in new_device_description[ATTR_HM_CHILDREN]
                ]
            anonymize_device_descriptions.append(new_device_description)

        # anonymize paramset_descriptions
        anonymize_paramset_descriptions: dict[str, Any] = {}
        for address, paramset_descriptions in paramset_descriptions.items():
            anonymize_paramset_descriptions[
                self._anonymize_address(address=address)
            ] = paramset_descriptions

        # Save device_descriptions for device to file.
        await self._save(
            file_dir=f"{self._storage_folder}/{DEVICE_DESCRIPTIONS_DIR}",
            filename=filename,
            data=anonymize_device_descriptions,
        )

        # Save device_descriptions for device to file.
        await self._save(
            file_dir=f"{self._storage_folder}/{PARAMSET_DESCRIPTIONS_DIR}",
            filename=filename,
            data=anonymize_paramset_descriptions,
        )

    def _anonymize_address(self, address: str) -> str:
        address_parts = address.split(":")
        address_parts[0] = self._random_id
        return ":".join(address_parts)

    async def _save(self, file_dir: str, filename: str, data: Any) -> int:
        """Save file to disk."""

        def _save() -> int:
            if not check_or_create_directory(file_dir):
                return DATA_NO_SAVE
            with open(
                file=os.path.join(file_dir, filename),
                mode="w",
                encoding=DEFAULT_ENCODING,
            ) as fptr:
                json.dump(data, fptr, indent=2)
            return DATA_SAVE_SUCCESS

        return await self._central.async_add_executor_job(_save)


async def save_device_definition(
    client: hm_client.Client, interface_id: str, device_address: str
) -> None:
    """Save device to file."""
    device_exporter = DeviceExporter(
        client=client, interface_id=interface_id, device_address=device_address
    )
    await device_exporter.export_data()
