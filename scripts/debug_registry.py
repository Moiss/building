
# -*- coding: utf-8 -*-
import logging
import sys

def run_debug(env):
    print(">>> REGISTRY DEBUG <<<")
    keys = sorted(env.registry.models.keys())
    count = 0
    for k in keys:
        if 'building' in k:
            print(f"FOUND: {k}")
            count += 1
    
    if count == 0:
        print("NO 'building' models found in registry!")
    else:
        print(f"Found {count} 'building' models.")
        
    # Check explicitly
    if 'building.work' in env.registry.models:
        print("building.work IS present.")
    else:
        print("building.work IS MISSING.")

if __name__ == '__main__':
    run_debug(env)
