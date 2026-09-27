# Companies — contacts + pipeline, most live money first (top 12)

company                contacts segment      stage        deals open pipeline_eur won
Delos Ab                      1 consultancy  reached         24    4       170000 yes
Pendant Oy                    1 ecommerce    conversation    19    4       170000 
Spectre Oy                    2 ecommerce    reached          9    4       160000 yes
Pied Oy                       2 accounting   reached          8    3       130000 yes
Tyrell Oy                     1 erp          reached         10    2       125000 
Sterling Oy                   2 erp          conversation    10    3       102500 yes
Hanso GmbH                    1 accounting   reached          9    2       102500 yes
Pymt Oy                       3 accounting   reached         12    2        82500 yes
Prestige Oy                   2 other        reached         14    1        60000 yes
Vandelay Oy                   2 erp          touched         15    1        60000 yes
Lumon Oy                      2 ecommerce    reached          9    2        57500 yes
Acme OÜ                       1 accounting   —                9    2        50000 yes

total companies: 34

# Invariants

every contact company listed: True
every deal company listed: True
Delos Ab: pipeline_eur=170000 == sum(open deals)=170000 → True
sorted by (open pipeline, size, name): True
