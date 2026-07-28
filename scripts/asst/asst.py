"""
Assistant Manager - small tool to call OpenAI Assistants from the command Line on MacOS
by Tim Walter, 02 and 04/2024; special adapted version for creating a commit message 08/24
It is part of Tim's extensions, i.e. is stored in the directory ~/custom-scripts.
There we also find the corresponding Z-shell script, asst.sh, which calls this Python script.

Temporarily adapted to Github; should be handled differently in own repo and with the ability to call it from any script.
This is a prototype.

The config section was updated, because the data is now read from the config.yaml file for the apimops solution:

  open_ai:
    endpoint: "https://someendpoint.openai.azure.com/" # OpenAI Endpoint
    api_key: "api key provided here" # OpenAI API Key
    api_version: "2024-02-15-preview" # OpenAI API Version
    assistant:
        name: "CommitMessenger"
        id: "asst_my_assistant_id"
        description: "Provides a one-line summary of a git diff-log, GPT4-32K"
"""

import json
from openai import OpenAI, AzureOpenAI
import argparse
import shutil
from textwrap import wrap
import os
import sys
import yaml

class AssistantManager:
    """
    Manages a list of OpenAI assistants loaded from a configuration file.
    """
    def __init__(self, config_file="config.yaml"):
        """
        Initialize the AssistantManager by loading assistants from the config file.

        Args:
            config_file (str): Path to the configuration YAML file.
        """
        p = os.getcwd()
        print("DEBUG: Current path is:", p)
        if p.endswith("scripts/asst"):
            path = "../../"
        elif p.endswith("scripts"):
            path = "../"
        else:
            path = ""

        config_file = path + config_file

        print("Config-File is:", config_file)

        with open(config_file, "r") as file:
            config = yaml.safe_load(file)

        assistants_config = config.get("general", {}).get("open_ai", {}).get("assistant", None)
        
        if assistants_config:
            # If there is only one assistant, put it in a list
            self.assistants = [assistants_config]
        else:
            self.assistants = []

        print(self.assistants)
        print(self.assistants[0])

    def find_id(self, name: str):
        """
        Find the ID of an assistant by name.

        Args:
            name (str): The name of the assistant.
        Returns:
            str or None: The assistant's ID if found, else None.
        """
        for assistant in self.assistants:
            if assistant['name'].lower() == name.lower():
                return assistant['id']
        return None

    def find(self, name: str):
        """
        Find the assistant configuration by name.

        Args:
            name (str): The name of the assistant.
        Returns:
            dict or None: The assistant configuration if found, else None.
        """
        for assistant in self.assistants:
            if assistant['name'].lower() == name.lower():
                return assistant
        return None

    def list(self, search: str = None):
        """
        List all assistants, optionally filtering by a search string.

        Args:
            search (str, optional): Filter assistants by name.
        Returns:
            list: List of assistant configurations.
        """
        if search:
            return [assistant for assistant in self.assistants if search.lower() in assistant["name"].lower()]
        return self.assistants

from textwrap import wrap
import shutil

def list_assistants(manager):
    """
    Print a formatted list of all assistants managed by the AssistantManager.

    Args:
        manager (AssistantManager): The manager instance.
    """
    assistants = manager.list()
    name_width = max(len(assistant["name"]) for assistant in assistants)
    terminal_width = shutil.get_terminal_size((80, 20)).columns
    description_start = name_width + 2  # Distance from name to description
    description_width = terminal_width - description_start
    
    print("")

    # Headings
    print(f"{'Assistant'.ljust(name_width)}  {'Description'.ljust(description_width)}")
    # Separator lines
    print(f"{'-' * name_width}  {'-' * description_width}")
    
    for assistant in assistants:
        name = assistant['name'].ljust(name_width)
        description = assistant['description']
        wrapped_description_lines = wrap(description, width=description_width)
        first_line = True
        for line in wrapped_description_lines:
            if first_line:
                print(f"{name}  {line}")
                first_line = False
            else:
                print(f"{' ' * description_start}{line}")

    print("")

