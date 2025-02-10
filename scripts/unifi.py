#!/usr/bin/env python3

import json
import click
import unificontrol
from unificontrol import UnifiClient
from unificontrol.metaprogram import UnifiAPICall

pass_unifi_client = click.make_pass_decorator(UnifiClient)

@click.group(help="Command line interface to the Unifi Control", context_settings={'show_default': True})
@click.option('--host', '-h', default='localhost', help="Hostname of Unifi controller")
@click.option('--port', '-p', default=8443, help="Port number for Unifi controller")
@click.option('--site', '-s', default='default', help="Site ID")
@click.option('--username', '-u', default='admin', help="User name")
@click.option('--path-prefix', '-u', default='', help="Path prefix to access API resources under (e.g. proxy/network)")
@click.password_option(help="Password (prompt if not present)", confirmation_prompt=False)
@click.pass_context
def unifi_test(ctx, host, port, username, password, site, path_prefix):
    client = unificontrol.UnifiClient(host=host, port=port, username=username, password=password,
                                 site=site, path_prefix=path_prefix)

    ctx.obj = client

@unifi_test.command("api-call")
@click.option("--api-version", type=int, default=1)
@click.argument("path", type=str)
@pass_unifi_client
def cli_api_call(unifi_client: UnifiClient, api_version: int, path: str):
    """Execute a custom API command"""
    custom_cmd = UnifiAPICall("Command Line API Call", path, api_version=api_version)

    cmd_response = custom_cmd(unifi_client)
    print(json.dumps(cmd_response, indent=4))

if __name__ == "__main__":
    unifi_test(auto_envvar_prefix="UNIFI_TEST")
