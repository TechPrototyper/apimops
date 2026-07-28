import argparse
import sys


class ArgumentParseError(Exception):
    """Exception raised for errors in the argument parsing."""


class ThrowingArgumentParser(argparse.ArgumentParser):
    """Custom argument parser that throws exceptions on errors and displays help."""

    def error(self, message):
        if message:
            print(f"Error: {message}")
        self.print_usage()
        print("\nUse '--help' or '-h' for further information.")
        raise ArgumentParseError(message)

    def print_usage(self, file=None):
        usage_prefix = "transfer" if hasattr(sys, "frozen") else "python transfer.py"
        print(f"usage: {usage_prefix} [options]", file=file)
        super().print_usage(file)

    def print_help(self, file=None):
        usage_prefix = "transfer" if hasattr(sys, "frozen") else "python transfer.py"
        super().print_help(file)
        self.print_usage_examples(file, usage_prefix)

    def print_usage_examples(self, file=None, usage_prefix=None):
        if usage_prefix is None:
            usage_prefix = "transfer" if hasattr(sys, "frozen") else "python transfer.py"
        print("\nExamples:\n", file=file)
        print("1. Migration of a single API from one node to another:", file=file)
        print(f"   {usage_prefix} --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --api my-api --verbose", file=file)
        print("\n2. Migration of multiple APIs:", file=file)
        print(f"   {usage_prefix} --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --apis api1,api2,api3 --verbose", file=file)
        print("\n3. Migration using a transfer set:", file=file)
        print(f"   {usage_prefix} --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --transferset transfer-set.yaml --verbose", file=file)
        print("\n4. Migration and creation of a pull request:", file=file)
        print(f"   {usage_prefix} --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --apis api1,api2 --pullrequest --verbose", file=file)
        print("\n5. Migration with backup of current APIs:", file=file)
        print(f"   {usage_prefix} --source DEV-APIM-SERVICE --destination PROD-APIM-SERVICE --apis api1,api2 --backup --verbose", file=file)


def parse_arguments() -> argparse.Namespace:
    parser = ThrowingArgumentParser()
    parser.add_argument('--config', '-cfg', type=str, help='Path to JSON configuration file')
    parser.add_argument('--transferset', '-set', type=str, help='Path to Microsoft APIOps Extractor configuration file')
    parser.add_argument('--commitid', '-cid', type=str, help='Commit ID to use for the transfer')
    parser.add_argument('--api', '-a', type=str, help='Single API artifact to transfer')
    parser.add_argument('--apis', '-as', type=str, help='Comma-separated list of API artifacts to transfer')
    parser.add_argument('--backends', '-be', type=str, help='Comma-separated list of Backend artifacts to transfer')
    parser.add_argument('--diagnostics', '-diag', type=str, help='Comma-separated list of Diagnostics artifacts to transfer')
    parser.add_argument('--loggers', '-log', type=str, help='Comma-separated list of Logger artifacts to transfer')
    parser.add_argument('--namedvalues', '-nava', type=str, help='Comma-separated list of NamedValues artifacts to transfer')
    parser.add_argument('--products', '-prod', type=str, help='Comma-separated list of Products artifacts to transfer')
    parser.add_argument('--subscriptions', '-sub', type=str, help='Comma-separated list of Subscriptions artifacts to transfer')
    parser.add_argument('--tags', '-tg', type=str, help='Comma-separated list of Tag artifacts to transfer')
    parser.add_argument('--versionsets', '-vs', type=str, help='Comma-separated list of VersionSet artifacts to transfer')
    parser.add_argument('--source', '-src', type=str, required=True, help='Source node')
    parser.add_argument('--destination', '-dst', type=str, required=True, help='Destination node')
    parser.add_argument('--githubrepo', '-g', type=str, help='GitHub repository path')
    parser.add_argument('--githubtoken', '-i', type=str, help='GitHub token')
    parser.add_argument('--pullrequest', '-pr', action='store_true', help='Use pull request for transfer')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose mode')
    parser.add_argument('--debug', '-dbg', action='store_true', help='Enable debug mode')
    parser.add_argument('--continueonapinotfound', '-canf', action='store_true', help='Continue if API not found')
    parser.add_argument('--backup', '-b', action='store_true', help='Backup the current state of APIs before transfer')
    parser.add_argument('--push', action='store_true', help='Use push for transfer instead of pull request')

    try:
        return parser.parse_args()
    except ArgumentParseError:
        sys.exit(2)
    except SystemExit as e:
        if e.code != 0:
            parser.print_usage()
            print("\nUse '--help' or '-h' for further information.")
        raise
    except Exception as e:
        print(f"Unexpected Error: {e}")
        raise

