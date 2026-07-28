#!/bin/bash

if [[ -z "$1" ]]; then
  # Wenn kein Argument angegeben ist, zeige die Hilfe an
  python3 ./asst.py -h
else
  # Sonst führe das Python-Skript mit den gegebenen Argumenten aus
  python3 ./asst.py -k $AZURE_OPENAI_API_KEY "$@"
fi