def read_file(filepath):
    """
    Read the contents of a file as a string.

    Args:
        filepath (str): Path to the file.
    Returns:
        str: File contents.
    """
    with open(filepath, "r", encoding="utf-8") as file:
        return file.read()

def create_thread(client, content, assistant_id):
    """
    Create a new thread for the assistant with the given content.

    Args:
        client: The OpenAI/AzureOpenAI client instance.
        content (str): The user message content.
        assistant_id (str): The assistant's ID.
    Returns:
        Thread object.
    """
    thread = client.beta.threads.create(
        messages=[
            {
                "role": "user",
                "content": content
            }
        ]
    )
    return thread

def run_assistant(api_key, assistant_id, content):
    """
    Run the assistant with the given API key, assistant ID, and user content.

    Args:
        api_key (str): The OpenAI API key.
        assistant_id (str): The assistant's ID.
        content (str): The user message content.
    Returns:
        str: The assistant's response message.
    Raises:
        Exception: If the assistant run fails or no response is found.
    """
    debug = int(os.getenv("DEBUG")) # 0 = False, 1 = True

    if debug: print("run_assistant called:")

    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    
    if debug: print(f"api_key: {api_key}, endpoint: {endpoint}, api_version: {api_version}")

    if not api_key or not endpoint:
        raise EnvironmentError("AZURE_OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT environment variable is not set.")
    
    try:            
        client = AzureOpenAI(api_key=api_key, api_version=api_version, azure_endpoint=endpoint)
    except Exception as e:
        if debug: 
            print(f"Error creating AzureOpenAI client: {e}", end="\n\n")
        raise e

    thread = create_thread(client, content, assistant_id)

    if debug: print(f"thread: {thread.id}")

    thread_id = thread.id

    run = client.beta.threads.runs.create(thread_id=thread_id, assistant_id=assistant_id)

    if debug: print(f"run: {run.id}")

    run_id = run.id

    while True:
        updated_run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
        status = updated_run.status
        if status in ["completed", "failed", "cancelled", "expired"]:
            if debug: print(f"Status: {status}")
            break
        if debug: print(".", end="", flush=True)

    if status == "completed":
        if debug: print("Run completed successfully.")
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        if messages.data and len(messages.data) > 0:
            last_message = messages.data[0].content[0].text.value
            return last_message
        else:
            raise Exception("No response message found.")
    else:
        raise Exception(f"Run failed with status: {status}")

def parse_arguments():
    """
    Parse command-line arguments for the assistant manager.

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="OpenAI Assistant Manager")
    parser.add_argument("-a", "--assistant", help="Name of the assistant")
    parser.add_argument("-p", "--prompt", help="User prompt")
    parser.add_argument("-f", "--filepath", help="Path to input file, UTF-8 encoded")
    parser.add_argument("-k", "--apikey", help="OpenAI API key")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("-l", "--list", action="store_true", help="List all assistants", required=False)

    args = parser.parse_args()

    if args.verbose:
        print("Not implemented.")
        # Standard logging framework integration could be added here

    return args

def main():
    """
    Main entry point for the assistant manager script.
    Handles argument parsing and runs the requested assistant or lists assistants.
    """
    args = parse_arguments()
    manager = AssistantManager()

    if args.list:
        list_assistants(manager)
        return

    assistant_id = manager.find_id(args.assistant)
    if not assistant_id:
        print(f"Assistant {args.assistant} not found.")
        return

    if args.prompt:
        content = args.prompt
    elif args.filepath:
        content = read_file(args.filepath)
    elif not sys.stdin.isatty():  # Check if data is available on stdin
        content = sys.stdin.read()
    else:
        print("No content provided to process.")
        return

    try:
        result = run_assistant(args.apikey, assistant_id, content)
        print(result)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
