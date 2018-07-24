#!/usr/bin/env python

import numpy as np
import sys 

nums = []
for line in sys.stdin:
    nums.append(int(line))
print('mean: {} us, std: {} us'.format(np.mean(np.array(nums)), np.std(np.array(nums))))
