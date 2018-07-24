#!/bin/bash

exps=(
    "341 79 32 4"
    "224 224 3 1"
    "56 56 256 1"
    "7 7 512 2"
)

virts=(
    "baremetal"
    "vm"
    "container"
)

for virt in "${virts[@]}"; do
    echo "--------------${virt}---------------"
    for exp in "${exps[@]}"; do
        printf "${exp}: "
        cat ${virt}-conv/* | tr -s ' ' | grep "${exp}" | cut -d ' ' -f 14 | python stats.py
    done
done