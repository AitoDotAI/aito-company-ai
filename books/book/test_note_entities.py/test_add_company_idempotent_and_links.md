# add a brand-new company

company_id=novaco  name=NovaCo  created=True

# adding it again is idempotent (safe to press twice)

created=False  count_unchanged=True

# the slug folds case, so a different-cased spelling hits the same row

'NOVACO' -> novaco  created=False

# a document naming the new company resolves its company_id link

doc.company='NovaCo'  ->  company_id.name='NovaCo'
