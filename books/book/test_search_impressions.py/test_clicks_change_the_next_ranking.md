# The round trip: repeatedly clicking a mid-ranked hit lifts it to the top

cold ranking (text-match), learned=False:
  0. doc:sdc001
  1. doc:sdc009
  2. deal:sec002
  3. deal:sec005
  4. deal:sec011
  5. deal:sec020
  6. deal:sec021
  7. deal:sec029
target to train (rank 3): deal:sec005

warm ranking, learned=True:
  0. deal:sec005   <- trained
  1. deal:sec002
  2. deal:sec011
  3. deal:sec020
  4. deal:sec021
  5. deal:sec029
  6. doc:sdc001
  7. doc:sdc009

target moved rank 3 -> 0
