# as shipped: this repository's operator

call windows: ['0800', '1215', '1600']
unavailable thu: all
unavailable wed: ['0800']

# another company: different windows, no blocked days, its own rhythm

call windows: ['0900', '1330', '1530']  (the catch-all stays: True)
the brief at 08h, 12h, 16h picks: ['0900', '1330', '1530']
Thursday 0900 callable: True
Monday note: 'Monday — pipeline review'
