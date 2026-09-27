# The round trip: repeatedly clicking a mid-ranked hit lifts it to the top

cold ranking (text-match), learned=False:
  0. deal:sec002
  1. deal:sec005
  2. deal:sec011
  3. deal:sec020
  4. deal:sec021
  5. deal:sec029
  6. deal:sec035
  7. deal:sec037
target to train (rank 3): deal:sec020

warm ranking, learned=True:
  0. deal:sec020   <- trained
  1. deal:sec002
  2. deal:sec005
  3. deal:sec011
  4. deal:sec021
  5. deal:sec029
  6. deal:sec035
  7. deal:sec037

target moved rank 3 -> 0
