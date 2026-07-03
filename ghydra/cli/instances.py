"""Instance management commands."""

import click
import sys

from ..client.exceptions import GhidraError
from ..utils import should_page, page_output, rich_echo


@click.group('instances')
def instances():
    """Manage Ghidra instances.

    Commands for discovering, registering, and managing multiple Ghidra
    instances running with the GhydraMCP plugin.
    """
    pass


@instances.command('list')
@click.pass_context
def list_instances(ctx):
    """List all known Ghidra instances with automatic discovery.

    This command automatically scans for new instances on ports 8192-8201
    before returning the list. This is the primary command for discovering instances.

    \b
    Example:
        ghydra instances list
    """
    client = ctx.obj['client']
    formatter = ctx.obj['formatter']
    config = ctx.obj['config']

    try:
        # For CLI, we implement simple discovery by trying to connect to known ports
        # and collecting successful connections
        instances_data = _discover_instances(client, config)

        output = formatter.format_instances_list(instances_data)

        if should_page(config, ctx.obj['output_json']):
            page_output(output, use_pager=config.page_output)
        else:
            click.echo(output)

    except GhidraError as e:
        error_output = formatter.format_error(e)
        rich_echo(error_output, err=True)
        ctx.exit(1)


@instances.command('discover')
@click.option('--host', help='Hostname or IP to scan (default: from config or localhost)')
@click.option('--start-port', type=int, default=8192, help='Starting port for discovery')
@click.option('--end-port', type=int, default=8201, help='Ending port for discovery')
@click.pass_context
def discover(ctx, host, start_port, end_port):
    """Discover Ghidra instances on a specific host.

    Use this command only when you need to scan a different host or custom port range.
    For normal usage, 'instances list' performs automatic discovery.

    \b
    Examples:
        ghydra instances discover --host 192.168.1.100
        ghydra instances discover --start-port 8192 --end-port 8220
    """
    client = ctx.obj['client']
    formatter = ctx.obj['formatter']
    config = ctx.obj['config']

    # Override host if specified
    scan_host = host or config.default_host

    try:
        instances_data = _discover_instances_on_host(
            scan_host,
            range(start_port, end_port + 1),
            config
        )

        output = formatter.format_instances_list(instances_data)

        if should_page(config, ctx.obj['output_json']):
            page_output(output, use_pager=config.page_output)
        else:
            click.echo(output)

    except GhidraError as e:
        error_output = formatter.format_error(e)
        rich_echo(error_output, err=True)
        ctx.exit(1)


@instances.command('register')
@click.option('--port', '-p', type=int, required=True, help='Port number of the instance')
@click.option('--url', help='Custom URL if different from http://host:port')
@click.pass_context
def register(ctx, port, url):
    """Register a new Ghidra instance.

    Manually register a Ghidra instance if it wasn't discovered automatically.

    \b
    Examples:
        ghydra instances register --port 8195
        ghydra instances register --port 9000 --url http://192.168.1.100:9000
    """
    client = ctx.obj['client']
    formatter = ctx.obj['formatter']
    config = ctx.obj['config']

    if url is None:
        url = f"http://{config.default_host}:{port}"

    try:
        # Try to connect to the instance
        from ..client import GhidraHTTPClient
        test_client = GhidraHTTPClient(
            host=config.default_host if not url.startswith('http') else url.split('://')[1].split(':')[0],
            port=port,
            timeout=config.timeout
        )

        # Test connection by getting plugin version
        version_data = test_client.get('plugin-version')

        result_data = {
            "success": True,
            "result": f"Registered instance on port {port} at {url}",
            "instance": {
                "port": port,
                "url": url,
                "plugin_version": version_data.get("result", {}).get("plugin_version", "unknown"),
                "api_version": version_data.get("result", {}).get("api_version", "unknown")
            }
        }

        output = formatter.format_simple_result(result_data)
        click.echo(output)

    except GhidraError as e:
        error_output = formatter.format_error(e)
        rich_echo(error_output, err=True)
        ctx.exit(1)


