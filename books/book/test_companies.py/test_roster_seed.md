# Companies — contacts + pipeline, most live money first (top 12)

company                contacts segment      stage        deals open pipeline_eur won
Oscorp OÜ                     1 erp          meeting          3    2       102500 
Gringotts Ab                  1 ecommerce    —                4    1        80000 yes
Lacuna OÜ                     1 analytics    conversation     5    1        80000 yes
Wayne GmbH                    1 accounting   reached          1    1        80000 
Omni Oy                       1 ecommerce    reached          2    1        60000 
Vance Oy                      1 ecommerce    touched          1    1        60000 
Pierce Oy                     1 other        reached          2    1        45000 
Mooby Ab                      1 accounting   touched          1    1        35000 
Onyx Oy                       1 consultancy  conversation     1    1        35000 
Pymt Oy                       1 analytics    touched          4    1        35000 
Dunder Ab                     1 other        reached          3    1        22500 yes
Vertex OÜ                     1 analytics    reached          1    1        22500 

total companies: 50

# Invariants

every contact company listed: True
every deal company listed: True
Oscorp OÜ: pipeline_eur=102500 == sum(open deals)=102500 → True
sorted by (open pipeline, size, name): True
