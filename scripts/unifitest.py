#!/usr/bin/env python3

import json
import click
import unificontrol

@click.command(help="Test the connections to a Unifi controller")
@click.option('--host', '-h', default='localhost', help="Hostname of Unifi controller")
@click.option('--port', '-p', default=8443, help="Port number for Unifi controller")
@click.option('--site', '-s', default='default', help="Site ID")
@click.option('--username', '-u', default='admin', help="User name")
@click.option('--path-prefix', '-u', default='', help="Path prefix to access API resources under (e.g. proxy/network)")
@click.password_option(help="Password (prompt if not present)", confirmation_prompt=False)
def unifi_test(host, port, username, password, site, path_prefix):
    c = unificontrol.UnifiClient(host=host, port=port, username=username, password=password,
                                 site=site, path_prefix=path_prefix)
    sysinfo = c.stat_sysinfo()
    print(json.dumps(sysinfo, indent=4))

if __name__ == "__main__":
    unifi_test(auto_envvar_prefix="UNIFI_TEST")
