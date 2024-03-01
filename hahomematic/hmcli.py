#!/usr/bin/python3
"""Commandline tool to query HomeMatic hubs via XML-RPC."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from xmlrpc.client import ServerProxy

from hahomematic.const import ParamsetKey
from hahomematic.support import build_headers, build_xml_rpc_uri, get_tls_context


def main() -> None:
    """Start the cli."""
    parser = argparse.ArgumentParser(
        description="Commandline tool to query HomeMatic hubs via XML-RPC",
    )
    parser.add_argument(
        "--host",
        "-H",
        required=True,
        type=str,
        help="Hostname / IP address to connect to",
    )
    parser.add_argument(
        "--port",
        "-p",
        required=True,
        type=int,
        help="Port to connect to",
    )
    parser.add_argument(
        "--path",
        type=str,
        help="Path, used for heating groups",
    )
    parser.add_argument(
        "--username",
        "-U",
        nargs="?",
        help="Username required for access",
    )
    parser.add_argument(
        "--password",
        "-P",
        nargs="?",
        help="Password required for access",
    )
    parser.add_argument(
        "--tls",
        "-t",
        action="store_true",
        help="Enable TLS encryption",
    )
    parser.add_argument(
        "--verify",
        "-v",
        action="store_true",
        help="Verify TLS encryption",
    )
    parser.add_argument(
        "--json",
        "-j",
        action="store_true",
        help="Output as JSON",
    )
    parser.add_argument(
        "--address",
        "-a",
        required=True,
        type=str,
        help="Address of HomeMatic device, including channel",
    )
    parser.add_argument(
        "--paramset_key",
        default=ParamsetKey.VALUES,
        choices=[ParamsetKey.VALUES, ParamsetKey.MASTER],
        help="Paramset of HomeMatic device. Default: VALUES",
    )
    parser.add_argument(
        "--parameter",
        required=True,
        help="Parameter of HomeMatic device",
    )
    parser.add_argument(
        "--value",
        type=str,
        help="Value to set for parameter. Use 0/1 for boolean",
    )
    parser.add_argument(
        "--type",
        choices=["int", "float", "bool"],
        help="Type of value when setting a value. Using str if not provided",
    )
    args = parser.parse_args()

    url = build_xml_rpc_uri(
        host=args.host,
        port=args.port,
        path=args.path,
        tls=args.tls,
    )
    headers = build_headers(username=args.username, password=args.password)
    context = None
    if args.tls:
        context = get_tls_context(verify_tls=args.verify)
    proxy = ServerProxy(url, context=context, headers=headers)

    try:
        if args.paramset_key == ParamsetKey.VALUES and args.value is None:
            proxy.getValue(args.address, args.parameter)
            if args.json:
                pass
            else:
                pass
            sys.exit(0)
        elif args.paramset_key == ParamsetKey.VALUES and args.value:
            value: Any
            if args.type == "int":
                value = int(args.value)
            elif args.type == "float":
                value = float(args.value)
            elif args.type == "bool":
                value = bool(int(args.value))
            else:
                value = args.value
            proxy.setValue(args.address, args.parameter, value)
            sys.exit(0)
        elif args.paramset_key == ParamsetKey.MASTER and args.value is None:
            paramset: dict[str, Any] | None
            if (paramset := proxy.getParamset(args.address, args.paramset_key)) and paramset.get(  # type: ignore[assignment] # noqa: E501
                args.parameter
            ):
                if args.json:
                    pass
                else:
                    pass
            sys.exit(0)
        elif args.paramset_key == ParamsetKey.MASTER and args.value:
            if args.type == "int":
                value = int(args.value)
            elif args.type == "float":
                value = float(args.value)
            elif args.type == "bool":
                value = bool(int(args.value))
            else:
                value = args.value
            proxy.putParamset(args.address, args.paramset_key, {args.parameter: value})
            sys.exit(0)
    except Exception:
        sys.exit(1)


if __name__ == "__main__":
    main()
