# Accented terms survive tokenization (not shredded into single chars)

tokens('Hämeenlinnan päätös') = ['hämeenlinnan', 'päätös']

# …and the accented query retrieves the accented document

  1. [doc    ] Hinnoittelun päätös