@instances.command('unregister')
@click.option('--port', '-p', type=int, required=True, help='Port number to unregister')
@click.pass_context
def unregister(ctx, port):
    """Unregister a Ghidra instance.

    Remove an instance from the known instances list.

    \b
    Example:
        ghydra instances unregister --port 8195
    """
    formatter = ctx.obj['formatter']

    # For CLI, we don't maintain a persistent registry, so this is a no-op
    # But we can provide feedback
    result_data = {
        "success": True,
        "result": f"Note: CLI doesn't maintain persistent instance registry. Port {port} noted."
    }

    output = formatter.format_simple_result(result_data)
    click.echo(output)


@instances.command('use')
@click.option('--port', '-p', type=int, required=True, help='Port number to use as default')
@click.pass_context
def use(ctx, port):
    """Set the current working Ghidra instance.

    Changes the default instance for subsequent commands.

    \b
    Example:
        ghydra instances use --port 8195
    """
    client = ctx.obj['client']
    formatter = ctx.obj['formatter']
    config = ctx.obj['config']

    try:
        # Test connection to the instance
        from ..client import GhidraHTTPClient
        test_client = GhidraHTTPClient(
            host=config.default_host,
            port=port,
            timeout=config.timeout
        )

        # Get program info
        program_data = test_client.get('program')
        program_info = program_data.get("result", {})

        # Update client's port
        client.port = port
        client.base_url = f"http://{client.host}:{port}"

        # Save to config if desired
        if ctx.obj.get('verbose'):
            click.echo(f"Switched to instance on port {port}", err=True)

        result_data = {
            "success": True,
            "result": {
                "message": f"Now using Ghidra instance on port {port}",
                "port": port,
                "program": program_info.get("name", "unknown"),
                "project": program_info.get("programId", "unknown").split(":")[0]
            }
        }

        output = formatter.format_simple_result(result_data)
        click.echo(output)

    except GhidraError as e:
        error_output = formatter.format_error(e)
        rich_echo(error_output, err=True)
        ctx.exit(1)


@instances.command('current')
@click.pass_context
def current(ctx):
    """Get information about the current working instance.

    Shows which Ghidra instance will be used for subsequent commands.

    \b
    Example:
        ghydra instances current
    """
    client = ctx.obj['client']
    formatter = ctx.obj['formatter']

    try:
        # Get program info from current instance
        program_data = client.get('program')
        program_info = program_data.get("result", {})

        result_data = {
            "success": True,
            "result": {
                "port": client.port,
                "url": client.base_url,
                "program": program_info.get("name", "unknown"),
                "project": program_info.get("programId", "unknown").split(":")[0]
            }
        }

        output = formatter.format_simple_result(result_data)
        click.echo(output)

    except GhidraError as e:
        error_output = formatter.format_error(e)
        rich_echo(error_output, err=True)
        ctx.exit(1)


# Helper functions for instance discovery

def _discover_instances(client, config):
    """Discover instances on default host using quick scan."""
    return _discover_instances_on_host(
        config.default_host,
        range(8192, 8202),  # Quick discovery range
        config
    )


def _discover_instances_on_host(host, port_range, config):
    """Discover instances via the plugin /instances API (single source of truth)."""
    from ..client import GhidraHTTPClient

    # Prefer base port; any live instance exposes the full activeInstances map.
    probe_order = [8192] + [p for p in port_range if p != 8192]

    for port in probe_order:
        try:
            test_client = GhidraHTTPClient(host=host, port=port, timeout=0.5)
            version_data = test_client.get('plugin-version')
            if not version_data.get("success"):
                continue

            version_info = version_data.get("result", {})
            plugin_version = version_info.get("plugin_version", "unknown")
            api_version = version_info.get("api_version", "unknown")

            instances_resp = test_client.get('instances')
            raw = instances_resp.get("result", [])
            found_instances = []
            for inst in raw:
                found_instances.append({
                    "port": inst.get("port", port),
                    "url": inst.get("url", f"http://{host}:{inst.get('port', port)}"),
                    "project": inst.get("project") or "-",
                    "file": inst.get("file") or "-",
                    "plugin_version": plugin_version,
                    "api_version": api_version,
                })

            found_instances.sort(key=lambda x: x['port'])
            return {"success": True, "instances": found_instances}
        except Exception:
            continue

    return {"success": True, "instances": []}
