#!/bin/bash

export PYTHONPATH=.

if [ "$1" == "-1" ]; then
    nosetests;
else
    watch -n 1 -- nosetests;
fi
