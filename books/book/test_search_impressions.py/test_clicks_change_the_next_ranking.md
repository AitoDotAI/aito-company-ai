# The round trip: repeatedly clicking a mid-ranked hit lifts it to the top

cold ranking (text-match), learned=False:
  0. deal:sec004
  1. deal:sec005
  2. deal:sec008
  3. deal:sec009
  4. deal:sec013
  5. deal:sec015
  6. deal:sec019
  7. deal:sec026
target to train (rank 3): deal:sec009

warm ranking, learned=True:
  0. deal:sec009   <- trained
  1. deal:sec004
  2. deal:sec005
  3. deal:sec008
  4. deal:sec013
  5. deal:sec015
  6. deal:sec019
  7. deal:sec026

target moved rank 3 -> 0
